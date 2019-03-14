import os
import sys
import subprocess

def run_for_project(projectpath):
    # assume that the project exists in the current WORKDIR
    # create mujavaCLI.config
    projectpath = os.path.abspath(projectpath)
    configpath = os.path.join(projectpath, 'mujavaCLI.config')
    with open(configpath, 'w') as f:
        f.write('MuJava_HOME={}'.format(os.path.normpath(projectpath)))
    
    compileproject(projectpath)
    genmutes('session', projectpath) 

def isjavasource(filename):
    name, ext = os.path.splitext(filename)
    return not name.endswith('Test') and ext == '.java'

def compileproject(projectpath):
    buildfile = os.path.abspath('build.xml')
    libdir = os.path.abspath('lib')
    antcmd = 'ant -f {} -Dresource_dir={} -Dbasedir={} clean compile' \
                .format(buildfile, libdir, projectpath) 
    subprocess.run(antcmd, shell=True)

def genmutes(sessionname, projectpath):
    srcdir = os.path.join(projectpath, 'src')
    srcfiles = ' '.join(filter(isjavasource, os.listdir(srcdir)))

    sessioncmd = 'java mujava.cli.testnew {} {}'.format(sessionname, srcfiles)
    subprocess.run(sessioncmd, cwd=projectpath, shell=True)

    # mv class files into place
    classpath = os.path.join(projectpath, 'classes')
    mvtestcmd = 'mv {}/*Test.class {}/testset/'.format(classpath, sessionname)
    mvsrccmd = 'mv {}/* {}/classes/'.format(classpath, sessionname)
    subprocess.run(mvtestcmd, cwd=projectpath, shell=True)
    subprocess.run(mvsrccmd, cwd=projectpath, shell=True)

    genmutescmd = 'java mujava.cli.genmutes -ror {}'.format(sessionname)
    result = subprocess.run(genmutescmd, stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE, cwd=projectpath, shell=True)

if __name__ == '__main__':
    arg = sys.argv[1]
    run_for_project(arg)
