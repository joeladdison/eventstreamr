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
    if background_filename:
        base_clip = mpy.ImageClip(background_filename)
    else:
        # in lieu of real one
        base_clip = mpy.ColorClip((720, 576), (255, 0, 0))
    base_clip = base_clip.set_duration(duration)

    # Set up the text itself
    text_clip = mpy.TextClip(text, font="FreeSans", fontsize=40)
    text_clip = text_clip.set_pos('center')
    text_clip = text_clip.set_duration(duration)

    # Overlay the text onto the background
    full_clip = mpy.CompositeVideoClip([base_clip, text_clip])
    full_clip.fps = 24
    return full_clip


def create_title_clip(background_filename, title, presenters, duration):
    print("Setting up title slide")
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
    full_clip.fps = 24
    return full_clip


def encode_file(video, base_filename, extension):
    filename = "{0}.{1}".format(base_filename, extension)

    if extension in ('mp4', 'ogv'):
        video.write_videofile(filename)
        return filename
    elif extension in ('ogg'):
        video.audio.to_audiofile(filename)
        return filename

    return None


def process_talk(config, talk):
    # Create intro (title) slide
    title = talk['title']
    presenters = talk['presenters']
    title_bg = config['backgrounds']['title']
    title_clip = create_title_clip(
        background_filename=title_bg,
        title=title,
        presenters=presenters,
        duration=2,
    )

    # Merge all files from the talk proper
    talk_clip = create_talk_clip(
        files=talk['file_list'],
        start=talk['in_time'],
        end=talk['out_time'],
    )

    # Create credits slide
    credits_bg = config['backgrounds']['credits']
    credits_clip = create_credits_clip(
        background_filename=credits_bg,
        text=talk['credits'],
        duration=2
    )

    # Merge all clips together and encode
    video = mpy.concatenate([title_clip, talk_clip, credits_clip])

    filename = "{0} - {1}".format(title, presenters)
    output_path = os.path.join(config['dirs']['output'], filename)

    generated_files = []
    for ext in ('mp4', 'ogv', 'ogg'):
        f = encode_file(video, output_path, ext)
        if f:
            generated_files.append(f)

    return generated_files


def process_remote_talk(config, talk):
    # Copy talk to local directory
    local_files = []
    for f in talk['file_list']:
        local_path = os.path.join(config['dirs']['recordings'], f)
        remote_path = os.path.join(config['dirs']['remote_recordings'], f)
        if not os.path.exists(local_path):
            shutil.copy(remote_path, local_path)
        local_files.append(local_path)

    # Use the new file list
    talk['original_file_list'] = talk['file_list']
    talk['file_list'] = local_files

    # Process the talk
    generated_files = process_talk(config, talk)

    # Copy the talk to the final location
    if config['dirs']['output'] != config['dirs']['remote_output']:
        for f in generated_files:
            filename = f.split(config['dirs']['output'])[1]
            remote_path = os.path.join(
                config['dirs']['remote_output'], filename)
            shutil.copy(f, remote_path)


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
