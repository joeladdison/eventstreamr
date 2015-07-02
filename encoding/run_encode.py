#!/usr/bin/python

from sys import argv, stderr, stdout
from json import loads
import os
from os.path import join
import re


def f():
    stderr.flush()
    stdout.flush()


def header(title):
    print "#" * 120
    print "#" + (" " * 118) + "#"
    print "#" + title.center(118) + "#"
    print "#" + (" " * 118) + "#"
    print "#" * 120
    f()


def call(cmd, *args, **kwargs):
    from subprocess import call
    print "Command: %r" % (cmd, )
    f()
    kwargs.update(stdout=stdout, stderr=stderr, cwd=job_folder)
    r = call(cmd, *args, **kwargs)
    if r != 0:
        print "Failed to call %r" % cmd
        exit(r)
    f()


def do_rsync(from_file, to_file):
    call(["rsync", "-u", from_file, to_file])
    print "Do something like rsync from %r to %r" % (from_file, to_file)
    f()

# Install perlmagick & xvfb


melt_base = ["xvfb-run", "-a", "melt", "-silent"]

if __name__ == "__main__":

    json = loads(argv[-1])

    extensions = json["extensions"]

    server = json["server"]
    base_folder = json["base-folder"]
    schedule_id = str(json["schedule_id"])

    job_folder = os.path.abspath(json["local_save"] + " - " + schedule_id)
    if not os.path.exists(job_folder):
        os.mkdir(job_folder)

    import atexit
    import shutil
    atexit.register(shutil.rmtree, job_folder)

    extensions = json["extensions"]

    server = json["server"]
    base_folder = json["base-folder"]
    schedule_id = str(json["schedule_id"])

    talk_file = json["main"]["filename"]
    talk_local_file = join(job_folder, talk_file)

    intro_file = json["intro"]["filename"]
    intro_local_file = join(job_folder, "..", intro_file)
    title = json["intro"]["title"]
    presenters = json["intro"]["presenters"]
    date_given = re.match(".*/(20[0-9][0-9]-[0-9][0-9]-[0-9][0-9])_.*[.]dv", json["file_list"][0])
    date_given = date_given and date_given.group(1) or ""

    credits_file = json["credits"]["filename"]
    credits_local_file = join(job_folder, "..", credits_file)
    credits_text = json["credits"]["text"]

    header("Rsyncing files down")
    do_rsync(server + ":" + join(base_folder, talk_file), talk_local_file)
    do_rsync(server + ":" + join(base_folder, intro_file), intro_local_file)
    do_rsync(server + ":" + join(base_folder, credits_file), credits_local_file)

    py_folder = os.path.dirname(os.path.realpath(__file__))

    header("Creating Title Image")
    intro_image = join(job_folder, schedule_id + "-intro-img.png")
    call([join(py_folder, "../../encoding/gen_image.pl"), intro_image, title + "\n" + presenters])

    header("Creating Credits Image")
    credits_image = join(job_folder, schedule_id + "-credits-img.png")
    call([join(py_folder, "../../encoding/gen_image.pl"), credits_image, credits_text])

    header("Combining Title Image and Title Background")
    intro_watermarked = join(job_folder, schedule_id + "-intro.dv")
    call(melt_base + [intro_local_file, '-filter', 'watermark:' + intro_image, 'in=0', 'out=50',
                    'composite.progressive=1', 'producer.align=centre', 'composite.valign=c', 'composite.halign=c',
                    '-consumer', 'avformat:' + intro_watermarked])

    header("Combining Credits Image and Credits Background")
    credits_watermarked = join(job_folder, schedule_id + "-credits.dv")
    call(melt_base + [credits_local_file, '-filter', 'watermark:' + credits_image,
                    'composite.progressive=1', 'producer.align=centre', 'composite.valign=c', 'composite.halign=c',
                    '-consumer', 'avformat:' + credits_watermarked])

    base_output_file = join(job_folder, schedule_id + "-out.")

    def do_encode(extension):
        header("Creating a file. Ext: %s" % extension)

        if extension == "mp4":
            args = melt_base + [intro_watermarked, talk_local_file, credits_watermarked, '-consumer',
                    'avformat:' + base_output_file + extension, "progressive=1", "vcodec=libx264"]
        elif extension == "ogv":
            args = melt_base + [intro_watermarked, talk_local_file, credits_watermarked, '-consumer',
                    'avformat:' + base_output_file + extension, "progress=1", "threads=0", "vb=1000k", "quality=good",
                    "deadline=good", "deinterlace=1", "deinterlace_method=yadif"]
        elif extension == "ogg":
            args = ["ffmpeg", "-i", talk_local_file, "-vn", "-acodec", "libvorbis", "-aq", "6", "-metadata",
                    "TITLE=%s" % title, "-metadata", "SPEAKER=%s" % presenters, "-metadata", "DATE=%s" % date_given, "-metadata",
                    "EVENT=PyconAu", base_output_file + extension]
        else:
            args = melt_base + [intro_watermarked, talk_local_file, credits_watermarked, '-consumer',
                    "avformat:" +  base_output_file + extension]
        call(args)

    from multiprocessing import Process
    processes = []
    for ext in extensions:
        p = Process(target=do_encode, args=(ext,))
        p.start()
        processes.append((ext, p))

    for ext, p in processes:
        p.join()
        if p.exitcode != 0:
            print "Failed to complete encoding of %s with code %d" % (ext, p.exitcode)
            exit(p.exitcode)

    for ext in extensions:
        do_rsync(base_output_file + ext, server + ":" + join(base_folder, schedule_id + "-out." + ext))
