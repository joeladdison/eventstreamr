#!/usr/bin/env python

import os
import signal
import logging
from flask import Flask, request, jsonify, json, make_response
from flask.ext.cors import CORS

from lib import devices, config

app = Flask(__name__, static_url_path='')

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


@app.route("/settings/<station_id>", methods=['POST'])
def update_settings(station_id):
    global state
    if station_id == state.station_config['station_id']:
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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)
