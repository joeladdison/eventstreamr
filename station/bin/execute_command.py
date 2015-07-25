#!/usr/bin/env python

import os
import json
import sys


def main():
    if len(sys.argv) < 1:
        print("Missing config file path")
        sys.exit(1)

    config_path = sys.argv[0]
    with open(config_path, 'r') as f:
        config = json.load(f)

    if config.get('args'):
        path = config['command'].format(**config['args'])
    else:
        path = config['command']
    path = path.split(' ')
    os.execvp(path[0], path)

    print("exec failed")
    sys.exit(2)


if __name__ == '__main__':
    main()
