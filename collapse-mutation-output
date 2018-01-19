#! /usr/bin/env python3

import argparse
import os
import sys
import pandas as pd

def collapse(group):
    killed = len(group[group['status'] == 'KILLED'])
    total = len(group)
    result = killed / total
    return pd.Series({ 'file': group.name, 'coverage': result })

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input',
        help='path to raw mutation testing output')
    parser.add_argument('output',
        help='path to CSV output (will be replaced if pre-existing')
    args = parser.parse_args()
    
    raw = pd.read_csv(args.input)
    groups = raw.groupby('class')
    results = groups.apply(collapse)
    results.to_csv(args.output, index=False)
