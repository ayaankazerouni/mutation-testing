#! /usr/bin/env python3

"""Utility to aggregate PITest mutation data for several projects
into a CSV file for analysis.
"""
from os import listdir, path
import argparse
import pandas as pd

def get_mutation_coverage(resultspath, getseries=True):
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

            if getseries:
                return pd.Series(result)

            return result
    except FileNotFoundError:
        pass

    return None

def aggregate_mutation_results(dirpath):
    """
    Aggregate output from mutation testing by reading PITest reports.

    Args:
        dirpath (str): Path to the directory containing tested projects
    """
    if not path.isabs(dirpath):
        dirpath = path.abspath(dirpath)

    projects = listdir(dirpath)
    resultpaths = {}

    for proj in projects:
        projpath = path.join(dirpath, proj)
        mutationscsv = path.join(projpath, 'pitReports', 'mutations.csv')
        mutationshtml = path.join(projpath, 'pitReports', 'com.example')

        # are there mutation results to speak of?
        if path.isfile(mutationscsv) and path.isdir(mutationshtml):
            resultpaths[proj] = mutationscsv

    mutationcoverage = pd.Series(resultpaths).apply(get_mutation_coverage)
    mutationcoverage.index.name = 'userName'
    return mutationcoverage

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('input', help='Path to PIT testing output')
    PARSER.add_argument('output', help='Path to output CSV file')
    ARGS = PARSER.parse_args()

    INFILE = ARGS.input
    OUTFILE = ARGS.output

    RESULTS = aggregate_mutation_results(INFILE)
    RESULTS.to_csv(path_or_buf=OUTFILE, index=True)
