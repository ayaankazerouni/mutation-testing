#! /usr/bin/env python3
"""
Author: Ayaan Kazerouni <ayaan@vt.edu>
Description: Grab sample projects from the specified directory.
"""

import os
import sys
import json
import random

def _printhelp():
    print("Write paths to projects for mutation testing as JSON tasks.")
    print('\nRequired arguments:')
    print('\tinfile: A path to a mutation-results.json file if -s is specified,')
    print('\t\tor a path to a directory containing projects as subdirectories otherwise.')
    print('Optional arguments:')
    print('\tn: The number of successful projects to randomly sample, or omit for all of them.')
    print('\t\t(Only used if -s is passed.')
    print('Optional flags:')
    print('\t-s: Only output paths to projects where mutation testing was successful.')
    sys.exit(0)


def write_successful(resultpath, n_projects):
    """Write out paths to projects where mutation testing was successful.
    Requires a mutation-results.json file.

    Args:
        resultpath (str): Path to a mutation-results.json file
        n_projects (int): The number of projects to print out (randomly sampled)
    """
    projects = []
    with open(resultpath, 'r') as infile:
        for line in infile:
            data = json.loads(line)
            if data['success']:
                projects.append(data['projectPath'])

    if n_projects is not None:
        projects = random.sample(projects, int(n_projects))
    for item in projects:
        obj = {'projectPath': item}
        print(json.dumps(obj))

def write_all_projects(dirpath, n_projects=None):
    """Write out paths to all projects within the specified dirpath."""
    #for item in os.listdir(dirpath):
    #    obj = {'projectPath': os.path.join(dirpath, item)}
    #    print(json.dumps(obj))

    projects=  [itm for itm in os.listdir(dirpath)]
    if n_projects is not None:
        projects = random.sample(projects, int(n_projects))
    for item in projects:
        obj = {'projectPath': os.path.join(dirpath,item)}
        print(json.dumps(obj))


if __name__ == '__main__':
    ARGS = sys.argv[1:]

    if not ARGS or any(x in ARGS for x in ['-h', '--help']):
        _printhelp()

    # grab a sample of successful projects?
    SUCCESSFUL = False
    if '-s' in ARGS:
        SUCCESSFUL = True
        ARGS.remove('-s')

    INFILE = ARGS[0]
    if SUCCESSFUL:
        try:
            N_PROJECTS = ARGS[2]
            write_successful(INFILE, N_PROJECTS)
        except IndexError:
            write_successful(INFILE, None)
    else:
        try:
            N_PROJECTS = ARGS[2]
            write_all_projects(INFILE, N_PROJECTS)
        except IndexError:
            write_all_projects(INFILE, None)

