#! /usr/bin/env node

'use strict';

const path = require('path');
const fs = require('fs-extra');
const getopt = require('node-getopt');
const promisify = require('util-promisify');
const exec = promisify(require('child_process').exec);

var opts = getopt.create([
  ['p', 'projectPath=ARG', 'Path to a single Java project'],
  ['m', '', 'Is projectPath pointing to a directory with multiple projects?'],
  ['t', 'antTask=ARG', 'ANT task to run on project(s). Should be defined in the shared build.xml.'],
  ['o', 'suppressOut', 'Switch to suppress stdout'],
  ['e', 'suppressErr', 'Switch to suppress stderr'],
  ['h', 'help', 'Display this help']
])
.bindHelp()
.parseSystem();

const projectPath = opts.options['projectPath'];
const manyProjects = opts.options['m'];
const task = opts.options['antTask'] || 'run';
const suppressOut = opts.options['suppressOut'];
const suppressErr = opts.options['suppressErr'];

function testSingleProject(projectPath) {
  // copy the project to /tmp/ to avoid modifying the original
  const clonePath = path.join('/tmp/', projectPath); 
  const src = path.join(clonePath, 'src');
  const pkg = path.join(src, 'com', 'example');

  fs.copy(projectPath, clonePath)
  // Create artificial package structure so PIT doesn't try to mutate itself
  .then(() => {
    // Create src/com/example
    return fs.mkdirp(pkg);
  })
  .then(() => {
    // Move Java files into src/com/example
    return exec(`mv ${path.join(src, '*.java')} ${pkg}`);
  })
  .then(() => {
    // Add the package declaration to the top of Java files
    return exec(`sed -i '1ipackage com.example;' ${path.join(pkg, '*.java')}`);
  })
  .then(() => {
    // run ANT
    const antPath = path.join(__dirname, 'build.xml'); // path to shared build file
    const libPath = path.join(__dirname, 'lib'); // path to shared libraries required to test projects

    return exec(`ant -f ${antPath} -Dbasedir=${clonePath} -Dresource_dir=${libPath}  ${task}`); 
  })
  .then((result) => { // this is an object
    if (!suppressOut) console.log(`stdout: ${result.stdout}`);
    if (!suppressErr) console.log(`stderr: ${result.stderr || 'None'}`);
  })
  .catch((err) => {
    console.error(err); 
  });
}

if (manyProjects) {
  console.log('Processing multiple projects is not yet implemented.');
} else {
  testSingleProject(projectPath);
}
