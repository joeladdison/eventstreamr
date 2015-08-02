#!/usr/bin/env python
import os
import signal
import logging
import fnmatch
import shutil

from flask import Flask, request, jsonify, json, make_response
from flask.ext.cors import CORS

from encoding import encode_video
from encoding.lib import schedule
from lib import devices, config
from tasks import make_celery

from celery.utils.log import get_task_logger

app = Flask(__name__, static_url_path='')
app.config.update(
    CELERY_BROKER_URL='amqp://encoder:3nc0d3r@10.4.4.3:5672',
)

# Load config
config_filename = os.environ.get('API_SETTINGS', 'settings.json')
local_config = config.load_local_config(config_filename)
app.config['local_config'] = local_config

celery = make_celery(app)

eventstreamr_log = logging.getLogger("eventstreamr")
eventstreamr_log.setLevel(logging.DEBUG)
eventstreamr_log.propagate = True

CORS(app, allow_headers='Content-Type')


COMMAND_MAP = {
    'stop': 0,
    'start': 1,
    'restart': 2,
}


state = config.State()


@app.route("/")
def index():
    return app.send_static_file('index.html')


@app.route("/dump")
def dump():
    return {}  # Should be general data


@app.route("/settings")
def get_settings():
    return jsonify(**state.station_config)


@app.route("/settings/<macaddress>", methods=['POST'])
def update_settings(macaddress):
    global state
    if macaddress == state.station_config['macaddress']:
        manager = state.station_config['manager']['pid']
        station_config = request.get_json(silent=True)
        if station_config:
            # TODO: save station_config
            state.station_config = station_config
            station_config['manager']['pid'] = manager
            os.kill(manager, signal.SIGUSR1)
        return jsonify()
    else:
        response = jsonify(status='invalid_mac')
        response.status = 400
        return response


@app.route("/devices")
def get_devices():
    return jsonify(**devices.all())


@app.route("/command/<command>", methods=['POST'])
def run_command(command):
    error = False
    command_id = COMMAND_MAP.get('command')
    data = request.get_json(silent=True)
    if data['id'] == 'all':
        if command_id:
            state.station_config['run'] = command_id
        else:
            error = True
    else:
        if command_id:
            state.station_config['device_control'][data['id']]['run'] = command_id
        else:
            error = True

    if error:
        response = jsonify(status='unknown command')
        response.status = 400
    else:
        response = jsonify()
        os.kill(state.station_config['manager']['pid'], signal.SIGUSR1)

    return response


@app.route("/manager/update", methods=['POST'])
def manager_update():
    os.kill(state.station_config['manager']['pid'], signal.SIGHUP)
    return jsonify()


@app.route("/manager/reboot", methods=['POST'])
def manager_reboot():
    # TODO: Ensure reboot is possible
    os.system("sudo /sbin/shutdown -r -t 5 now &")
    os.kill(state.station_config['manager']['pid'], signal.SIGUSR1)
    return jsonify()


@app.route("/manager/refresh", methods=['POST'])
def manager_refresh():
    os.kill(state.station_config['manager']['pid'], signal.SIGUSR2)
    return jsonify()


@app.route("/status")
def get_status():
    return jsonify()


@app.route("/status/<mac>", methods=['POST'])
def update_status(mac):
    return jsonify()


# Internal communications
@app.route("/internal/settings", methods=['POST'])
def internal_settings_receive():
    data = request.get_json(silent=True)
    state.station_config = data
    app.logger.info('Received station config from manager')
    return jsonify()


@app.route("/internal/settings")
def internal_settings_send():
    app.logger.info('Sent station config to manager')
    return jsonify(**state.station_config)


# Encoding
@app.route("/encoding/rooms")
def available_rooms():
    # Load the schedule
    schedule_file = app.config['local_config']['schedule']
    schedule_url = app.config['local_config']['schedule_url']
    loaded_schedule = schedule.load_schedule(schedule_file, schedule_url)

    # Load the rooms
    rooms = schedule.available_rooms(loaded_schedule)
    return jsonify(rooms=rooms)


@app.route("/encoding/schedule")
def full_schedule():
    # Load the schedule
    schedule_file = app.config['local_config']['schedule']
    schedule_url = app.config['local_config']['schedule_url']
    loaded_schedule = schedule.load_schedule(schedule_file, schedule_url)

    # Use remote recording directory to give greater chance of file existance
    recording_dir = app.config['local_config']['dirs']['remote_recordings']

    # Load all talks
    talks = schedule.load_all_talks(loaded_schedule, recording_dir)
    return jsonify(talks=talks)


