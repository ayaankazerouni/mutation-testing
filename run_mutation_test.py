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
import logging
from shutil import rmtree, copytree

def main(args):
    """Entry point. Respond to CLI args and trigger execution."""
    if any(x in args for x in ['-h', '--help']):
        printhelp()

    loglevel = logging.WARN
    if any(x in args for x in ['-l', '--log']):
        loglevel = logging.INFO
    logging.basicConfig(filename='mutation.log', filemode='w', level=loglevel)

    all_mutators = True
    if any(x in args for x in ['-s', '--steps']):
        all_mutators = False

    taskfile = args[0]
    run(taskfile, all_mutators)

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

def run(taskfile, all_mutators=True):
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
                projectpath = opts['projectPath']
                logging.info('Starting for %s', projectpath)
                runner = MutationRunner(
                    projectpath=projectpath,
                    all_mutators=all_mutators
                )
                result = runner.testsingleproject()
                if result:
                    diff = time.time() - start
                    output = {
                        'success': True,
                        'projectPath': opts['projectPath'],
                        'runningTime': diff
                        }
                    print(json.dumps(output))
                    logging.info(result.stdout)
                else:
                    logging.info(('Ran mutation testing for each individual mutator. '
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
                logging.error(err.stdout)

class MutationRunner:
    """Runs mutation testing on a specified project.

    Attributes:
        projectpath (str): Absolute path to the project
    """
    # class attributes
    available_mutators = [
        'REMOVE_CONDITIONALS',
        'VOID_METHOD_CALLS',
        'NON_VOID_METHOD_CALLS',
        'CONSTRUCTOR_CALLS',
        'TRUE_RETURNS',
        'FALSE_RETURNS',
        'PRIMITIVE_RETURNS',
        'EMPTY_RETURNS'
    ]

    def __init__(self, projectpath, antpath=None, libpath=None, all_mutators=True):
        self.projectpath = os.path.normpath(os.path.expanduser(projectpath))
        self.projectname = os.path.basename(self.projectpath)
        self.clonepath = os.path.join('/tmp/mutation-testing', self.projectname, '')
        self.all_mutators = all_mutators
        cwd = os.getcwd()
        self.antpath = antpath or os.path.join(cwd, 'build.xml')
        self.libpath = libpath or os.path.join(cwd, 'lib')

    def testsingleproject(self):
        """Run mutation testing on a single project.

        This function has file system side effects. Copies the project to /tmp/ and
        runs mutation testing using PIT. PIT results are in /tmp/{projectpath}/pitReports.

        Arguments:
            opts (dict): Containing the keys { projectPath (required), antTask (default "pit") }

        Returns:
            *subprocess.CompletedProcess*: The result of executing the ANT task

        Raises:
            *subprocess.CalledProcessError*: If any CLI utils invoked by subprocess cause exceptions
        """
        # Copy the project to /tmp/ to avoid modifying the original
        if os.path.exists(self.clonepath) and os.path.isdir(self.clonepath):
            rmtree(self.clonepath)
        copytree(self.projectpath, self.clonepath)

        # Create com.example package structure
        pkg = os.path.join(self.clonepath, 'src', 'com', 'example', '')
        os.makedirs(pkg)

        # Move Java files directly under src into src/com/example
        mvcmd = 'mv {javafiles} {package}' \
                .format(javafiles=os.path.join(self.clonepath, 'src', '*.java'), package=pkg)
        subprocess.run(mvcmd, shell=True).check_returncode()

        # Add package declaration to the top of Java files
        sedcmd = 'gsed' if sys.platform == 'darwin' else 'sed' # requires GNU sed on macOS
        sedcmd = sedcmd + " -i '1ipackage com.example;' {javafiles}" \
                .format(javafiles=os.path.join(pkg, '*.java'))
        try:
            subprocess.run(sedcmd, shell=True).check_returncode()
        except subprocess.CalledProcessError as err:
            if err.returncode == 127 and sys.platform == 'darwin':
                logging.error(('If you are on macOS, please install the GNU sed extension "gsed". '
                               'To install: brew install gsed'))
            sys.exit(0)

        if self.all_mutators:
            mutators = ','.join(MutationRunner.available_mutators)
            return self.__mutate(mutators)

        # use each mutation operator one-by-one
        for mutator in MutationRunner.available_mutators:
            pitreports = os.path.join(self.clonepath, 'pitReports', mutator)
            self.__mutate(mutator, pitreports=pitreports)
            logging.info('%s: Finished mutating with %s', self.projectname, mutator)
        return None

    def __mutate(self, mutators, pitreports=None):
        if pitreports is None:
            pitreports = os.path.join(self.clonepath, 'pitReports')
        targetclasses, targettests = self.getpittargets(os.path.join(self.clonepath, 'src', ''))
        antcmd = ('ant -f {} -Dbasedir={} -Dresource_dir={} -Dtarget_classes={} '
                  '-Dtarget_tests={} -Dmutators={} -Dpit_reports={} pit') \
                  .format(
                      self.antpath,
                      self.clonepath,
                      self.libpath,
                      targetclasses,
                      targettests,
                      mutators,
                      pitreports
                  )
        logging.info('ANT command: %s', antcmd)
        result = subprocess.run(antcmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding='utf-8')
        result.check_returncode()

        return result

    def getpittargets(self, src):
        """Walk down the dirtree starting at src and return code and test targets for PIT
        as Java class globs.

        Arguments: .
            src (str): Path to the directory to start at

        Returns:
            (str, str). e.g. (com.example.*, com.example.*Test*)
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
