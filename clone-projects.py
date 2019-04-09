#! /usr/bin/env python3
"""Simple utility for cloning projects for mutation testing."""
import os
import sys
import json
from shutil import rmtree, copytree
import subprocess

def clone_project(projectpath, clonepath, package=True):
    """Copy the project at projectpath to the specified clonepath.

    Args:
        projectpath (str): Original path to the initial project
        clonepath (str): Path to be cloned to
        package (bool): Should com.example.* package structure be created?
                        This is needed for PIT testing, so that PIT doesn't
                        try to mutate itself.
    """
    # Copy the project to /tmp/ to avoid modifying the original
    if os.path.exists(clonepath) and os.path.isdir(clonepath):
        rmtree(clonepath)
    copytree(projectpath, clonepath)
    
    if package:
        # Create com.example package structure
        pkg = os.path.join(clonepath, 'src', 'com', 'example', '')
        os.makedirs(pkg)

        # Move Java files directly under src into src/com/example
        mvcmd = 'mv {javafiles} {package}' \
                .format(javafiles=os.path.join(clonepath, 'src', '*.java'), package=pkg)
        subprocess.run(mvcmd, shell=True).check_returncode()

        # Add package declaration to the top of Java files
        sedcmd = 'gsed' if sys.platform == 'darwin' else 'sed' # requires GNU sed on macOS
        sedcmd = sedcmd + " -i '1ipackage com.example;' {javafiles}" \
                .format(javafiles=os.path.join(pkg, '*.java'))
        try:
            subprocess.run(sedcmd, shell=True).check_returncode()
        except subprocess.CalledProcessError as err:
            if err.returncode == 127 and sys.platform == 'darwin':
                logging.error(('If you are on macOS, please install the GNU '
                               'sed extension "gsed". To install: brew install gsed'))
            sys.exit(0)

if __name__ == '__main__':
    ARGS = sys.argv[1:]
    if not ARGS:
        print('Error! No args')
        sys.exit(1)

    outerdir = os.path.join('/', 'tmp', 'mutation-testing')
    if os.path.exists(outerdir) and os.path.isdir(outerdir):
        rmtree(outerdir)

    taskfile = ARGS[0]
    package = '-p' in ARGS
    with open(taskfile) as infile:
        for task in infile:
            opts = json.loads(task)
            projectpath = opts['projectPath']
            clonepath = os.path.join(outerdir, os.path.basename(projectpath))
            clone_project(projectpath, clonepath, package=package)

