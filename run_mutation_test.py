#! /usr/bin/env python3

"""
Author: Ayaan Kazerouni <ayaan@vt.edu>
Description: Run mutation analysis on projects from a taskFile. 

Overview:
 - Copy project to /tmp/
 - Create artificial package structure for the project so that
   PIT doesn't try to mutate itself
 - Run PIT from the ANT build file (assumed to be in the current directory)

Mutation testing dependencies:
 - ANT (https://ant.apache.org)
 - PIT (http://pitest.org)
 - see lib/ for required jars to get PIT running
 - (on macOS) brew install gsed

Usage:
 - Part of a batch job, using ./run-all (./run-all --help) 
 - Run as a CLI tool on one or more projects using a task file.
   Usage: ./run-mutation-test --help
"""

import os
import sys
import json
import time
import subprocess
from shutil import rmtree, copytree

def main(args):
    """Entry point. Respond to CLI args and trigger execution."""
    if any(x in args for x in [ '-h', '--help' ]):
        usage()
   
    log = False
    if any(x in args for x in [ '-l', '--log' ]):
        log = True

    taskfile = args[0]
    run(taskfile, log=log)

def usage():
    """Print usage info."""
    usage = '''
    Run mutation analysis on projects from a taskFile.
    Usage: ./run-mutation-test tasks.json [-l] [-h]

    taskFile\t NDJSON file containing tasks with the keys:
    \t\t{ projectPath (required), antTask (default "pit") }
    -l|--log\t Print stdout and stderr? Don't use this with GNU Parallel
    -h|--help\t Print this help (ignoring any other params)
    '''
    print(usage)
    sys.exit(1)

def run(taskfile, log=False):
    """Trigger mutation testing and respond to output.

    Output is printed to the console in the form of a stringified dict.
    Arguments:
        log (bool): Print full stdout/stderr?
    """
    with open(taskfile) as f:
        for line in f:
            opts = json.loads(line)
            start = time.time()
            try:
                result = testsingleproject(opts, log)
                diff = time.time() - start
                output = {
                        'success': True,
                        'projectPath': opts['projectPath'],
                        'runningTime': diff
                    }
                print(json.dumps(output))
                if log:
                    print(result.stdout)
            except subprocess.CalledProcessError as e:
                diff = time.time() - start
                output = {
                        'success': False,
                        'projectPath': opts['projectPath'],
                        'message': str(e),
                        'runningTime': diff
                    }
                print(json.dumps(output))
                if log:
                    print(e.stdout)

def testsingleproject(opts, log):
    """Run mutation testing on a single project.

    This function has file system side effects. Copies the project to /tmp/ and
    runs mutation testing using PIT. PIT results are in /tmp/{projectpath}/pitReports.

    Arguments:
        options (dict): Containing the keys { projectPath (required), antTask (default "pit")
        log (bool): To log or not to log, that is the question

    Returns:
        *subprocess.CompletedProcess*: The result of executing the ANT task

    Raises:
        *subprocess.CalledProcessError*: If any CLI utils invoked by subprocess cause exceptions 
    """
    projectpath = opts['projectPath']
    task = opts.get('antTask', 'pit')
    clonepath = os.path.join('/tmp/mutation-testing', os.path.basename(projectpath), '')
    src = os.path.join(clonepath, 'src', '')
    pkg = os.path.join(src, 'com', 'example', '')
    
    # Copy the project to /tmp/ to avoid modifying the original
    if os.path.exists(clonepath) and os.path.isdir(clonepath):
        rmtree(clonepath)
    copytree(projectpath, clonepath)
    
    # Create com.example package structure
    os.makedirs(pkg)

    # Move Java files directly under src into src/com/example
    mvcmd = 'mv {javafiles} {package}' \
            .format(javafiles=os.path.join(src, '*.java'), package=pkg)
    subprocess.run(mvcmd, shell=True).check_returncode()

    # Add package declaration to the top of Java files
    sedcmd = 'gsed' if sys.platform == 'darwin' else 'sed' # requires GNU sed on macOS
    sedcmd = sedcmd + " -i '1ipackage com.example;' {javafiles}" \
            .format(javafiles=os.path.join(pkg, '*.java'))
    try:
        subprocess.run(sedcmd, shell=True).check_returncode()
    except subprocess.CalledProcessError as e:
        if e.returncode == 127 and sys.platform == 'darwin':
            print(('If you are on macOS, please install the GNU sed extension "gsed". '
                    'To install: brew install gsed'))
        sys.exit(0)

    # Prepare to run PIT using ANT
    wd = os.getcwd()
    antpath = os.path.join(wd, 'build.xml')
    libpath = os.path.join(wd, 'lib')
    targetclasses, targettests = getpittargets(src)
    antcmd = ('ant -f {} -Dbasedir={} '
            '-Dresource_dir={} -Dtarget_classes={} -Dtarget_tests={} {}') \
                    .format(antpath, clonepath, libpath, targetclasses, targettests, task)
    result = subprocess.run(antcmd, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
            encoding='utf-8')
    result.check_returncode()

    return result


def getpittargets(src):
    """Walk down the dirtree starting at src and return code and test targets for PIT.

    Arguments:
        src (str): Path to the directory to start at

    Returns:
        A tuple containing (targetclasses, targettests). e.g. (com.example.*, com.example.*Test*)
    """
    targetclasses = []
    targettests = []
    for root, dirs, files in os.walk(src):
        if files:
            packagename = root.replace(src, '').replace(os.sep, '.')
            targetclasses.append('{}.*'.format(packagename))
            targettests.append('{}.*Test*'.format(packagename))

    targetclasses = ','.join(targetclasses)
    targettests = ','.join(targettests)

    return (targetclasses, targettests)

if __name__ == '__main__':
    main(sys.argv[1:])
