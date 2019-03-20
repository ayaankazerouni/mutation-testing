#! /usr/bin/env python3

import os
import re
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess

class MutationRunner:
    """Runs muJava mutation testing on a specified project.
    
    Class Attributes:
        deletion_mutator (str): Code for the statement deletion mutator.
        all_mutators (list): All mutation operators provided by muJava.
    """
    # class attributes
    all_mutators = 'all'
    deletion_mutator = 'sdl'
    sessionname = 'session'
    
    def __init__(self, projectpath, mutators='deletion'):
        self.projectpath = os.path.normpath(projectpath)
        self.projectname = os.path.basename(self.projectpath)
        self.clonepath = os.path.join('/tmp/mujava-testing', self.projectname, '')
        if mutators == 'all':
            self.mutators = self.all_mutators
        elif mutators == 'deletion':
            self.mutators = [self.deletion_mutator]
        else:
            raise ValueError('Mutators must be "all" or "deletion"')

        cwd = os.getcwd()
        self.antpath = os.path.join(cwd, 'build.xml')
        self.libpath = os.path.join(cwd, 'lib')
        self.mujava_classpath = ('{libdir}/mujava.jar:{libdir}/openjava.jar:'
                                 '{libdir}/commons-io.jar:{libdir}/junit.jar:'
                                 '{libdir}/student.jar:$JAVA_HOME/lib/tools.jar'
                                ).format(libdir=self.libpath)
    
    def run(self):
        """Create the muJava config file and run mutation testing 
        on the current project.
        """
        # projects were cloned already; assume they exist at self.clonepath
        # create mujavaCLI.config
        configpath = os.path.join(self.clonepath, 'mujavaCLI.config')
        with open(configpath, 'w') as f:
            f.write('MuJava_HOME={}'.format(os.path.normpath(self.clonepath)))
        
        self.compileproject()
        self.setup_test_session()
        self.genmutes() 
        self.runmutes()

    def compileproject(self):
        """Compile the project using ANT."""
        antcmd = 'ant -f {} -Dresource_dir={} -Dbasedir={} clean compile' \
                    .format(self.antpath, self.libpath, self.clonepath) 
        logging.info('Compiling: {}'.format(antcmd)) 
        result = subprocess.run(antcmd, shell=True, stderr=subprocess.PIPE, 
                                stdout=subprocess.PIPE)
        if result.returncode == 0:
            logging.info(result.stdout)
        else:
            logging.error(result.stdout)
            logging.error(result.stderr)

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
        """Use muJava to generated mutants."""
        # generate mutants
        mutators = ' '.join(list(map(lambda m: '-{}'.format(m), self.mutators)))
        start = time.time()
        genmutescmd = 'java -cp {} mujava.cli.genmutes {} {}'\
                      .format(self.mujava_classpath, mutators, self.sessionname)
        logging.info('Generating mutants: {}'.format(genmutescmd))
        result = subprocess.run(genmutescmd, cwd=self.clonepath, shell=True,
                                stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        runningtime = time.time() - start
        if result.returncode == 0:
            logging.info(result.stdout)
        else:
            logging.error(result.stdout)
            logging.error(result.stderr)    
        self.gentime = runningtime

    def runmutes(self):
        # original class files
        original = os.path.join(self.clonepath, 'classes')

        # find mutated class files 
        mutated = self.__mutant_classes()
        count = 0
        for mutantdir, mutantclass in mutated:
            if count < 10:
                self.__runmutant(mutantdir, mutantclass)
                count = count + 1
            else:
                break

    def __runmutant(self, mutantdir, mutantclass):
        mutantdir = "'{}'".format(mutantdir)
        antcmd = (
                    'ant -f {} -Dbasedir={} -Dresource_dir={} -Dmutant_class={} '
                    '-Dmutant_dir={} run'
                 ).format(self.antpath, self.clonepath, self.libpath, \
                          mutantclass, mutantdir)
        subprocess.run(antcmd, shell=True)

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
                runner.run()
                result = { 'projectPath': projectpath, 'genTime': runner.gentime }
                print(json.dumps(result))
    else:
        print('Error! Need a taskfile')
        parser.print_help()

