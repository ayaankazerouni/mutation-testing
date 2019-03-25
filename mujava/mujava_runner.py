#! /usr/bin/env python3
"""
Author: Ayaan Kazerouni <ayaan@vt.edu>
Description: Run mutation analysis using muJava on projects from a taskFile.

Overview:
 - Copy project to /tmp/
 - Assumes the following project structure: {project-root}/{src}/{*.java}
 - Run muJava from the mujava.jar, which includes muScript (https://cs.gmu.edu/~offutt/mujava/muscript/) 

Mutation testing dependencies:
 - ANT (https://ant.apache.org)
 - muJava (https://cs.gmu.edu/~offutt/mujava/)
 - see lib/ for required jars to get muJava running

Usage:
 - Run as a CLI tool on one or more projects using a task file.
   Usage: see ./mujava_runner.py --help
 - import mutation_runner 
"""

import os
import re
import csv
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess

ENGINE = 'mujava'

class MutationRunner:
    """Runs muJava mutation testing on a specified project.
    
    Class Attributes:
        deletion_mutator (str): Code for the statement deletion mutator.
        all_mutators (list): All mutation operators provided by muJava.
    """
    # class attributes
    mutators = ['sdl'] 
    sessionname = 'session'
    
    def __init__(self, projectpath):
        self.projectpath = os.path.normpath(projectpath)
        self.projectname = os.path.basename(self.projectpath)
        self.clonepath = os.path.join('/tmp/mujava-testing', self.projectname, '')

        cwd = os.getcwd()
        self.antpath = os.path.join(cwd, 'build.xml')
        self.libpath = os.path.join(cwd, 'lib')
        self.mujava_classpath = ('{libdir}/mujava.jar:{libdir}/openjava.jar:'
                                 '{libdir}/commons-io.jar:{libdir}/junit.jar:'
                                 '{libdir}/student.jar:$JAVA_HOME/lib/tools.jar'
                                ).format(libdir=self.libpath)

        self.gentime = None
        self.runtime = None
        self.coverage = None

    def run(self):
        """
        Do the following:

        .. code-block:: none
            1. Compile the project
            2. Setup the test session
            3. Generate mutants
            4. Run tests against mutants

        Returns a dict containing output information, and writes a CSV file
        containing individual mutant information.

        Returns:
            (dict) A dictionary containing the keys below. If some keys are missing,
            it means that the runner errored out during or before that step. 

            .. code-block:: python
            {
                'projectPath': path to project (always present),
                'success': boolean (always present),
                'genTime': seconds taken to generate mutants,
                'runTime': seconds taken to run mutants,
                'coverage': proportion of mutants killed,
                'num_mutations': number of mutations being run 
            }
        """
        # projects were cloned already; assume they exist at self.clonepath
        # create mujavaCLI.config
        configpath = os.path.join(self.clonepath, 'mujavaCLI.config')
        with open(configpath, 'w') as f:
            f.write('MuJava_HOME={}'.format(os.path.normpath(self.clonepath)))
        
        output = {
            'projectPath': self.projectpath
        }

        success = self.compileproject()
        if not success:
            output['success'] = False
            return output
        
        self.setup_test_session()

        success, gentime = self.genmutes()
        output['genTime'] = gentime
        if not success:
            output['success'] = False
            return output

        results = self.runmutes()
        mutationresults = results.pop('mutationresults')
        output.update(results)
         
        fieldnames = ['project', 'className', 'engine', 'mutator', 'killed']
        csvpath = os.path.join(self.clonepath, 'mutations.csv')
        with open(csvpath, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=',')
            for result in mutationresults:
                writer.writerow(result)

        # write mujava results to file 
        resultfile = os.path.join(self.clonepath, 'mujava-result.ndjson')
        with open(resultfile, 'w') as outfile:
            json.dump(output, outfile)

        return output 

    def compileproject(self):
        """
        Compile the project using ANT.
        
        Returns:
            (bool): was the compilation successful?
        """
        antcmd = 'ant -f {} -Dresource_dir={} -Dbasedir={} clean compile' \
                    .format(self.antpath, self.libpath, self.clonepath) 
        logging.info('Compiling: {}'.format(antcmd))
        stdoutpath = os.path.join(self.clonepath, 'compile.log')
        with open(stdoutpath, 'w') as outfile:
            result = subprocess.run(antcmd, shell=True, cwd=self.clonepath, stdout=outfile, 
                                    stderr=subprocess.STDOUT, universal_newlines=True)
        if result.returncode == 0:
            logging.info('Compiled {}'.format(self.projectname))
            return True 
        else:
            msg = 'There was an error compiling {}. See the compile log at {}'\
                  .format(self.projectname, stdoutpath)
            logging.error(msg)
            return False

    def setup_test_session(self):
        """Create the test session directory structure required by muJava.

        MuJava can do this by itself, but it's pretty error prone. Setup the
        following directories within the project root:

        .. code-block:: none
        
            session/src         # source files
            session/classes     # class files for all source files
            session/testset     # class files for all tests
            session/result      # initially empty, will get populated with mutants
        """

        # make session directory structure
        sesh_path = os.path.join(self.clonepath, self.sessionname)
        logging.info('Creating test session at {}'.format(sesh_path))
        if os.path.exists(sesh_path):
            shutil.rmtree(sesh_path)

        sesh_srcpath = os.path.join(sesh_path, 'src')
        sesh_clspath = os.path.join(sesh_path, 'classes')
        sesh_tstpath = os.path.join(sesh_path, 'testset')
        sesh_resultpath = os.path.join(sesh_path, 'result')
        os.makedirs(sesh_srcpath)
        os.makedirs(sesh_clspath)
        os.makedirs(sesh_tstpath)
        os.makedirs(sesh_resultpath)

        # mv src files into place
        srcfiles = self.__javafiles()
        for filepath in srcfiles:
            filename = os.path.basename(filepath)
            dest = os.path.join(sesh_srcpath, filename)
            shutil.copy(filepath, dest)

        # mv source class files into place
        classfiles = self.__javafiles(dirname='classes')
        for filepath in classfiles:
            filename = os.path.basename(filepath)
            dest = os.path.join(sesh_clspath, filename)
            shutil.copy(filepath, dest)

        # mv test class files into place
        testfiles = self.__javafiles(test=True, dirname='classes')
        for filepath in testfiles:
            filename = os.path.basename(filepath)
            dest = os.path.join(sesh_tstpath, filename)
            shutil.copy(filepath, dest)

    def genmutes(self):
        """
        Use muJava to generated mutants.

        Returns:
            (bool, float): Success and running time in seconds
        """
        # generate mutants
        mutators = ' '.join(list(map(lambda m: '-{}'.format(m), self.mutators)))
        start = time.time()
        genmutescmd = 'java -cp {} mujava.cli.genmutes {} {}'\
                      .format(self.mujava_classpath, mutators, self.sessionname)
        logging.info('Generating mutants: {}'.format(genmutescmd))
        result = subprocess.run(genmutescmd, cwd=self.clonepath, shell=True,
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE,
                                universal_newlines=True)
        runningtime = time.time() - start
        if result.returncode == 0:
            logging.info(result.stdout)
            return (True, runningtime)
        else:
            logging.error(result.stdout)
            logging.error(result.stderr)
            return (False, runningTime)

    def runmutes(self):
        """
        Run the supplied JUnit tests on all mutants found in the directory:
        `{projectRoot}/{self.sessionname}/result`.

        All class files matching the glob `*Test.class` are treated as tests.
        """
        # original class files
        original = os.path.join(self.clonepath, 'classes')

        # find mutated class files and mutate
        mutated = self.__mutant_classes()
        total = len(mutated)
        killedcount = 0
        mutationresults = []
        err = False
        start = time.time()
        for mutantdir, mutantclass in mutated:
            classname, _ = os.path.splitext(mutantclass)
            mutator = os.path.basename(mutantdir).split('_')[0]
            killed = self.__runmutant(mutantdir, mutantclass)
            if killed:
                killedcount = killedcount + 1
            elif killed is None: # running this mutant errored out
                err = True
            mutationresults.append({
                'project': self.projectname,
                'className': classname,
                'engine': ENGINE,
                'mutator': mutator,
                'killed': killed
            })
        runningtime = time.time() - start
        coverage = killedcount / total
        
        return {
            'coverage': coverage,
            'runtime': runningtime,
            'success': not err,
            'mutationresults': mutationresults
        }

    def __runmutant(self, mutantdir, mutantclass):
        # create tmp bin directory
        tmpdir = os.path.join(self.clonepath, 'tmpbin')
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
        os.makedirs(tmpdir)
        classes = os.path.join(self.clonepath, 'classes')
        for filename in os.listdir(classes):
            if filename != mutantclass:
                shutil.copy(os.path.join(classes, filename), os.path.join(tmpdir, filename))
        mutantsrc = os.path.join(mutantdir, mutantclass)
        shutil.copy(mutantsrc, os.path.join(tmpdir, mutantclass))
        
        # run junit tests using the new set of classfiles
        antcmd = ('ant -f {} -Dbasedir={} -Dresource_dir={} run') \
                 .format(self.antpath, self.clonepath, self.libpath)
        logging.info('Running mutant: {}'.format(antcmd))
        stdoutpath = os.path.join(self.clonepath, 'runmutes.log')
        result = subprocess.run(antcmd, cwd=self.clonepath, shell=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        

        stdoutpath = os.path.join(self.clonepath, 'runmutes.log')
        with open(stdoutpath, 'a') as outfile:
            if result.returncode == 0:
                logging.info('Ran mutant {} for project {}'.format(mutantdir, self.projectname))
                # write ANT output
                outfile.write('Running mutant {} for project {}\n'.format(mutantdir, self.projectname))
                outfile.write(result.stdout)
                outfile.write(result.stderr)

                # was the mutant killed?
                return 'tests failed' in result.stderr.lower()
            else:
                msg = 'Project: {}. Error while running mutant: {}. See log file at {}' \
                      .format(self.projectname, mutantdir, stdoutpath) 
                logging.error(msg)
                outfile.write('Running mutant {} for project {}\n'.format(mutantdir, self.projectname))
                outfile.write(result.stdout)
                outfile.write(result.stderr)
                return None

    def __mutant_classes(self):
        # credit: https://stackoverflow.com/questions/4639506/os-walk-with-regex
        mutantdir_regexp = r'^[A-Z]{3,}_\d+'
        dirpath = os.path.join(self.clonepath, self.sessionname, 'result')
        mutated = []
        for root, _, files in os.walk(dirpath):
            for filename in files:
                dirname = os.path.basename(root)
                if filename.endswith('.class') and re.match(mutantdir_regexp, dirname):
                    mutant = (root, filename) 
                    mutated.append(mutant)
        return mutated

    def __javafiles(self, test=False, dirname='src'):
       src = os.path.join(self.clonepath, dirname)
       javafiles = []
       if dirname == 'src':
           expext = '.java'
       elif dirname == 'classes':
           expext = '.class'

       for root, _, files in os.walk(src):
           for filename in files:
               name, ext = os.path.splitext(filename)
               if ext == expext:
                   if test and name.endswith('Test'):
                       javafiles.append(os.path.join(root, filename))
                   elif not test and not name.endswith('Test'):
                       javafiles.append(os.path.join(root, filename))
       return javafiles

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Run mutation analysis using muJava on projects from a taskFile.'
        )
    parser.add_argument('taskfile', 
                        help='Path to an NDJSON file containing project tasks.\n\
                                Each task should have the key "projectPath", pointing \
                                to a project target for mutation.')
    parser.add_argument('-l', '--log', action='store_const', const=logging.INFO, 
                        default=logging.WARN, help='if given, sets log level to INFO')
    if sys.argv[1:]:
        args = parser.parse_args()
        loglevel = args.log
        logging.basicConfig(filename='.log', filemode='w', level=loglevel)
        taskfile = args.taskfile
        outerdir = os.path.normpath('/tmp/mujava-testing')
        with open(taskfile, 'r') as infile:
            for line in infile:
                task = json.loads(line)
                projectpath = task['projectPath']
                projectname = os.path.basename(projectpath)
                runner = MutationRunner(os.path.join(outerdir, projectname))
                output = runner.run()
                print(json.dumps(output))
    else:
        print('Error! Need a taskfile')
        parser.print_help()

