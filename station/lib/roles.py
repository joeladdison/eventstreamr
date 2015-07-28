import os
import time
import logging

from . import config, devices

logger = logging.getLogger('eventstreamr')


def devmon(state):
    control = state.device_control.setdefault('devmon', {})

    params = {
        'bin': state.local_config['dirs']['scripts'],
    }
    control['command'] = state.commands['devmon'].format(**params)

    device = {
        'role': 'devmon',
        'id': 'devmon',
        'type': 'internal'
    }
    run_stop(state, device)


def ingest(state):
    if state.dvswitch['running']:
        for device in state.station_config['devices']:
            device['role'] = 'ingest'

            if device['type'] == 'dv':
                # Check dv exists
                if os.path.exists(state.station_config['devices']['dv'][device['id']]['path']):
                    run_stop(state, device)
                elif state.station_config['device_control'][device['id']]['run'] == 1:
                    # If we're restarting we should refresh the devices and try again
                    logger.warn('%s has been disconnected', device['id'])
                    # It's not ideal, but dvgrab hangs if no camera exist.
                    # devmon will restart it when it's plugged in again.
                    state.station_config['device_control'][device['id']]['run'] = 0
                    run_stop(state, device)

                    # Set status
                    state.device_control[device['id']]['timestamp'] = time.time()
                    state.status[device['id']]['running'] = 0
                    state.status[device['id']]['status'] = 'disconnected'
                    state.status[device['id']]['state'] = 'hard'
                    config.post_config(state)
                elif state.station_config['device_control'][device['id']]['run'] == 2:
                    logger.warn('%s has been restarted, refreshing devices', device['id'])
                    state.devices = devices.all()
                    config.post_config(state)
                    run_stop(state, device)
            else:
                run_stop(state, device)


def mixer(state):
    device = {
        'role': 'mixer',
        'id': 'dvswitch',
        'type': 'mixer'
    }
    run_stop(state, device)

    loop = {
        'role': 'ingest',
        'id': state.station_config['mixer']['loop'],
        'type': 'file'
    }
    if state.station_config['mixer']['loop'] and state.dvswitch['running']:
        if os.path.exists(state.station_config['mixer']['loop']):
            run_stop(state, loop)
        else:
            # Set status
            state.device_control[loop['id']]['timestamp'] = time.time()
            state.status[loop['id']]['running'] = 0
            state.status[loop['id']]['status'] = 'file_not_found'
            state.status[loop['id']]['state'] = 'hard'
            state.status[loop['id']]['name'] = 'standby loop'
            config.post_config(state)


def stream(state):
    device = {
        'role': 'stream',
        'id': state.station_config['stream']['stream'],
        'type': 'stream'
    }
    run_stop(state, device)


def record(state):
    state.device_control.setdefault('record', {})

    if not state.device_control['record'].get('record_path'):
        # Get path
        path_vars = {
            'room': state.station_config['room'],
            'date': state.date.strftime(config.DATE_FORMAT),
        }
        record_path = state.station_config['record_path'].format(**path_vars)
        state.device_control['record']['record_path'] = record_path
    else:
        record_path = state.device_control['record']['record_path']

    if not os.path.exists(record_path):
        # Create directory
        os.makedirs(record_path)

        if os.path.exists(record_path):
            logger.info("Path created for record: %s", record_path)
        else:
            if (state.device_control['record'].get('run_count', 0) > 5 and
                    time.time() % 10 != 0):
                # Slow down attempts to create directory after multiple failures
                return

            logger.error("Path creation failed for record: %s", record_path)

            state.device_control['record']['run_count'] += 1
            state.status.setdefault('record', {})
            state.status['record']['type'] = 'record'
            state.status['record']['timestamp'] = time.time()
            state.status['record']['running'] = 0
            state.status['record']['status'] = "not_writeable"
            state.status['record']['state'] = "hard"
            return

    if state.dvswitch['running'] == 1:
        device = {
            'role': 'record',
            'id': 'record',
            'type': 'record',
        }
        run_stop(state, device)


ROLE_FUNCTIONS = {
    'devmon': devmon,
    'mixer': mixer,
    'ingest': ingest,
    'stream': stream,
    'record': record,
}


