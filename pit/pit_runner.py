#! /usr/bin/env python3
"""
Author: Ayaan Kazerouni <ayaan@vt.edu>
Description: Run mutation analysis using PIT on projects from a taskFile.

Overview:
 - Copy project to /tmp/
 - Create artificial package structure for the project so that
   PIT doesn't try to mutate itself (e.g., com.example)
 - Assumes the following project structure: {project-root}/{src}/{*.java}
 - Run PIT from the ANT build file

Mutation testing dependencies:
 - ANT (https://ant.apache.org)
 - PIT (http://pitest.org)
 - see lib/ for required jars to get PIT running
 - (on macOS) brew install gsed

Usage:
 - Run as a CLI tool on one or more projects using a task file.
   Usage: see ./pit_runner.py --help
 - import mutation_runner 
"""

import os
import sys
import json
import time
import subprocess
import logging
import argparse
from shutil import rmtree, copytree

module_path = os.path.abspath('..')
if module_path not in sys.path:
    sys.path.append(module_path)

import utils

def main(args):
    """Entry point. Respond to CLI args and trigger execution."""
    loglevel = args.log
    logging.basicConfig(filename='.log', filemode='w', level=loglevel)

    taskfile = args.taskfile
    run(taskfile, args.steps, args.mutators)

def run(taskfile, steps=False, mutators='all'):
    """Trigger mutation testing and respond to output.

    Output is printed to the console in the form of a stringified dict.
    Args:
        taskfile (str): Path to an NDJSON file containing filepaths
        step (bool): Run mutators one-by-one, or all at once? 
        mutators (bool): Set of mutators to use (see --help)
    """
    with open(taskfile) as infile:
        for line in infile:
            __run_for_project(line, steps, mutators)

def __run_for_project(task, steps, mutators):
    opts = json.loads(task)
    projectpath = opts['projectPath']
    logging.info('Starting for %s', projectpath)
    runner = MutationRunner(
        projectpath=projectpath,
        steps=steps,
        mutators=mutators
    )
    mutationoutput = runner.testsingleproject()
    if not steps:
        # mutationoutput is a tuple
        coverage, result, runningtime = mutationoutput
        if result.returncode == 0:
            output = {
                'success': True,
                'projectPath': opts['projectPath'],
                'runningTime': runningtime,
                'coverage': coverage
                }
            print(json.dumps(output))
            logging.info('%s: %s set', runner.projectname, mutators)
            logging.info(result.stdout)
        else:
            output = {
                'success': False,
                'projectPath': opts['projectPath'],
                'runningTime': runningtime
                }
            print(json.dumps(output))
            logging.error('%s: %s set', runner.projectname, mutators)
            logging.error(result.stdout)
            logging.error(result.stderr)
    else:
        # mutationoutput is a dict
        output = {
            'projectPath': opts['projectPath']
        }
        successes = []
        for key, value in mutationoutput.items():
            coverage, result, runningtime = value # this is a tuple
            if result.returncode == 0:
                output[key] = coverage
                output['{}_runningTime'.format(key)] = runningtime
                logging.info('%s: %s', runner.projectname, key)
                logging.info(result.stdout)
                successes.append(True)
            elif result.returncode > 0 or coverage is None:
                logging.error('%s: %s', runner.projectname, key)
                logging.error(result.stderr)
                logging.error(result.stdout)
                successes.append(False)
        output['success'] = all(successes)
        print(json.dumps(output))

