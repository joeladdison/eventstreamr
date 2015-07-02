import datetime
import subprocess


def get_duration(filename):
    # from matt, untested since i don't have test files
    # not quite sure what this returns/outputs
    cmd = ['exiftool', '-duration', filename]
    p = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in p.stdout:
        duration = line.split()[2]
    return str2delta(duration)


def str2delta(raw):
    formats = ["%H:%M:%S", "%H:%M:%S.%f", "%M:%S", "%M:%S.%f", "%S", "%S.%f"]
    time = None
    zero = datetime.datetime.strptime("", "")
    for f in formats:
        try:
            time = datetime.datetime.strptime(raw, f) - zero
            break
        except ValueError:
            pass
    return time