def run_stop(state, device):
    current_time = time.time()
    did = device['id']

    control = state.device_control.setdefault(did, {})
    status = state.status.setdefault(did, {})

    # Build command for execuion and save it for future use
    command = control.get('command')
    if not command:
        if device['role'] == 'ingest':
            command = ingest_command(state, device['id'], device['type'])
        elif device['role'] == 'mixer':
            command = mixer_command(state, device['id'], device['type'])
        elif device['role'] == 'stream':
            command = stream_command(state, device['id'], device['type'])
        elif device['role'] == 'record':
            command = record_command(state, device['id'], device['type'])

        control['command'] = command
        logger.info(
            'Command for %s - %s: %s', device['id'], device['type'], command)

    # Only deal with internal services. External are managed by web
    run_type = control.get('run', None)
    if state.station_config['run'] == 1 and (
            run_type in (None, 1) or device['type'] == 'internal'):
        # Ensure device is set to be running
        control['run'] = 1

        # Get current state
        program_name = control.get('program_name')
        running = False
        if program_name:
            proc_state = state.supervisor.process_state(program_name)
            running = proc_state['statename'] == 'RUNNING'

        if not running:
            # Start device
            if not control.get('timestamp'):
                control['timestamp'] = current_time
                status['running'] = 0
                status['status'] = 'starting'
                status['state'] = 'sfot'
                status['type'] = device['type']
                status['timestamp'] = current_time

            if device['type'] == 'mixer':
                logger.info('Starting DVswitch')
            elif device['type'] == 'internal':
                logger.info('Starting %s', did)
            else:
                logger.info('Connect %s to DVswitch', did)

            program_name = config.create_process_config(
                state, device, command)
            started = state.supervisor.start_process(program_name)
            if not started:
                # Problem starting
                logger.warn('Failed to start device: %s', did)

                # Refresh devices
                state.devices = devices.all()

                # Force command rebuild
                control['command'] = ''

                config.post_config(state)

        # Update state
        proc_state = state.supervisor.process_state(program_name)

        if proc_state['statename'] == 'RUNNING':
            status['running'] = 1
            status['status'] = 'started'
            status['state'] = 'hard'
            control['timestamp'] = current_time
        else:
            status['running'] = 0
            status['status'] = 'stopped'
            status['state'] = 'hard'
    elif run_type is not None:
        # Stop device
        program_name = control['program_name']
        stopped = state.supervisor.stop_process(program_name)
        if stopped:
            # Process stopped
            logger.info('Stopped %s', did)

            control['running'] = 0

            # Get new state
            # proc_state = state.supervisor.process_state(program_name)
            control['timestamp'] = current_time
            status['running'] = 0
            status['status'] = 'stopped'
            status['state'] = 'hard'

        control['timestamp'] = 0

    if run_type == 2 and not control['running']:
        # Restart device
        logger.info('Restarting %s', did)

        control['run'] = 1
        control['timestamp'] = current_time
        control['command'] = ''

        # Refresh devices
        state.devices = devices.all()

        # Update status
        status['status'] = 'restarting'
        status['state'] = 'hard'

        config.write_config(state.station_config_path, state.station_config)

    # TODO: Add more status information to state
    config.post_config(state)


def ingest_command(state, device_id, device_type):
    if device_type == 'file':
        did = device_id
    elif device_type == 'alsa':
        state.devices = devices.all()
        did = state.devices['alsa'][device_id]['alsa']
    else:
        did = state.devices[device_type][device_id]['device']

    params = {
        'device': did,
        'bin': state.local_config['dirs']['scripts'],
        'host': state.station_config['mixer']['host'],
        'post': state.station_config['mixer']['post'],
    }

    command = state.commands[device_type].format(**params)
    return command


def mixer_command(state, device_id, device_type):
    params = {
        'port': state.station_config['mixer']['port'],
    }

    command = state.commands['dvswitch'].format(**params)
    return command


def record_command(state, device_id, device_type):
    params = {
        'host': state.station_config['mixer']['host'],
        'port': state.station_config['mixer']['port'],
        'room': state.station_config['room'],
        'path': state.device_control[device_id]['recordpath'],
    }

    command = state.commands['record'].format(**params)
    return command


def stream_command(state, device_id, device_type):
    params = {
        'host': state.station_config['mixer']['host'],
        'port': state.station_config['mixer']['port'],
        'id': device_id,
        'shost': state.station_config['stream']['host'],
        'sport': state.station_config['stream']['port'],
        'spassword': state.station_config['stream']['password'],
        'stream': state.station_config['stream']['stream'],
    }

    command = state.commands['stream'].format(**params)
    return command
