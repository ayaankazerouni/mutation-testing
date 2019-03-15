#! /usr/bin/env python3
"""Simple utility for cloning projects for muJava."""
import os
import sys
import json

module_path = os.path.abspath('..')
if module_path not in sys.path:
    sys.path.append(module_path)
import utils

ARGS = sys.argv[1:]
if not ARGS:
    sys.exit(1)

taskfile = ARGS[0]
with open(taskfile) as infile:
    for task in infile:
        opts = json.loads(task)
        projectpath = opts['projectPath']
        clonepath = os.path.join('/tmp/mujava-testing', os.path.basename(projectpath))
        utils.clone_project(projectpath, clonepath, package=False)

