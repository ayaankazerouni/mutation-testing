import os
import sys
import shutil
import subprocess

class MutationRunner:
    """Runs muJava mutation testing on a specified project.
    
    Class Attributes:
        deletion_mutator (str): Code for the statement deletion mutator.
        all_mutators (list): All mutation operators provided by muJava.
    """
    # class attributes
    #TODO: Populate this list entirely
    deletion_mutator = 'SDL'
    all_mutators = [ 'ROR' ]

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
        self.mujava_classpath = '{libdir}/mujava.jar:{libdir}/openjava.jar:{libdir}/commons-io.jar:{libdir}/junit.jar:$JAVA_HOME/lib/tools.jar'\
                                .format(libdir=self.libpath)
    
    def run(self):
        # projects were cloned already; assume they exist at self.clonepath
        # create mujavaCLI.config
        configpath = os.path.join(self.clonepath, 'mujavaCLI.config')
        with open(configpath, 'w') as f:
            f.write('MuJava_HOME={}'.format(os.path.normpath(self.clonepath)))
        
        self.compileproject()
        sessionname = 'session'
        self.testsession(sessionname)
        self.genmutes(sessionname) 

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

        # mv src and class files into place
        srcfiles = self.srcfiles()
        for filepath in srcfiles:
            filename = os.path.basename(filepath)
            shutil.copy(filepath, os.path.join(sesh_srcpath, filename))

        classpath = os.path.join(self.clonepath, 'classes')
        mvtestcmd = 'mv {}/*Test.class {}/testset/'.format(classpath, sessionname)
        mvsrccmd = 'mv {}/* {}/classes/'.format(classpath, sessionname)
        subprocess.run(mvtestcmd, cwd=self.clonepath, shell=True)
        subprocess.run(mvsrccmd, cwd=self.clonepath, shell=True)

    def genmutes(self, sessionname):
        # generate mutants
        genmutescmd = 'java -cp {} mujava.cli.genmutes -all {}'\
                      .format(self.mujava_classpath, sessionname)
        print('Generating mutants: {}'.format(genmutescmd))
        subprocess.run(genmutescmd, cwd=self.clonepath, shell=True)

    def srcfiles(self):
       src = os.path.join(self.clonepath, 'src')
       srcfiles = []
       for root, _, files in os.walk(src):
           for filename in files:
               name, ext = os.path.splitext(filename)
               if ext == '.java' and not name.endswith('Test'):
                   srcfiles.append(os.path.join(root, filename))
       return srcfiles
            
if __name__ == '__main__':
    outerdir = os.path.normpath('/tmp/mujava-testing')
    for project in os.listdir(outerdir):
        runner = MutationRunner(os.path.join(outerdir, project))
        runner.run()

