#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib2
import json
import datetime
import os
import subprocess
import sys

from lib import schedule, ui
from lib.schedule import SCHEDULE_URL, JSON_FORMAT, DV_FORMAT, DV_MATCH_WINDOW

DV_FRAME_RATE = 25


def setup(config):
    schedule_url = config.get('schedule_url', SCHEDULE_URL)
    schedule_file = config['schedule']
    recording_dir = config['dirs']['recordings']
    queue_dir = config['dirs']['queue']

    try:
        os.makedirs(queue_dir)
    except OSError:
        pass

    if not os.path.exists(schedule_file):
        with open(schedule_file, "w") as f:
            f.write(urllib2.urlopen(schedule_url).read())

    # Load the schedule
    talks = schedule.get_schedule(schedule_file, JSON_FORMAT)

    # Look for DV files that match the times from the schedule
    for talk in talks:
        schedule.link_dv_files(
            talk, recording_dir, DV_MATCH_WINDOW, DV_FORMAT, True)
    jobs = {t['schedule_id']: t for t in talks if t['playlist']}

    return jobs, queue_dir, recording_dir


def run_interface(jobs, queue_dir, recording_dir):
    available_jobs = [t for t, v in jobs.items() if v['playlist']]
    if not available_jobs:
        print "No available jobs."
        return
    print "Available jobs:", available_jobs
    n = ui.prompt_for_number("Select a job")

    while n:
        talk = jobs[n]

        dv_files = [os.path.join(recording_dir, dv_file['filepath'], dv_file['filename'])
                    for dv_file in talk['playlist']]

        with open(os.devnull, 'wb') as DEVNULL:
            subprocess.Popen(['vlc'] + dv_files, stderr=DEVNULL)
            pass

        # Show some basic information about the talk
        print
        print "Title:", talk['title']
        if 'presenters' in talk:
            print "Presenter:", talk['presenters']
        else:
            print "NO PRESENTER FOUND"

        print "Files:"
        for i, dv_file in enumerate(dv_files):
            print i, dv_file

        print

        # Prompt the operator for required details
        start_file = ui.prompt_for_number("Start file", 0)
        start_offset = None
        while start_offset is None:
            start_offset = ui.prompt("Start time offset", "00:00")

        end_file = ui.prompt_for_number("End file", len(talk['playlist'])-1)
        end_offset = None
        while end_offset is None:
            end_offset = ui.prompt("End time offset [mm:ss]")

        # some error checking with the offsets would be nice
        # also auto-calculating

        credits = ui.prompt("Credits", "")

        # Calculate the time offsets from operator input
        # something involving DV_FRAME_RATE here
        file_list = dv_files[start_file:end_file+1]

        # Add a json file for this talk to the queue dir
        print "Creating and queuing job " + str(talk['schedule_id'])
        job_file = os.path.join(queue_dir, str(talk['schedule_id'])) + '.json'

        todo = {}
        todo["schedule_id"] = talk["schedule_id"]
        todo["title"] = talk.get("title", "")
        todo["presenters"] = talk.get("presenters", "")
        todo["file_list"] = file_list
        todo["in_time"] = "00:{0}.00".format(start_offset)
        todo["out_time"] = "00:{0}.00".format(end_offset)
        todo["credits"] = credits

        with open(job_file, 'w') as f:
            json.dump(
                todo, f, sort_keys=True, indent=4, separators=(',', ': '))

        # And start all over again!
        available_jobs = [t for t, v in jobs.items() if v['playlist']]
        if not available_jobs:
            print "No available jobs."
            return
        print
        print "----------"
        print "Available jobs:", available_jobs
        n = ui.prompt_for_number("Select a job")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        config_filename = sys.argv[1]
    else:
        config_filename = 'config.json'

    config = schedule.open_json(config_filename)
    jobs, queue_dir, recording_dir = setup(config)
    run_interface(jobs, queue_dir, recording_dir)