class MutationRunner:
    """Runs PIT mutation testing on a specified project.

    Class Attributes:
        deletion_mutators (list): Approximation of Offut's deletion set using PIT operators. 
        default_mutators (list): PIT's old default group ("STRONGER" group in v1.4.6)
        all_mutators (list): All PIT mutators used by Laurent et al. in their evaluation.
                             This list subsumes the deletion_mutators list. 
    """
    # class attributes
    deletion_mutators = [
        'REMOVE_CONDITIONALS',
        'VOID_METHOD_CALLS',
        'NON_VOID_METHOD_CALLS',
        'CONSTRUCTOR_CALLS',
        'TRUE_RETURNS',
        'FALSE_RETURNS',
        'PRIMITIVE_RETURNS',
        'EMPTY_RETURNS'
    ]

    sufficient_mutators = [
        'ABS',
        'AOR',
        'ROR',
        'UOI'
    ]

    default_mutators = [
        'CONDITIONALS_BOUNDARY',
        'INCREMENTS',
        'INVERT_NEGS',
        'MATH',
        'NEGATE_CONDITIONALS',
        'RETURN_VALS',
        'VOID_METHOD_CALLS'
    ]

    all_mutators = deletion_mutators + [
        'CONDITIONALS_BOUNDARY',
        'NEGATE_CONDITIONALS',
        'MATH',
        'INCREMENTS',
        'INVERT_NEGS',
        'INLINE_CONSTS',
        'RETURN_VALS',
        'EXPERIMENTAL_MEMBER_VARIABLE',
        'EXPERIMENTAL_SWITCH',
        'ABS',
        'AOD',
        'AOR',
        'CRCR',
        'OBBN',
        'ROR',
        'UOI'
    ]

    def __init__(self, projectpath, antpath=None, libpath=None,
                 steps=False, mutators='all'):
        self.projectpath = os.path.normpath(os.path.expanduser(projectpath))
        self.projectname = os.path.basename(self.projectpath)
        self.clonepath = os.path.join('/tmp/mutation-testing', self.projectname, '')
        self.steps = steps 
        if mutators == 'all':
            self.mutators = self.all_mutators
        elif mutators == 'deletion':
            self.mutators = self.deletion_mutators
        elif mutators == 'default':
            self.mutators = self.default_mutators
        elif mutators == 'sufficient':
            self.mutators = self.sufficient_mutators
        else:
            mutators = mutators.split(',')
            if MutationRunner.__check_mutators(mutators):
                self.mutators = mutators
            else:
                raise ValueError(('Use keywords all, deletion, default, sufficient, '
                                'or a comma-separated valid set of mutation operators'))

        cwd = os.getcwd()
        self.antpath = antpath or os.path.join(cwd, 'build.xml')
        self.libpath = libpath or os.path.join(cwd, 'lib')

    @classmethod
    def __check_mutators(cls, mutators):
        return all([x in cls.all_mutators for x in mutators])


    def testsingleproject(self):
        """Run mutation testing on a single project.

        Returns a (float, CompletedSubprocess, float)  tuple if all
        supplied mutators are used, or a dict of (float, CompletedSubprocess, float)
        tuples if mutators are applied one after the other, with each key being
        the name of a mutation operator.

        Returns:
            (float, CompletedProcess, float): A tuple containing the coverage percentage, the
                                              completed subprocess, and the running time, or
            (dict): The coverage percentages, completed subprocess, and running time
                    for each mutation operator (if self.steps)
        """
        utils.clone_project(self.projectpath, self.clonepath)

        if not self.steps:
            start = time.time()
            pitreports = os.path.join(self.clonepath, 'pitReports')
            mutators = ','.join(self.mutators)
            result = self.__mutate(mutators, pitreports)
            runningtime = time.time() - start
            # look for the CSV file PIT creates
            coveragecsv = os.path.join(pitreports, 'mutations.csv')
            coverage = utils.get_mutation_coverage(coveragecsv)
            if coverage is None:
                return (None, result, runningtime)
            return (coverage['mutationCovered'], result, runningtime)

        # use each mutation operator one-by-one
        results = {}
        for mutator in self.mutators:
            start = time.time()
            pitreports = os.path.join(self.clonepath, 'pitReports', mutator)
            result = self.__mutate(mutator, pitreports=pitreports)
            runningtime = time.time() - start
            if result.returncode > 0:
                logging.error('%s: Error running operator %s',
                              self.projectname, mutator)
                results[mutator] = (None, result, runningtime)
            else:
                coveragecsv = os.path.join(pitreports, 'mutations.csv')
                coverage = utils.get_mutation_coverage(coveragecsv)
                if coverage is None:
                    results[mutator] = (None, result, runningtime)
                else:
                    results[mutator] = (coverage['mutationCovered'], result, runningtime)
            logging.info('%s: Finished mutating with %s', self.projectname, mutator)
        return results

    def __mutate(self, mutators, pitreports):
        targetclasses, targettests = self.getpittargets()
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
        return result

    def getpittargets(self):
        """Walk down the dirtree starting at the project source and return code and
        test targets for PIT as Java class globs.

        Returns:
            (str, str). e.g. (com.example.*, com.example.*Test*)
        """
        src = os.path.join(self.clonepath, 'src', '')
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
    parser = argparse.ArgumentParser(
            description='Run mutation analysis on projects from a taskFile.'
        )
    parser.add_argument('taskfile', 
                        help='Path to an NDJSON file containing project tasks.\n\
                                Each task should have the key "projectPath", pointing \
                                to a project target for mutation.')
    parser.add_argument('-l', '--log', action='store_const', const=logging.INFO, 
                        default=logging.WARN, help='if given, sets log level to INFO')
    parser.add_argument('-s', '--steps', action='store_true', 
                        help='run each mutator one-by-one?')
    parser.add_argument('-m', '--mutators', default='all',
                        help='set of mutators to run (all|default|deletion|sufficient)')
    if sys.argv[1:]:
        args = parser.parse_args()
        main(args)
    else:
        print('Error! No args')
        parser.print_help()
