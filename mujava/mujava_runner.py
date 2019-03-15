import os
import sys
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
    
    def run(self):
        # projects were cloned already; assume they exist at self.clonepath
        # create mujavaCLI.config
        configpath = os.path.join(self.clonepath, 'mujavaCLI.config')
        with open(configpath, 'w') as f:
            f.write('MuJava_HOME={}'.format(os.path.normpath(self.clonepath)))
        
        self.compileproject()
        self.genmutes('session') 


    def compileproject(self):
        antcmd = 'ant -f {} -Dresource_dir={} -Dbasedir={} clean compile' \
                    .format(self.antpath, self.libpath, self.clonepath) 
        subprocess.run(antcmd, shell=True)

    def genmutes(self, sessionname):
        srcdir = os.path.join(self.clonepath, 'src')
        srcfiles = ' '.join(filter(isjavasource, os.listdir(srcdir)))

        sessioncmd = 'java mujava.cli.testnew {} {}'.format(sessionname, srcfiles)
        subprocess.run(sessioncmd, cwd=self.clonepath, shell=True)

        # mv class files into place
        classpath = os.path.join(self.clonepath, 'classes')
        mvtestcmd = 'mv {}/*Test.class {}/testset/'.format(classpath, sessionname)
        mvsrccmd = 'mv {}/* {}/classes/'.format(classpath, sessionname)
        subprocess.run(mvtestcmd, cwd=self.clonepath, shell=True)
        subprocess.run(mvsrccmd, cwd=self.clonepath, shell=True)

        genmutescmd = 'java mujava.cli.genmutes -ror {}'.format(sessionname)
        result = subprocess.run(genmutescmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                cwd=self.clonepath, shell=True)

def isjavasource(filename):
    name, ext = os.path.splitext(filename)
    return not name.endswith('Test') and ext == '.java'

if __name__ == '__main__':
    outerdir = os.path.normpath('/tmp/mujava-testing')
    for project in os.listdir(outerdir):
        runner = MutationRunner(os.path.join(outerdir, project))
        runner.run()