@app.route("/encoding/schedule/<room>")
def room_schedule(room):
    # Load the schedule
    schedule_file = app.config['local_config']['schedule']
    schedule_url = app.config['local_config']['schedule_url']
    loaded_schedule = schedule.load_schedule(schedule_file, schedule_url)

    # Use remote recording directory to give greater chance of file existance
    recording_dir = app.config['local_config']['dirs']['remote_recordings']

    # Load talks for the room
    talks = schedule.load_room_talks(loaded_schedule, recording_dir, room)
    return jsonify(room=room, talks=talks)


@app.route('/encoding/submit', methods=['POST'])
def submit_encoding_task():
    talk = request.get_json(silent=True)
    talk_id = talk['schedule_id']

    # Ensure queue folder exists
    queue_dir = app.config['local_config']['dirs']['queue']
    try:
        os.makedirs(queue_dir)
    except OSError:
        pass

    # Save job to queue
    job_file = '{0}.json'.format(talk_id)
    job_path = os.path.join(queue_dir, job_file)
    with open(job_path, 'w') as f:
            json.dump(
                talk, f, sort_keys=True, indent=4, separators=(',', ': '))

    app.logger.info('Submitted job to queue: {0}'.format(talk_id))

    # Create celery task
    if app.config['local_config']['use_celery']:
        do_encoding.delay(job_file)
        app.logger.info('Submitted job to celery: {0}'.format(talk_id))

    # TODO: Actually ensure we were successful
    success_msg = 'Encoding job for {0} submitted successfully'.format(talk_id)

    return jsonify(result=success_msg)


@app.route('/encoding/resubmit/<talk_id>')
def resubmit_encoding_task(talk_id):
    success_msg = {
        'msg': 'Encoding job for {0} submitted successfully'.format(talk_id),
        'type': 'success',
    }
    error_msg = {
        'msg': 'Encoding job for {0} could not be submitted'.format(talk_id),
        'type': 'error',
    }

    alerts = []
    # Create celery task
    if app.config['local_config']['use_celery']:
        job_file = '{0}.json'.format(talk_id)
        do_encoding.delay(job_file)
        app.logger.info('Submitted job to celery: {0}'.format(talk_id))
        alerts.append(success_msg)
    else:
        alerts.append(error_msg)

    return jsonify(alerts=alerts)


@app.route('/encoding/queue')
def encoding_queue():
    # Ensure queue folder exists
    queue_dir = app.config['local_config']['dirs']['queue']
    try:
        os.makedirs(queue_dir)
    except OSError:
        pass

    jobs = [f[:-5] for f in
            fnmatch.filter(os.listdir(queue_dir), '*.json')]
    return jsonify(queue=jobs)


@celery.task(name="api.do_encoding")
def do_encoding(talk_job_filename):
    """
    Schedule a task to encode the video as described by the JSON config str in
    `json_conf`.

    TODO: Include Youtube Uploading here as well?
    """
    print('Received job: {0}'.format(talk_job_filename))
    local_config = app.config['local_config']

    # Load talk job
    queue_dir = local_config['dirs']['queue']
    queue_job_path = os.path.join(queue_dir, talk_job_filename)
    if not os.path.exists(queue_job_path):
        print('Failed to load job: {0}'.format(queue_job_path))
        return

    # Move to in progress
    in_progress_dir = local_config['dirs']['in_progress']
    try:
        os.makedirs(in_progress_dir)
    except OSError:
        pass
    in_progress_job_path = os.path.join(in_progress_dir, talk_job_filename)
    shutil.move(queue_job_path, in_progress_job_path)

    talk_job = encode_video.load_talk_config(in_progress_job_path)
    if not talk_job:
        print('Failed to load job: {0}'.format(in_progress_job_path))
        return

    # Setup talk job
    config, talk = encode_video.setup(local_config, talk_job)

    # Run encoding
    print('Starting encoding: {0}'.format(talk_job['schedule_id']))
    output_files = encode_video.process_remote_talk(config, talk)

    if output_files:
        # Move job to complete
        complete_dir = local_config['dirs']['complete']
        try:
            os.makedirs(complete_dir)
        except OSError:
            pass
        complete_job_path = os.path.join(complete_dir, talk_job_filename)
        shutil.move(in_progress_job_path, complete_job_path)

        print('Finished encoding: {0}'.format(talk_job['schedule_id']))
    else:
        # Move job back to queue
        shutil.move(in_progress_job_path, queue_job_path)
        print('Encoding FAILED: {0}'.format(talk_job['schedule_id']))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
