#! /usr/bin/env python3 
"""Miscellaneous utilities for managing PIT output."""
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
        print("Couldn't find output")
        pass

    return None

def __combiner(resultspath):
    return pd.Series(get_mutation_coverage(resultspath))

def aggregate_mutation_results(dirpath, aggregate=False):
    """
    Aggregate output from mutation testing by reading PITest reports.

    Args:
        dirpath (str): Path to the directory containing tested projects
        aggregate (bool): Summarise each student's mutation score or return
                          data for all mutants?
    """
    if not os.path.isabs(dirpath):
        dirpath = os.path.abspath(dirpath)

    projects = os.listdir(dirpath)
    resultpaths = {}

    results = []

    for proj in projects:
        projpath = os.path.join(dirpath, proj)
        mutationscsv = os.path.join(projpath, 'pitReports', 'mutations.csv')
        mutationshtml = os.path.join(projpath, 'pitReports', 'com.example')

        # are there mutation results to speak of?
        if os.path.isfile(mutationscsv) and os.path.isdir(mutationshtml):
            if aggregate:
                results.append(pd.read_csv(mutationscsv))
            else:
                resultpaths[proj] = mutationscsv
    
    if aggregate:
        return pd.concat(results)

    mutationcoverage = pd.Series(resultpaths).apply(__combiner)
    mutationcoverage.index.name = 'userName'
    return mutationcoverage

