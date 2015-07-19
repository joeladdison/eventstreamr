#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib2
import json
import datetime
import os
import subprocess
import sys

from lib import duration, job, schedule, ui


SCHEDULE_URL = 'http://2015.pycon-au.org/schedule/programme/json'
JSON_FORMAT = "%Y-%m-%d %H:%M:%S"
DV_FORMAT = "%Y-%m-%d_%H-%M-%S"
DV_MATCH_WINDOW = datetime.timedelta(minutes=10)
DV_FRAME_RATE = 25


def setup(config_filename):
    config = schedule.open_json(config_filename)

    base_dir = os.path.abspath(config['base_dir'])
    schedule_file = os.path.join(base_dir, config['schedule'])
    recording_dir = os.path.join(base_dir, config['recording_dir'])
    queue_todo_dir = os.path.join(base_dir, 'queue', 'todo')

    try:
        os.makedirs(queue_todo_dir)
    except OSError:
        pass

    if not os.path.exists(schedule_file):
        with open(schedule_file, "w") as f:
            f.write(urllib2.urlopen(SCHEDULE_URL).read())

    # Load the schedule
    talks = schedule.get_schedule(schedule_file, JSON_FORMAT)

    # Look for DV files that match the times from the schedule
    for talk in talks:
        schedule.link_dv_files(talk, recording_dir, DV_MATCH_WINDOW, DV_FORMAT)
    jobs = {t['schedule_id']: t for t in talks if t['playlist']}

    return jobs, queue_todo_dir


def run_interface(jobs, todo_dir):
    available_jobs = [t for t,v in jobs.items() if v['playlist']]
    if not available_jobs:
        print "No available jobs."
        return
    print "Available jobs:", available_jobs
    n = ui.prompt_for_number("Select a job")

    while n:
        talk = jobs[n]

        dv_files = [os.path.join(dv_file['filepath'], dv_file['filename'])
                    for dv_file in talk['playlist']]

        #with open(os.devnull, 'wb') as DEVNULL:
            #subprocess.Popen(['vlc'] + dv_files, stderr=DEVNULL)
            #pass

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

        # our users always type sensible things...right
        start_file = ui.prompt_for_number("Start file", 0)
        start_offset = None
        while start_offset is None:
            start_offset = ui.prompt_for_time("Start time offset", 0)
        end_file = ui.prompt_for_number("End file", len(talk['playlist'])-1)
        end_offset = None
        while end_offset is None:
            end_offset = ui.prompt_for_time("End time offset")

        credits = None
        while credits is None:
            credits = ui.prompt("Credits")

        intro_file = ui.prompt("Intro File", "intro.dv")

        # this sets up the cut_list which will be used later
        talk['cut_list'] = talk['playlist'][start_file:end_file+1]
        talk['cut_list'][0]['in'] = start_offset
        talk['cut_list'][-1]['out'] = end_offset

        print "Creating and queuing job " + str(talk['schedule_id'])
        job_file = os.path.join(todo_dir, str(talk['schedule_id']))

        talk["filename"] = str(talk['schedule_id']) + "-main.dv"
        talk["intro"] = {"title": talk['title'],
                         "filename": intro_file}
        if "presenters" in talk:
            talk['intro']['presenters'] = talk['presenters']
        else:
            if " by " in talk['title']:
                (talk['intro']['title'], talk['intro']['presenters']) = talk['title'].split(" by ")
            else:
                talk['intro']['presenters'] = ""
        talk["credits"] = {"text": credits,
                           "filename": "credits.dv"
                           }

        job.create_json(talk, job_file + ".json", DV_FRAME_RATE)

        available_jobs = [t for t,v in jobs.items() if v['playlist']]
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
        config_filename = 'test/config.json'
        
    jobs, todo_dir = setup(config_filename)
    run_interface(jobs, todo_dir)
