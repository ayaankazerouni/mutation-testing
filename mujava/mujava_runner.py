#! /usr/bin/env python3

import os
import sys
import json
import shutil
import subprocess

class MutationRunner:
    """Runs muJava mutation testing on a specified project.
    
    Class Attributes:
        deletion_mutator (str): Code for the statement deletion mutator.
        all_mutators (list): All mutation operators provided by muJava.
    """
    # class attributes
    deletion_mutator = 'SDL'
    all_mutators = 'ALL'
    
    def __init__(self, projectpath, mutators='all'):
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
        self.mujava_classpath = ('{libdir}/mujava-11.jar:{libdir}/openjava.jar:'
                                 '{libdir}/commons-io.jar:{libdir}/junit.jar:'
                                ).format(libdir=self.libpath)
    
    def run(self):
        # projects were cloned already; assume they exist at self.clonepath
        # create mujavaCLI.config
        configpath = os.path.join(self.clonepath, 'mujavaCLI.config')
        with open(configpath, 'w') as f:
            f.write('MuJava_HOME={}'.format(os.path.normpath(self.clonepath)))
        
        self.compileproject()
        sessionname = 'session'
        self.testsession(sessionname)
        # self.genmutes(sessionname) 

    def compileproject(self):
        antcmd = 'ant -f {} -Dresource_dir={} -Dbasedir={} clean compile' \
                    .format(self.antpath, self.libpath, self.clonepath) 
        subprocess.run(antcmd, shell=True)

    def testsession(self, sessionname):
        # make session directory structure
        sesh_srcpath = os.path.join(self.clonepath, sessionname, 'src')
        sesh_clspath = os.path.join(self.clonepath, sessionname, 'classes')
        sesh_tstpath = os.path.join(self.clonepath, sessionname, 'testset')
        sesh_resultpath = os.path.join(self.clonepath, sessionname, 'result')
        os.makedirs(sesh_srcpath)
        os.makedirs(sesh_clspath)
        os.makedirs(sesh_tstpath)
        os.makedirs(sesh_resultpath)

        # mv src files into place
        srcfiles = self.javafiles()
        for filepath in srcfiles:
            filename = os.path.basename(filepath)
            shutil.copy(filepath, os.path.join(sesh_srcpath, filename))

        # mv source class files into place
        classfiles = self.javafiles(dirname='classes')
        for filepath in classfiles:
            filename = os.path.basename(filepath)
            shutil.copy(filepath, os.path.join(sesh_clspath, filename))

        # mv test class files into place
        testfiles = self.javafiles(test=True, dirname='classes')
        for filepath in testfiles:
            filename = os.path.basename(filepath)
            shutil.copy(filepath, os.path.join(sesh_tstpath, filename))

    def genmutes(self, sessionname):
        # generate mutants
        genmutescmd = 'java -cp {} mujava.cli.genmutes -sdl {}'\
                      .format(self.mujava_classpath, sessionname)
        print('Generating mutants: {}'.format(genmutescmd))
        subprocess.run(genmutescmd, cwd=self.clonepath, shell=True)

    def javafiles(self, test=False, dirname='src'):
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
    outerdir = os.path.normpath('/tmp/mujava-testing')
    if not sys.argv[1:]:
        print('Error! Need a taskfile')
        sys.exit(1)

    taskfile = sys.argv[1]
    with open(taskfile, 'r') as infile:
        for line in infile:
            task = json.loads(line)
            projectpath = task['projectPath']
            projectname = os.path.basename(projectpath)
            runner = MutationRunner(os.path.join(outerdir, projectname))
            runner.run()

