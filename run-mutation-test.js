#! /usr/bin/env node

/*
 * Author: Ayaan Kazerouni <ayaan@vt.edu>
 * Description: Run mutation analysis on a single project.
 *
 * Overview:
 *  - Copy project to /tmp/
 *  - Create artificial package structure for the project so that
 *    PIT doesn't try to mutate itself
 *  - Run PIT from the ANT build file (assumed to be in the current directory)
 * 
 * Dependencies:
 *  - npm install fs-extra, util-promisify
 *  - or simple npm install if you have package.json or package-lock.json
 */

'use strict';

const path = require('path');
const fs = require('fs-extra');
const promisify = require('util-promisify');
const exec = promisify(require('child_process').exec);
const traverseList = promisify(require('fs-tree-traverse').list);

const argFile = process.argv[2];
if (!argFile) {
  console.error('Error, no args :-(');
  process.exit(1);
}

const opts = JSON.parse(fs.readFileSync(argFile, 'utf-8'));
const projectPath = opts.projectPath;
const task = opts.task;
const suppressOut = opts.suppressOut;
const suppressErr = opts.suppressErr;

function testSingleProject(projectPath) {
  // copy the project to /tmp/ to avoid modifying the original
  const clonePath = path.join('/tmp/mutation-testing', path.basename(projectPath)); 
  const src = path.join(clonePath, 'src');
  const pkg = path.join(src, 'com', 'example');

  fs.copy(projectPath, clonePath)
  // Create artificial package structure for items in the default package
  // so PIT doesn't try to mutate itself
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
    return traverseList(src, { relative: true } );
  })
  .then((dirTree) => {
    // Compute packages to point PIT at
    var dirs = dirTree.map(p => path.dirname(p)); 
    var targetClasses = [];
    var targetTests = [];
    
    dirs = [...new Set(dirs)]; // unique 
    dirs.forEach(d => {
      d = d.replace("/", ".");
      var packageName;
      if (d.endsWith(".")) {
        packageName = `${d}*`; 
      } else {
        packageName = `${d}.*`; 
      }

      targetClasses.push(packageName);
      targetTests.push(`${packageName}Test*`);
    })

    targetClasses = targetClasses.join(",");
    targetTests = targetTests.join(",");

    // run ANT
    const antPath = path.join(__dirname, 'build.xml'); // path to shared build file
    const libPath = path.join(__dirname, 'lib'); // path to shared libraries 

    return exec(`ant -f ${antPath} -Dbasedir=${clonePath} -Dresource_dir=${libPath} -Dtarget_classes=${targetClasses} -Dtarget_tests=${targetTests} ${task}`); 
  })
  .then((result) => { // this is an object
    if (!suppressOut) console.log(`stdout: ${result.stdout.toString()}`);
    if (!suppressErr) console.log(`stderr: ${result.stderr || 'None'}`);
  })
  .catch((err) => {
    console.error(err); 
  });
}

try {
  testSingleProject(projectPath);
} catch(error) {
  console.error(error);
}
