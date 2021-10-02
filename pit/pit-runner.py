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
"""
import os
import re
import sys
import json
import time
import subprocess
import logging
import argparse
from shutil import rmtree, copytree

import utils

def main(args):
    """Entry point. Respond to CLI args and trigger execution."""
    loglevel = args.log
    logging.basicConfig(filename='.log-pit', filemode='w', level=loglevel)

    taskfile = args.taskfile
    run(taskfile, args.mutators, args.targetclasses, args.excludetargetclasses, args.excludetargettests)

def run(taskfile, mutators='all', targetclasses=None, exclude_class=None, exclude_test=None):
    """Trigger mutation testing and respond to output.

    Output is printed to the console in the form of a stringified dict.
    Args:
        taskfile (str): Path to an NDJSON file containing filepaths
        mutators (bool): Set of mutators to use (see --help)
        targetclasses (str): Comma-separated Java blob of fully qualified class 
                             names to mutate
        exclude_class (str): Java globs of classes that should NOT be mutated
        exclude_test (str): Java globs of tests that should NOT be checked
    """
    with open(taskfile) as infile:
        for line in infile:
            __run_for_project(line, mutators, targetclasses, exclude_class, exclude_test)

def __run_for_project(task, mutators, targetclasses, exclude_class, exclude_test):
    opts = json.loads(task)
    projectpath = opts['projectPath']
    logging.info('Starting for %s', projectpath)
    runner = MutationRunner(
        projectpath=projectpath,
        mutators=mutators,
        targetclasses=targetclasses,
        exclude_class=exclude_class,
        exclude_test=exclude_test
    )
    mutationoutput = runner.testsingleproject()

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

class MutationRunner:
    """Runs PIT mutation testing on a specified project.

    Class Attributes:
        deletion_mutators (list): Approximation of Offut's deletion set using PIT operators. 
        sufficient_mutators (list): Classic mutation operators from the literature, added by Laurent
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
        'AOD',
        'EXPERIMENTAL_MEMBER_VARIABLE',
        'OBBN'
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

    all_mutators = [
        'ABS',
        'AOD',
        'AOR',
        'TRUE_RETURNS',
        'CRCR',
        'REMOVE_CONDITIONALS',
        'CONSTRUCTOR_CALLS',
        'EMPTY_RETURNS',
        'INCREMENTS',
        'INLINE_CONSTS',
        'MATH',
        'NON_VOID_METHOD_CALLS',
        'VOID_METHOD_CALLS',
        'ROR',
        'RETURN_VALS',
        'UOI',
        'EXPERIMENTAL_MEMBER_VARIABLE',
        'EXPERIMENTAL_SWITCH'
    ]

    mutator_lists = {
        'all': all_mutators,
        'deletion': deletion_mutators,
        'default': default_mutators,
        'sufficient': sufficient_mutators
    }

    def __init__(self, projectpath, antpath=None, mutators='all', targetclasses='',
                 exclude_class=None, exclude_test=None):
        self.projectpath = os.path.normpath(os.path.expanduser(projectpath))
        self.projectname = os.path.basename(self.projectpath)
        self.clonepath = os.path.join('/tmp/mutation-testing', self.projectname, '')
        self.mutators = self.mutator_lists.get(mutators, None)
        if not self.mutators:
            mutators = mutators.split(',')
            if MutationRunner.__check_mutators(mutators):
                self.mutators = mutators
            else:
                raise ValueError(('Use keywords all, deletion, default, sufficient, '
                                'or a comma-separated valid set of mutation operators'))

        exclusion_class_rules = {
                None: None,
                "p5-excludeGUI": MutationRunner.__check_class_gui_window,
                "excludeGUI": MutationRunner.__check_class_gui_window
        }

        exclusion_test_rules = {
                None: None,
                "p5-excludeInputReference": MutationRunner.__check_test_InputReference,
                "excludeInputReference": MutationRunner.__check_test_InputReference
        }
        
        self.targetclasses = targetclasses
        self.exclusion_class_rule = exclusion_class_rules[exclude_class]
        self.exclusion_test_rule  = exclusion_test_rules[exclude_test]
        
        wd = os.path.abspath(os.path.dirname(__file__))
        self.antpath = antpath or os.path.join(wd, 'build.xml')
        self.libpath = os.path.join(wd, 'lib')

    @classmethod
    def __check_mutators(cls, mutators):
        r = '|'.join(['^{}'.format(m) for m in cls.all_mutators])
        return all([re.match(r, s) for s in mutators])  
    
    @classmethod
    def __check_class_gui_window(cls, filename):
        if not "java" in filename:
            # Default rule: if the file is not a java file, exclude it from testing
            return True
        if "GUI" in filename or "Window" in filename or "Test" in filename:
            return True
        # Ignore this class anyway, it is a default behaviour for test exclusion functions if Test is not in there.
        return False

    @classmethod 
    def __check_test_InputReference(cls, filename):
        if not "java" in filename:
            # Default rule: if the file is not a java file, exclude it from testing
            return True
        if "Test" in filename:
            if "InputReference" in filename:
                return True
            else:
                return False
        #Ignore this class anyway, it is a default behaviour for test exclusion functions if Test is not in there.
        return True

    def testsingleproject(self):
        """Run mutation testing on a single project.

        Returns a (float, CompletedSubprocess, float)  tuple if all
        supplied mutators are used, or a dict of (float, CompletedSubprocess, float)
        tuples if mutators are applied one after the other, with each key being
        the name of a mutation operator.

        Returns:
            (float, CompletedProcess, float): A tuple containing the coverage percentage, the
                                              completed subprocess, and the running time, or
        """
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

    def __mutate(self, mutators, pitreports):
        if self.targetclasses:
            _, targettests = self.getpittargets()
        else:
            self.targetclasses, targettests = self.getpittargets()

        antcmd = ('ant -f {} -Dbasedir={} -Dresource_dir={} -Dtarget_classes={} '
                  '-Dtarget_tests={} -Dmutators={} -Dpit_reports={} pit') \
                  .format(
                      self.antpath,
                      self.clonepath,
                      self.libpath,
                      self.targetclasses,
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
        
        # finds Java source files recursively
        for root, _, files in os.walk(src):
            if files:
                packagename = root.replace(src, '').replace(os.sep, '.')
                if not self.exclusion_class_rule:
                    targetclasses.append('{}.*'.format(packagename))
                else:
                    for filename in files:
                        if not self.exclusion_class_rule(filename):
                            targetclasses.append('{}.{}'.format(packagename,filename.replace(src, '').replace(os.sep, '.').replace('.java','')))

                if not self.exclusion_test_rule:
                    targettests.append('{}.*Test*'.format(packagename))
                else:
                    for filename in files:
                        if not self.exclusion_test_rule(filename):
                            targettests.append('{}.{}'.format(packagename,filename.replace(src, '').replace(os.sep, '.').replace('.java','')))

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
    parser.add_argument('-m', '--mutators', default='deletion',
                        help=('set of mutators to run: one of [all|default|deletion|sufficient] or '
                            'a list of comma-separated mutator names, as seen in the PIT documentation.'
                            ' Defaults to "deletion".'))
    parser.add_argument('-c', '--targetclasses', default=None,
                        help=('set of Java package globs to mutate: '
                            'a list of comma-separated values '
                            'Defaults to an empty string.'))
    parser.add_argument('-e', '--excludetargetclasses', default=None,
                        help=('Name of rule for excluding families of classes from target classes, associated with a function name in MutationRunner'
                            'a single string name, '
                            'Defaults to None, in which case target classes are determined by --targetclasses option'))
    parser.add_argument('-t', '--excludetargettests', default=None,
                        help=('Name of rule for excluding families of test classes from target tests, associated with a function name in MutationRunner'
                            'a single string name, '
                            'Defaults to None, in which case all target tests are selected'))
    if sys.argv[1:]:
        args = parser.parse_args()
        main(args)
    else:
        print('Error! No args')
        parser.print_help()

