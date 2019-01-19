#! /usr/bin/env python3

"""Grabs sample projects from the specified directory."""
# pylint: skip-file
import os
import sys
import json
import random

def printhelp():
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


def write_successful(resultpath, n):
    projects = []
    with open(resultpath, 'r') as infile:
        for line in infile:
            data = json.loads(line)
            if data['success']:
                projects.append(data['projectPath'])

    if n is not None:
        projects = random.sample(projects, int(n))
    for item in projects:
        obj = { 'projectPath': item }
        print(json.dumps(obj))

def write_all_projects(dirpath):
    projects = []
    for item in os.listdir(dirpath):
        obj = { 'projectPath': item }
        print(json.dumps(obj))


if __name__ == '__main__':
    args = sys.argv[1:]

    if not args or any(x in args for x in ['-h', '--help']):
        printhelp()
    
    # grab a sample of successful projects?
    successful = False
    if '-s' in args:
        successful = True
        args.remove('-s')

    infile = args[0]
    if successful:
        try:
            n = args[1]
            write_successful(infile, n)
        except IndexError:
            write_successful(infile, None)
    else:
        write_all_projects(infile)
