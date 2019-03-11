#! /usr/bin/env python3 
"""Miscellaneous utilities."""
import os
import sys
import argparse
import subprocess
from shutil import rmtree, copytree
import pandas as pd

def get_mutation_coverage(resultspath):
    """Gets mutation coverage for the project at resultspath."""
    names = ['fileName', 'className', 'mutator', 'method', 'lineNumber', \
            'status', 'killingTest']
    try:
        mutations = pd.read_csv(resultspath, names=names)
        if not mutations.empty:
            killed = ['KILLED', 'TIMED_OUT'] # pylint: disable=unused-variable
            nkilled = len(mutations.query('status in @killed'))
            nsurvived = len(mutations) - nkilled
            coverage = nkilled / len(mutations)

            result = {
                'mutants': len(mutations),
                'survived': nsurvived,
                'killed': nkilled,
                'mutationCovered': coverage
            }

            return result
    except FileNotFoundError:
        pass

    return None

def __combiner(resultspath):
    return pd.Series(get_mutation_coverage(resultspath))

def aggregate_mutation_results(dirpath):
    """
    Aggregate output from mutation testing by reading PITest reports.

    Args:
        dirpath (str): Path to the directory containing tested projects
    """
    if not os.path.isabs(dirpath):
        dirpath = os.path.abspath(dirpath)

    projects = os.listdir(dirpath)
    resultpaths = {}

    for proj in projects:
        projpath = os.path.join(dirpath, proj)
        mutationscsv = os.path.join(projpath, 'pitReports', 'mutations.csv')
        mutationshtml = os.path.join(projpath, 'pitReports', 'com.example')

        # are there mutation results to speak of?
        if os.path.isfile(mutationscsv) and os.path.isdir(mutationshtml):
            resultpaths[proj] = mutationscsv

    mutationcoverage = pd.Series(resultpaths).apply(__combiner)
    mutationcoverage.index.name = 'userName'
    return mutationcoverage

def clone_with_package_structure(projectpath, clonepath):
    """Copy the project at projectpath to the specified
    clonepath, to avoid modifying the source data. Also create
    an artificial package structure (i.e., com.example) to appease
    PIT.
    """
    # Copy the project to /tmp/ to avoid modifying the original
    if os.path.exists(clonepath) and os.path.isdir(clonepath):
        rmtree(clonepath)
    copytree(projectpath, clonepath)

    # Create com.example package structure
    pkg = os.path.join(clonepath, 'src', 'com', 'example', '')
    os.makedirs(pkg)

    # Move Java files directly under src into src/com/example
    mvcmd = 'mv {javafiles} {package}' \
            .format(javafiles=os.path.join(clonepath, 'src', '*.java'), package=pkg)
    subprocess.run(mvcmd, shell=True).check_returncode()

    # Add package declaration to the top of Java files
    sedcmd = 'gsed' if sys.platform == 'darwin' else 'sed' # requires GNU sed on macOS
    sedcmd = sedcmd + " -i '1ipackage com.example;' {javafiles}" \
            .format(javafiles=os.path.join(pkg, '*.java'))
    try:
        subprocess.run(sedcmd, shell=True).check_returncode()
    except subprocess.CalledProcessError as err:
        if err.returncode == 127 and sys.platform == 'darwin':
            logging.error(('If you are on macOS, please install the GNU '
                           'sed extension "gsed". To install: brew install gsed'))
        sys.exit(0)
