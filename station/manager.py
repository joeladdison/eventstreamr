#!/usr/bin/env python

import os
import sys
import datetime
import time
import logging

from lib import config, roles


LOCAL_CONFIG_PATH = 'settings.json'
STATION_CONFIG_PATH = 'station.json'
COMMANDS_CONFIG_PATH = 'commands.json'


# Setup logging
logging.basicConfig()

logger = logging.getLogger('eventstreamr')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))


def main():
    state = config.State.from_files(
        LOCAL_CONFIG_PATH, STATION_CONFIG_PATH, COMMANDS_CONFIG_PATH)

    if state.station_config['run'] == 2:
        state.station_config['run'] = 1

    config.register_station(state)

    # Log when started
    if state.station_config['run']:
        logger.info("Manager started, starting devices")
    else:
        logger.info("Manager started, configuration set to not start devices.")

    state.station_config.setdefault('device_control', {})
    state.station_config['device_control'].setdefault('record', {})
    state.station_config['device_control']['record']['recordpath'] = 0

    run_daemon(state)


def run_daemon(state):
    while state.running:
        if state.station_config['run'] == 2:
            logger.info('Restart triggered')
            state.dvswitch['check'] = 1

        roles.devmon(state)

        for role in state.station_config['roles']:
            roles.ROLE_FUNCTIONS[role](state)

        # 2 is the restart all processes trigger
        if state.station_config['run'] == 2:
            state.station_config['run'] = 1

        # if not state.dvswitch['running'] and state.dvswitch['check']:
            # TODO: Check for dvswitch running
            # if utils.port(state.station_config['mixer']['host'], state.station_config['mixer']['port']):
            #     logger.info('DVswitch found running')
            #     state.dvswitch['running'] = True
            #     state.dvswitch['check'] = False

        # Update date if it has changed
        if state.date != datetime.date.today():
            state.date = datetime.date.today()
            state.station_config['device_control']['record']['recordpath'] = 0
            state.station_config['device_control']['record']['run'] = 2

        time.sleep(1)


def sig_exit():
    logger.info("manager exiting...")
    # TODO: Kill daemons
    pass


def self_update():
    logger.info("Performing self update")
    logger.debug("Update host: ../../baseimage/update-host.sh")
    os.system('../../baseimage/update-host.sh')

    sig_exit()
    logger.debug(
        "Restart manager: {0} {1}".format(__file__, ' '.join(sys.argv)))
    logger.shutdown()
    os.execv(__file__, sys.argv)
    raise RuntimeError()


if __name__ == '__main__':
    main()
