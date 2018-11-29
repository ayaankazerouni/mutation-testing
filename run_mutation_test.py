#! /usr/bin/env python3

"""
Author: Ayaan Kazerouni <ayaan@vt.edu>
Description: Run mutation analysis on projects from a taskFile.

Overview:
 - Copy project to /tmp/
 - Create artificial package structure for the project so that
   PIT doesn't try to mutate itself (e.g., com.example)
 - Assumes the following project structure: {project-root}/{src}/{*.java}
 - Run PIT from the ANT build file (assumed to be in the current directory)

Mutation testing dependencies:
 - ANT (https://ant.apache.org)
 - PIT (http://pitest.org)
 - see lib/ for required jars to get PIT running
 - (on macOS) brew install gsed

Usage:
 - Part of a batch job, using ./run-all (see ./run-all --help)
 - Run as a CLI tool on one or more projects using a task file.
   Usage: ./run-mutation-test --help
 - import run_mutation_test
"""

import os
import sys
import json
import time
import subprocess
from shutil import rmtree, copytree
from aggregate_results import get_mutation_coverage

MUTATORS = [
    'REMOVE_CONDITIONALS',
    'VOID_METHOD_CALLS',
    'NON_VOID_METHOD_CALLS',
    'CONSTRUCTOR_CALLS',
    'TRUE_RETURNS',
    'FALSE_RETURNS',
    'PRIMITIVE_RETURNS',
    'EMPTY_RETURNS'
]

# default values; might be modified once at startup and read-only thereafter
CONFIG = {
    'log': False,
    'all_mutators': True
}

def main(args):
    """Entry point. Respond to CLI args and trigger execution."""
    if any(x in args for x in ['-h', '--help']):
        printhelp()

    if any(x in args for x in ['-l', '--log']):
        CONFIG['log'] = True

    if any(x in args for x in ['-s', '--steps']):
        CONFIG['all_mutators'] = False

    taskfile = args[0]
    run(taskfile)

def printhelp():
    """Print usage info."""
    usage = '''
    Run mutation analysis on projects from a taskFile.
    Usage: ./run-mutation-test tasks.json [-l] [-h]

    taskFile\t NDJSON file containing tasks with the keys:
    \t\t{ projectPath (required) }
    -l|--log\t Print stdout and stderr? Don't use this with ./run-all
    -h|--help\t Print this help (ignoring any other params)
    -s|--steps\t Run testing in steps, one mutator at a time
    '''
    print(usage)
    sys.exit(1)

def run(taskfile):
    """Trigger mutation testing and respond to output.

    Output is printed to the console in the form of a stringified dict.
    Arguments:
        taskfile (str): Path to an NDJSON file containing filepaths
    """
    with open(taskfile) as infile:
        for line in infile:
            opts = json.loads(line)
            start = time.time()
            try:
                result = testsingleproject(opts)
                if result:
                    diff = time.time() - start
                    output = {
                        'success': True,
                        'projectPath': opts['projectPath'],
                        'runningTime': diff
                        }
                    print(json.dumps(output))
                    if CONFIG['log']:
                        print(result.stdout)
                elif CONFIG['log']:
                    print(('Ran mutation testing for each individual mutator. '
                           'Results in pitReports.'))
            except subprocess.CalledProcessError as err:
                diff = time.time() - start
                output = {
                    'success': False,
                    'projectPath': opts['projectPath'],
                    'message': str(err),
                    'runningTime': diff
                    }
                print(json.dumps(output))
                if CONFIG['log']:
                    print(err.stdout)

def testsingleproject(opts):
    """Run mutation testing on a single project.

    This function has file system side effects. Copies the project to /tmp/ and
    runs mutation testing using PIT. PIT results are in /tmp/{projectpath}/pitReports.

    Arguments:
        opts (dict): Containing the keys { projectPath (required), antTask (default "pit")

    Returns:
        *subprocess.CompletedProcess*: The result of executing the ANT task

    Raises:
        *subprocess.CalledProcessError*: If any CLI utils invoked by subprocess cause exceptions
    """
    projectpath = os.path.normpath(os.path.expanduser(opts['projectPath']))
    clonepath = os.path.join('/tmp/mutation-testing', os.path.basename(projectpath), '')
    pkg = os.path.join(clonepath, 'src', 'com', 'example', '')

    # Copy the project to /tmp/ to avoid modifying the original
    if os.path.exists(clonepath) and os.path.isdir(clonepath):
        rmtree(clonepath)
    copytree(projectpath, clonepath)

    # Create com.example package structure
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
            print(('If you are on macOS, please install the GNU sed extension "gsed". '
                   'To install: brew install gsed'))
        sys.exit(0)

    cwd = os.getcwd()
    antpath = os.path.join(cwd, 'build.xml')
    libpath = os.path.join(cwd, 'lib')
    antopts = {
        'antpath': antpath,
        'libpath': libpath,
        'clonepath': clonepath
    }

    if CONFIG['all_mutators']:
        antopts['mutators'] = ','.join(MUTATORS)
        return __mutate(**antopts)

    # use each mutation operator one-by-one
    for mutator in MUTATORS:
        antopts['mutators'] = mutator
        antopts['pitreports'] = os.path.join(clonepath, 'pitReports', mutator)
        __mutate(**antopts)
        if CONFIG['log']:
            print('Finished mutating with {}'.format(mutator))
        
        # TODO: Aggregate results from multiple runs

    return None

def __mutate(antpath, clonepath, libpath, mutators, pitreports=None):
    pitreports = os.path.join(clonepath, 'pitReports') if pitreports is None else pitreports
    targetclasses, targettests = getpittargets(os.path.join(clonepath, 'src', ''))
    antcmd = ('ant -f {} -Dbasedir={} -Dresource_dir={} -Dtarget_classes={} '
              '-Dtarget_tests={} -Dmutators={} -Dpit_reports={} {}') \
              .format(antpath, clonepath, libpath, targetclasses, targettests, mutators,
                      pitreports, 'pit')
    result = subprocess.run(antcmd, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                            encoding='utf-8')
    result.check_returncode()

    mutationresults = get_mutation_coverage(resultspath=os.path.join(pitreports, 'mutations.csv'),
                                            getseries=False)
    if mutationresults is not None:
        with open(os.path.join(pitreports, 'results.json'), 'w') as resultfile:
            json.dump(mutationresults, resultfile)

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
    for root, _, files in os.walk(src):
        if files:
            packagename = root.replace(src, '').replace(os.sep, '.')
            targetclasses.append('{}.*'.format(packagename))
            targettests.append('{}.*Test*'.format(packagename))

    targetclasses = ','.join(targetclasses)
    targettests = ','.join(targettests)

    return (targetclasses, targettests)

if __name__ == '__main__':
    if sys.argv[1:]:
        main(sys.argv[1:])
    else:
        print('Error! No args')
        printhelp()
