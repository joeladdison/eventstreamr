import os
import json
import socket
import uuid
import datetime
import logging
import requests
import httplib
try:
    import configparser
except:
    # Python 2.x
    import ConfigParser as configparser

from . import process, devices


# Setup logging
httplib.HTTPConnection.debuglevel = 1
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

logger = logging.getLogger('eventstreamr')


DATE_FORMAT = '%Y%m%d'
DEFAULT_ROOM = 'room'
DEFAULT_MIXER_IP = '127.0.0.1'


JSON_HEADERS = {
    'station-mgr': 1,
    'Content-Type': 'application/json'
}


class State(object):

    def __init__(self):
        self.local_config = {}
        self.station_config = {}
        self.commands = {}
        self.devices = {}
        self.dvswitch = {
            'check': 1,
            'running': 0
        }
        self.date = datetime.date.today()
        self.device_control = {}
        self.running = True

        # TODO
        self.status = {}
        self.controller = {'running': 0}

        self.local_config_path = None
        self.station_config_path = None
        self.command_config_path = None

        self.supervisor = process.SupervisorProxy()
        # Connect to Supervisor if configured
        supervisor_config = self.local_config.get('supervisor')
        if (supervisor_config and supervisor_config.get('url') and
                supervisor_config.get('sock')):
            self.supervisor.connect(
                supervisor_config['url'], supervisor_config['sock'])

    @classmethod
    def from_files(
            cls, local_config_path, station_config_path, command_config_path):
        local_config = load_local_config(local_config_path)
        station_config = load_station_config(station_config_path)
        commands = load_commands(command_config_path)

        if not station_config.get('station_id'):
            station_config['station_id'] = get_station_id()
        all_devices = devices.all()
        state = cls()
        state.local_config_path = local_config_path
        state.station_config_path = station_config_path
        state.command_config_path = command_config_path
        state.local_config = local_config
        state.station_config = station_config
        state.commands = commands
        state.devices = all_devices
        return state


def load_config(config_path, default_config):
    config = None
    if os.path.exists(config_path):
        # Read existing
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        config = default_config()
        with open(config_path, 'w') as f:
            json.dump(config, f)
    return config


def load_local_config(config_path):
    return load_config(config_path, blank_local_config)


def blank_local_config():
    return {
        'controller': 'http://10.4.4.10:5001',
        'script_bin': 'bin',
        'supervisor': {
            "url": '',
            "sock": '',
            'ini_dir': ''
        },
        "dirs": {
            "scripts": "/home/av/eventstreamr/station/bin",
            "working": "/home/av/eventstreamr",
            "queue": "/localbackup/queue/",
            "recordings": "/localbackup/recordings/",
            "output": "/localbackup/output/"
        },
        "schedule": "test/schedule.json",
        "backgrounds": {
            "title": "media/title.jpg",
            "credits": "media/credits.jpg"
        }
    }


def load_station_config(config_path):
    return load_config(config_path, blank_station_config)


def blank_station_config():
    hostname = get_hostname()
    room = DEFAULT_ROOM
    current_date = datetime.date.today().strftime(DATE_FORMAT)
    mixer_ip = DEFAULT_MIXER_IP

    return {
        "roles": [],
        "nickname": hostname,
        "room": room,
        "record_path": "/localbackup/{0}/{1}".format(room, current_date),
        "mixer": {
            "port": "1234",
            "host": mixer_ip,
            "loop": "/home/av/eventstreamr/baseimage/video/standby.dv"
        },
        "sync": {
            "host": "storage.local",
            "path": "/storage"
        },
        "devices": "all",
        "device_control": {},
        "run": "0",
        "stream": {
            "host": "",
            "port": "",
            "password": "",
            "stream": ""
        }
    }


def load_commands(config_path):
    config = None
    if os.path.exists(config_path):
        # Read existing
        with open(config_path, 'r') as f:
            config = json.load(f)
    return config


