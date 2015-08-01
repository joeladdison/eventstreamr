#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys
import shutil

import moviepy.editor as mpy


BASE_CONFIG_FILENAME = 'config.json'


def load_config():
    with open(BASE_CONFIG_FILENAME, 'r') as f:
        try:
            base_config = json.load(f)
        except Exception as e:  # dunno
            print "Error loading base config:"
            print e
            sys.exit(1)

    return base_config


def load_talk_config(talk_config_json):
    talk_config = None

    try:
        talk_config = json.loads(talk_config_json)
    except Exception as e:  # dunno
        print "Error loading talk config:"
        print e

    return talk_config


def setup(base_config, talk_config_json):
    if base_config is None:
        base_config = load_config()

    talk_config = load_talk_config(talk_config_json)

    try:
        os.makedirs(os.path.join(base_config['dirs']['output']))
    except OSError:
        pass

    return base_config, talk_config


def create_text_overlay_clip(background_filename, text, duration):
    # Set up the background image
    if background_filename and os.path.exists(background_filename):
        base_clip = mpy.ImageClip(str(background_filename))
    else:
        # in lieu of real one
        base_clip = mpy.ColorClip((720, 576), (255, 0, 0))
    base_clip = base_clip.set_duration(duration)

    clips = [base_clip]

    if text:
        # Set up the text itself
        filename = '/tmp/text_clip.txt'
        with open(filename, 'w') as f:
            f.write(text)

        text_clip = mpy.TextClip(filename=filename, font="FreeSans", fontsize=40, color='white', print_cmd=True)
        text_clip = text_clip.set_pos(('center', 30))
        text_clip = text_clip.set_duration(duration)
        clips.append(text_clip)

    # Overlay the text onto the background
    full_clip = mpy.CompositeVideoClip(clips)
    full_clip.fps = 25
    return full_clip


def create_title_clip(background_filename, title, presenters, duration):
    text = "{0}\n\n{1}".format(title, presenters)
    return create_text_overlay_clip(background_filename, text, duration)


def create_credits_clip(background_filename, text, duration):
    print("Setting up credits slide")
    return create_text_overlay_clip(background_filename, text, duration)


def create_talk_clip(files=(), start=0, end=None):
    print("Setting up main talk")
    clip_list = []

    if end and end >= 0:
        last_clip = mpy.VideoFileClip(files.pop())
        last_clip = last_clip.subclip(0, end)

    for dv in files:
        clip = mpy.VideoFileClip(dv)
        clip_list.append(clip)

    clip_list.append(last_clip)

    full_clip = mpy.concatenate(clip_list)
    full_clip = full_clip.subclip(start)
    #full_clip.fps = 24
    return full_clip


def encode_file(video, base_filename, extension):
    filename = "{0}.{1}".format(base_filename, extension)
    print('Creating video: {0}'.format(filename))

    if extension in ('mp4', 'ogv'):
        video.write_videofile(filename, preset='medium', ffmpeg_params=['-aspect', '16:9'])  #, '-qp', '0', '-crf', '0'])
        return filename
    elif extension in ('ogg'):
        video.audio.to_audiofile(filename)
        return filename

    return None


def process_talk(config, talk):
    talk_id = talk['schedule_id']
    
    # Create intro (title) slide
    print('[{0}] Creating intro (title) slide'.format(talk_id))
    title = talk['title']
    presenters = talk['presenters']
    title_bg = config['backgrounds']['title']
    title_clip = create_title_clip(
        background_filename=title_bg,
        title=title,
        presenters=presenters,
        duration=10,
    )

    # Merge all files from the talk proper
    print('[{0}] Merge talk clips'.format(talk_id))
    talk_clip = create_talk_clip(
        files=talk['file_list'],
        start=talk['in_time'],
        end=talk['out_time'],
    )

    # Create credits slide
    print('[{0}] Creating credits slide'.format(talk_id))
    credits_bg = config['backgrounds']['credits']
    credits_clip = create_credits_clip(
        background_filename=credits_bg,
        text=talk['credits'],
        duration=10
    )

    # Merge all clips together and encode
    print('[{0}] Merging clips'.format(talk_id))
    video = mpy.concatenate([title_clip, talk_clip, credits_clip])
    print("VIDEO SIZE:", video.size, video.w, video.h)
    if config.get('output_filename', ''):
        filename = config['output_filename'].format(**talk)
    else:
        filename = "{0} - {1}".format(title, presenters)
    output_path = os.path.join(config['dirs']['output'], filename)

    print('[{0}] Starting encoding'.format(talk_id))
    generated_files = []
    extensions = config.get('output_extensions', ('mp4', 'ogv', 'ogg'))
    for ext in extensions:
        f = encode_file(video, output_path, ext)
        if f:
            generated_files.append(f)

    print('[{0}] Finished encoding'.format(talk_id))
    return generated_files


def process_remote_talk(config, talk):
    talk_id = talk['schedule_id']
    print('Processing talk: {0}'.format(talk['schedule_id']))
    # Copy talk to local directory
    local_files = []
    for f in talk['file_list']:
        file_path = os.path.join(f['filepath'], f['filename'])
        local_path = os.path.join(config['dirs']['recordings'], file_path)
        remote_path = os.path.join(config['dirs']['remote_recordings'], file_path)

        local_recording = os.path.join(config['dirs']['recordings'], f['filepath'])
        if not os.path.exists(local_recording):
            try:
                os.makedirs(local_recording)
            except OSError:
                print('Failed to make local recording dir: {0}'.format(local_recording))
                return

        if not os.path.exists(local_path):
            print('[{0}] Copying file: {1} to {2}'.format(talk_id, remote_path, local_path))
            shutil.copy(remote_path, local_path)
            print('[{0}] Finished copying file: {1} to {2}'.format(talk_id, remote_path, local_path))

        local_files.append(local_path)

    # Use the new file list
    talk['original_file_list'] = talk['file_list']
    talk['file_list'] = local_files

    try:
        if not os.path.exists(config['dirs']['output']):
            print('[{0}] Creating directory: {1}'.format(talk_id, config['dirs']['output']))
            os.makedirs(config['dirs']['output'])
        if not os.path.exists(config['dirs']['remote_output']):
            print('[{0}] Creating directory: {1}'.format(talk_id, config['dirs']['remote_output']))
            os.makedirs(config['dirs']['remote_output'])
    except OSError:
        print('Failed to create output directories')
        return

    # Process the talk
    generated_files = process_talk(config, talk)

    # Copy the talk to the final location
    if config['dirs']['output'] != config['dirs']['remote_output']:
        print('[{0}] Copying output files'.format(talk_id))
        for f in generated_files:
            filename = f.split(config['dirs']['output'])[1]
            remote_path = os.path.join(
                config['dirs']['remote_output'], filename)
            print('[{0}] Copying file: {1} to {2}'.format(talk_id, f, remote_path))
            shutil.copy(f, remote_path)

    print('[{0}] Completed processing encoding job'.format(talk_id))


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Encode some videos.")
    parser.add_argument("-s", "--string", help="talk config as a json string")
    # parser.add_argument("-f", "--file", help="talk config as a json file")
    args = parser.parse_args()

    if len(sys.argv) > 1:
        talk_config_json = args.string
    else:
        print "Usage: enter a json string describing a talk from the todo queue"
        sys.exit(1)

    config, talk = setup(None, talk_config_json)
    if config is None or talk is None:
        sys.exit(1)
    process_talk(config, talk)
