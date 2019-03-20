#! /usr/bin/env python3
"""Simple utility for cloning projects for muJava."""
import os
import sys
import json
from shutil import rmtree

module_path = os.path.abspath('..')
if module_path not in sys.path:
    sys.path.append(module_path)
import utils

ARGS = sys.argv[1:]
if not ARGS:
    sys.exit(1)

outerdir = os.path.join('/', 'tmp', 'mujava-testing')
if os.path.exists(outerdir) and os.path.isdir(outerdir):
    rmtree(outerdir)

taskfile = ARGS[0]
with open(taskfile) as infile:
    for task in infile:
        opts = json.loads(task)
        projectpath = opts['projectPath']
        clonepath = os.path.join(outerdir, os.path.basename(projectpath))
        utils.clone_project(projectpath, clonepath, package=False)

