#!/usr/bin/python

__author__ = 'lee'

from sys import argv, stderr, stdout
from json import loads
import os
from os.path import join
from lib.shellquote import shellquote

BYTES_PER_FRAME = 144000


def header(title):
    print "#" * 120
    print "#" + (" " * 118) + "#"
    print "#" + title.center(118) + "#"
    print "#" + (" " * 118) + "#"
    print "#" * 120


def call(*args, **kwargs):
    from subprocess import call
    kwargs.update(stdout=stdout, stderr=stderr, cwd=job_folder)
    r = call(*args, **kwargs)
    if r != 0:
        exit(r)


json = loads(argv[-1])

job_folder = os.path.abspath(json["base-folder"])
in_time = int(json.get("in_time", "0"))
out_time = int(json.get("out_time", "0"))
out_file = join(job_folder, json["main"]["filename"])
file_list = json["file_list"]
schedule_id = json["schedule_id"]

cmd = [["dd", "if=%s" % file_list[0],"bs=%d" % BYTES_PER_FRAME, "skip=%d" % in_time]]
if len(file_list) > 2:
    cmd.append(["cat"] + file_list[1:-1])
if out_time != 0:
    if len(file_list) == 1:
        cmd[-1].append("count=%d" % (out_time - in_time))
    else:
        cmd.append(["dd", "if=%s" % file_list[-1], "bs=%d" % BYTES_PER_FRAME, "count=%d" % out_time])

cmd = "(%s)>%s" % (
    '; '.join(" ".join(shellquote(c) for c in cc) for cc in cmd),
    shellquote(out_file))

call(cmd, shell=True)
