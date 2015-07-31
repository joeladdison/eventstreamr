#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import fnmatch
import time
import json

from lib import schedule
from lib.youtube import *

config_file = 'config.json'
with open(config_file, 'r') as f:
    config_data = json.load(f)

base_dir = config_data['base_dir']
queue_todo_dir = os.path.join(base_dir, 'completed')
queue_wip_dir = os.path.join(base_dir, 'uploading')
queue_done_dir = os.path.join(base_dir, 'uploaded')
youtube_log_file = os.path.join(base_dir, 'youtube_uploads.log')
schedule_file = os.path.join(base_dir, config_data['schedule'])

client_id = ''
client_secret = ''
category_id = 28
youtube = get_authenticated_youtube_service('youtube_upload.json', client_id, client_secret)

loaded_schedule = schedule.load_schedule(schedule_file, schedule.SCHEDULE_URL)

talks = schedule.get_schedule(loaded_schedule, schedule.JSON_DATE_FORMAT)
talks = {t['schedule_id']: t for t in talks}


def move_job(src_dir, dst_dir, jobname):
    files = os.listdir(src_dir)
    for filename in files:
        if fnmatch.fnmatch(filename, jobname + '.[lm][op][g4]'):
            src = os.path.join(src_dir, filename)
            dst = os.path.join(dst_dir, filename)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)
            os.rename(src, dst)


while True:
    files = os.listdir(queue_todo_dir)
    for filename in files:
        if fnmatch.fnmatch(filename, '*.mp4'):
            job = filename[:-4]
            print "Starting job " + job
            move_job(queue_todo_dir, queue_wip_dir, job)

            upload_file = os.path.join(queue_wip_dir, filename)
            upload_video_info = {
                'snippet': {
                    'title': talks[int(job)]['title'],
                    'description': talks[int(job)]['abstract'] + ' by ' + talks[int(job)]['presenters'],
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': 'private'
                }
            }
            upload = resumable_youtube_upload(youtube, os.path.join(queue_wip_dir, filename), upload_video_info)
            with open(youtube_log_file, 'a') as youtube_log:
                youtube_log.write("\t".join([job, 'http://www.youtube.com/watch?v=' + upload['id'], upload['snippet']['title']]) + "\n")
            print "Finished job " + job
            move_job(queue_wip_dir, queue_done_dir, job)
            break
    else:
        print "Nothing to do, sleeping"
        time.sleep(10)
