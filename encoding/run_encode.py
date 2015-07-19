#!/usr/bin/python

import atexit
import json
import os
import re
import shutil
import subprocess
import sys

import moviepy.editor as mpy


BASE_CONFIG_FILENAME = 'test/config.json'




def do_rsync(from_file, to_file):
    subprocess.call(["rsync", "-u", from_file, to_file])
    print "Do something like rsync from %r to %r" % (from_file, to_file)
    flush_output()


def setup(talk_config_filename):
    config = {}

    with open(talk_config_filename, 'r') as f:
        try:
            config['talk'] = json.load(f)
            talk_config = config['talk']
        except Exception as e: # dunno
            print "Error loading talk config:"
            print e
            sys.exit(1)

    # setup directory structure:
    # test/
    #   queue/
    #       39.json
    #   output/
    #       Sprinting_for_Beginners-Tennessee_Leeuwenburg.mp4
    #       Sprinting_for_Beginners-Tennessee_Leeuwenburg.ogv
    #       Sprinting_for_Beginners-Tennessee_Leeuwenburg.ogg
    
    with open(BASE_CONFIG_FILENAME, 'r') as f:
        try:
            base = json.load(f)
            print base
        except Exception: # dunno
            print "Error loading base config:"
            print e
            sys.exit(1)


    try:
        os.makedirs('queue/output')
    except OSError:
        pass

    job_folder = 'queue/output'
    return base, talk_config

def create_text_overlay_clip(background_filename, text, duration):
    # Set up the background image
    # base_clip = mpy.ImageClip(background_filename)
    base_clip = mpy.ColorClip((720,576), (255,0,0)) # in lieu of real one
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
    print("Setting up title image")
    text = "{0}\n\n{1}".format(title, presenters)
    return create_text_overlay_clip(background_filename, text, duration)


def create_credits_clip(background_filename, text, duration):
    print("Creating credits image")
    return create_text_overlay_clip(background_filename, text, duration)


def create_talk_clip(files=[], start=0, end=None):
    print("Creating main talk")
    clip_list = []

    print files[-1]
    #if end and end >= 0:
        #last_clip = mpy.VideoFileClip(files.pop())
        #last_clip = last_clip.subclip(0, end)

    for dv in files:
        clip = mpy.VideoFileClip(dv)
        clip_list.append(clip)

    #clip_list.append(last_clip)
    print clip_list

    full_clip = mpy.concatenate(clip_list)
    #full_clip = full_clip.set_start(start, change_end=False)
    full_clip.fps = 24
    return full_clip
    
    
def encode_file(video, base_filename, extension):
    print "Encoding {0}: ".format(extension),
    filename = "{0}.{1}".format(base_filename, extension)

    if extension in ['mp4', 'ogv']:
        video.write_videofile(filename)

    elif extension in ['ogg']:
        video.audio.to_audiofile(filename)


def process_talk(config, talk):

    #server = config["server"]
    base_folder = config["base_dir"]
    title = talk['title']
    presenters = talk['presenters']

    # Create intro (title) slide
    title_bg = config['title_background']
    title_clip = create_title_clip(
        background_filename=title_bg,
        title=title,
        presenters=presenters,
        duration=2,
    )

    # Merge all files from the talk proper
    print talk['file_list']
    talk_clip = create_talk_clip(
        files=talk['file_list'],
        start=talk['in_time'],
        end=talk['out_time'],
    )

    # Create credits slide
    credits_bg = config['credits_background']
    credits_clip = create_credits_clip(
        background_filename=credits_bg,
        text=talk['credits'],
        duration=2
    )

    # Merge all clips together and encode
    video = mpy.concatenate([title_clip, talk_clip, credits_clip])

    filename = "{0} - {1}".format(title, presenters)
    output_path = os.path.join(config['base_dir'], 'output', filename)

    for ext in ['mp4', 'ogv', 'ogg']:
        encode_file(video, output_path, ext)

    
    #header("Rsyncing files down")
    #do_rsync(server + ":" + os.path.join(base_folder, talk_file), talk_local_file)
    #do_rsync(server + ":" + os.path.join(base_folder, intro_file), intro_local_file)
    #do_rsync(server + ":" + os.path.join(base_folder, credits_file), credits_local_file)

    #py_folder = os.path.dirname(os.path.realpath(__file__))

    #credits_image = os.path.join(job_folder, schedule_id + "-credits-img.png")
    #subprocess.call([os.path.join(py_folder, "gen_image.pl"), credits_image, credits_text])

    #base_output_file = os.path.join(job_folder, schedule_id + "-out.")

    """
    from multiprocessing import Process
    processes = []
    for ext in EXTENSIONS:
        p = Process(target=do_encode, args=(ext,))
        p.start()
        processes.append((ext, p))

    for ext, p in processes:
        p.join()
        if p.exitcode != 0:
            print "Failed to complete encoding of %s with code %d" % (ext, p.exitcode)
            exit(p.exitcode)
    """

    #for ext in EXTENSIONS:
        #do_rsync(base_output_file + ext, server + ":" + os.path.join(base_folder, schedule_id + "-out." + ext))


if __name__ == '__main__':

    if len(sys.argv) > 1:
        talk_config_filename = sys.argv[1]
    else:
        print "Usage: enter a json file from the todo queue."
        sys.exit(1)
        
    config, talk = setup(talk_config_filename)
    process_talk(config, talk)