def register_station(state):
    logger.info(
        "Registering with controller: %s/api/station/%s",
        state.local_config['controller'], state.station_config['station_id'])

    # TODO: Post to controller
    register_url = '{0}/api/station/{1}'.format(
        state.local_config['controller'], state.station_config['station_id'])
    try:
        r = requests.post(register_url, headers=JSON_HEADERS)
    except requests.exceptions.ConnectionError:
        # Controller is not available
        logger.warn('Unable to connect to controller')
        return

    if r.status_code == 201:
        # 201 => send config to controller
        logger.info(
            'Posting config to controller (%s)',
            state.local_config['controller'])
        url = '{0}/api/station'.format(state.local_config['controller'])
        r = requests.post(
            url, data=json.dumps(state.station_config), headers=JSON_HEADERS)

        # TODO: Log response
        # logger.debug()

    if r.status_code == 200:
        try:
            content = r.json()
            state.station_config = content
        except ValueError:
            # Not config that we want
            pass

        write_config(state.station_config_path, state.station_config)
    elif r.status_code == 204:
        state.controller['running'] = 1
        logger.warn('Connected to controller but not registered')
    else:
        state.controller['running'] = 0
        logger.warn(
            'Failed to connect to controller: [%d] %s',
            r.status_code, r.reason)
        logger.info('Falling back to local config')

    # TODO: Fix devices
    # Run all connected devices - need to get devices to return an array
    if state.station_config['devices'] == 'all':
        state.station_config['devices'] = devices['array']

    state.station_config['manager']['pid'] = os.getpid()
    post_config(state)


def post_config(state):
    state.devices = devices.all()

    # Post to manager API
    url = 'http://127.0.0.1:3000/internal/settings'
    # TODO: is station config correct?
    try:
        r = requests.post(
            url, data=json.dumps(state.station_config), headers=JSON_HEADERS)
    except requests.exceptions.ConnectionError:
        logger.warn("Unable to post config - controller not available")
        return

    logger.info('Config posted to API')
    logger.debug(r.text)

    status = {
        'status': state.status,
        'station_id': state.station_config['station_id'],
        'nickname': state.station_config['nickname'],
    }

    logger.debug('Status: %s', json.dumps(status))

    # Post status to mixer
    # TODO: remove port
    url = 'http://{0}:3000/status/{1}'.format(
        state.station_config['mixer']['host'],
        state.station_config['station_id'])
    r = requests.post(url, data=json.dumps(status), headers=JSON_HEADERS)
    logger.info("Status posted to Mixer API -> %s", url)
    logger.debug(r.text)

    # Post status + devices to controller
    if state.controller['running']:
        data = {
            'status': status['status'],
            'devices': state.devices['all']
        }

        url = 'http://{0}/api/stations/{1}/partial'.format(
            state.local_config['controller'],
            state.station_config['station_id'])
        r = requests.post(url, data=json.dumps(data), headers=JSON_HEADERS)
        logger.info("Status posted to Controller API -> %s", url)
        logger.debug(r.text)


def get_config(state):
    r = requests.get('http://127.0.0.1:3000/internal/settings')
    logger.info('Config received from API')
    logger.debug(r.text)
    state.station_config = r.json()
    write_config(state.station_config_path, state.station_config)


def write_config(config_path, config):
    with open(config_path, 'w') as f:
        json.dump(config, f)
    logger.info("Config written to disk: %s", config_path)


def get_station_id():
    """
    Get a string representation of the MAC address for the computer.
    Note: if a MAC address is not found, a random value is returned.
    """
    mac = uuid.getnode()
    return ':'.join(("%012X" % mac)[i:i+2] for i in range(0, 12, 2))


def get_hostname():
    return socket.gethostname()


def create_process_config(state, device, command):
    name = "{0}_{1}".format(device['type'], device['id'])
    # Make a name that complies with supervisor naming guidelines
    program_name = name.replace(':', '_').replace(']', '_')

    supervisor_config = state.local_config.get('supervisor', {})
    if not supervisor_config.get('ini_dir'):
        logger.warn('Supervisor is not configured. Not able to run process')
        return

    # Write command to file
    command_config = {
        'command': command
    }
    command_file_name = "{0}.json".format(name)
    command_file_path = os.path.join(
        supervisor_config['ini_dir'], command_file_name)
    with open(command_file_path, 'w') as command_file:
        json.dump(command_file, command_config)

    # Create supervisor command
    params = {
        'bin': state.load_config['dirs']['scripts'],
        'command_json_path': command_file_path,
    }
    process = state.commands['command_proxy'].format(**params)

    # Create ini file
    config = configparser.RawConfigParser()
    header = 'program:{0}'.format(program_name)
    config.add_section(header)
    config.set(header, 'command', process)
    config.set(header, 'numprocs', '1')
    config.set(header, 'autorestart', 'true')
    config.set(header, 'user', state.local_config['user'])
    config.set(header, 'directory', state.local_config['dirs']['working'])
    config.set(header, 'umask', '0027')

    # Store ini file path and process name
    file_name = "{0}.ini".format(name)
    ini_path = os.path.join(supervisor_config['ini_dir'], file_name)
    with open(ini_path, 'w') as config_file:
        config.write(config_file)

    # Return process name
    settings = state.device_control.setdefault(device['id'], {})
    settings['supervisor_ini'] = ini_path
    settings['program_name'] = program_name
    settings['name'] = name

    return program_name
