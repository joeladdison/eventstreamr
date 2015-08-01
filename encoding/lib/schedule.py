import os
import urllib2
import json
import datetime


SCHEDULE_URL = 'http://2015.pycon-au.org/schedule/programme/json'
JSON_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DV_FORMAT = "%Y-%m-%d_%H-%M-%S"
DV_MATCH_WINDOW = datetime.timedelta(minutes=10)


def dv_to_datetime(filename, filename_format):
    """ Return a datetime object if filename is <timestamp>.dv, else None """
    if filename[-3:] == ".dv":
        try:
            time = datetime.datetime.strptime(filename[:-3], filename_format)
        except ValueError:
            time = None
    else:
        time = None
    return time


def open_json(filename):
    if "://" in filename:
        json_data = urllib2.urlopen(filename)
    else:
        json_data = open(filename)
    data = json.load(json_data)
    json_data.close()
    return data


def load_schedule(schedule_file, schedule_url):
    if not os.path.exists(schedule_file):
        # Download from url
        with open(schedule_file, "w") as f:
            f.write(urllib2.urlopen(schedule_url).read())

    with open(schedule_file, "r") as f:
        return json.load(f)


def get_schedule(schedule, json_date_format=JSON_DATE_FORMAT):
    # Read the schedule, removing spaces in room names
    schedule_data = {k.replace(" ", "").lower(): v for k, v in schedule.items()}
    fields = ["schedule_id", "presenters", "title", "abstract", "start", "end"]
    talks = []
    for schedule_room, schedule_room_data in schedule_data.iteritems():
        for schedule_talk in schedule_room_data:
            copyfields = list(fields)
            if "break" in schedule_talk or "heading" in schedule_talk:
                continue
            if "presenters" not in schedule_talk:
                copyfields.remove("presenters")

            talk = {field: schedule_talk[field] for field in copyfields}
            talk['room'] = schedule_room.lower()
            talk['start'] = datetime.datetime.strptime(
                schedule_talk['start'], json_date_format)
            talk['end'] = datetime.datetime.strptime(
                schedule_talk['end'], json_date_format)
            talk['date'] = talk['start'].strftime("%Y%m%d")
            talks.append(talk)
    return talks


def link_dv_files(talk, recording_root, dv_match_window, dv_format, all=False):
    talk['playlist'] = []
    room = talk['room'].lower()
    talk_path = os.path.join(recording_root, room, talk['date'])
    if os.path.exists(talk_path):
        for filename in os.listdir(talk_path):
            time = dv_to_datetime(filename, dv_format)
            start_window = talk['start'] - dv_match_window
            end_window = talk['end'] + dv_match_window
            if all or (time and start_window <= time <= end_window):
                dv_file = {
                    'filename': filename,
                    'filepath': os.path.join(talk['room'], talk['date'])
                }
                talk['playlist'].append(dv_file)
            talk['playlist'].sort()


def load_all_talks(schedule, recording_dir):
    # Load the schedule
    talks = get_schedule(schedule, JSON_DATE_FORMAT)

    # Look for DV files that match the times from the schedule
    for talk in talks:
        link_dv_files(talk, recording_dir, DV_MATCH_WINDOW, DV_FORMAT, False)

    jobs = {t['schedule_id']: t for t in talks}
    return jobs


def load_room_talks(schedule, recording_dir, room):
    talks = load_all_talks(schedule, recording_dir)
    room_talks = {t: v for t, v in talks.items() if v['room'] == room}
    return room_talks


def available_rooms(schedule):
    # Read the schedule, removing spaces in room names
    return {k.replace(" ", "").lower(): k for k in schedule}
