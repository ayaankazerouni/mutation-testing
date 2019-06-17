"""Utilities for managing mutation testing data."""
import os
import re
import sys
import json

import pandas as pd

modulepath = os.path.expanduser(os.path.join('~', 'Developer'))
if os.path.exists(modulepath) and modulepath not in sys.path:
    sys.path.append(modulepath)
from sensordata import load_datasets   

pit_results_path = os.path.join(modulepath, 'mutation-testing', 'data', 'icer-2019', 'pit')
pit_mutations_path = os.path.join(pit_results_path, 'mutations.csv')
webcat_path = os.path.join(modulepath, 'sensordata', 'data', 'fall-2016', 'web-cat-3114-fall-2016.csv')

pit_deletion = [
    'RemoveConditional',
    'VoidMethodCall',
    'NonVoidMethodCall',
    'ConstructorCall',
    'BooleanTrueReturnVals',
    'BooleanFalseReturnVals',
    'PrimitiveReturns',
    'EmptyObjectReturnVals'
]

pit_sufficient = ['ABS', 'ROR', 'AOD', 'UOI']

pit_default = [
    'ConditionalsBoundary',
    'Increments',
    'Math',
    'NegateConditionals',
    'ReturnVals',
    'VoidMethodCall'
]

pit_full = [
    'ABS',
    'AOD',
    'AOR',
    'BooleanFalseReturnVals',
    'BooleanTrueReturnVals',
    'CRCR',
    'ConditionalsBoundary',
    'ConstructorCall',
    'EmptyObjectReturnVals',
    'Increments',
    'InlineConstant',
    'Math',
    'NegateConditionals',
    'NonVoidMethodCall',
    'PrimitiveReturns',
    'ROR',
    'RemoveConditional',
    'ReturnVals',
    'UOI',
    'VoidMethodCall'
]

def getsubmissions(webcat_path, keepassignments=[], users=None): 
    """Get Web-CAT submissions for the specified users on the specified assignments.""" 
    pluscols = ['statements', 'statements.test', 'statements.nontest', 
                'methods.test', 'methods.nontest', 'conditionals.nontest']
    submissions = load_datasets.load_submission_data(webcat_path, pluscols=pluscols, 
                    keepassignments=keepassignments).reset_index()
    if users is not None:
        submissions = submissions.query('userName in @users')
    cols = ['userName', 'assignment', 'score', 'methods.test', 'methods.nontest', 'statements', 
            'statements.test', 'statements.nontest', 'elementsCovered', 'conditionals.nontest']
    return submissions[cols].set_index(['userName', 'assignment'])

def get_mutator_specific_data(pit_mutations=None, submissions=None, **kwargs):
    """Get characteristics of individual mutation operators, for each project."""
    if pit_mutations is None:
        pit_mutations = pd.read_csv(pit_mutations_path)

    if submissions is None:
        assignments = kwargs.get('assignments', ['Project 2'])
        subpath = kwargs.get('webcat_path', webcat_path)
        submissions = getsubmissions(webcat_path=subpath, users=pit_mutations.userName.unique(),
                                     assignments=assignments)
    pit_mutations['mutator'] = pit_mutations['mutator'].apply(__clean_mutator_name)
    return pit_mutations.groupby(['userName', 'assignment', 'mutator']).apply(__mutator_specific_data_helper, submissions)

def __mutator_specific_data_helper(mutations, submissions):
    username, assignment, _ = mutations.name
    if (username, assignment) not in submissions.index:
        return None

    total = mutations.shape[0]
    survived = mutations.query('killed == "SURVIVED"').shape[0]
    killed = total - survived
    loc = submissions.loc[(username, assignment), 'statements.nontest']
    survival = survived / total
    mpl = total / loc
    return pd.Series({
        'num': total,
        'killed': killed,
        'cov': killed / total,
        'surv': survived / total,
        'mpl': mpl,
        'eff': survival / mpl
    })

def get_running_time(resultfile):
    """Get running time from the NDJSON file at `resultfile`."""
    results = {}
    with open(os.path.abspath(resultfile)) as infile:
        for line in infile:
            result = json.loads(line)
            username = os.path.basename(result['projectPath'])
            runningtime = result['runningTime']
            results[username] = runningtime
    return pd.Series(results)

def get_main_subset_data(mutators, submissions, running_time_paths=None):
    """Gets aggregate data for the main subsets: deletion, default, sufficient, full.
    
    Args:
        mutators (pd.DataFrame): Per-mutator, per-project data, as returned by 
                                 `get_mutator_specific_data`
        submissions (pd.DataFrame): Submission data for student projects, as 
                                    returned by `getsubmissions`
        running_time_paths (str): Paths to ndjson files containing running time information
                                  for the main subsets 
    
    Returns:
        A DataFrame containing columns {subset}_cov, {subset}_surv, {subset}_mpl, 
        {subset}_num, and {subset}_runningTime, where subset is each of the main subsets.
    """
    deletion = get_data_for_subset(mutators, submissions=submissions, subset=pit_deletion, prefix='deletion')
    default = get_data_for_subset(mutators, submissions=submissions, subset=pit_default, prefix='default')
    sufficient = get_data_for_subset(mutators, submissions=submissions, subset=pit_sufficient, 
                                     prefix='sufficient')
    full = get_data_for_subset(mutators, submissions=submissions, prefix='full')
    joined = deletion.merge(right=default, right_index=True, left_index=True) \
                     .merge(right=sufficient, right_index=True, left_index=True) \
                     .merge(right=full, right_index=True, left_index=True)

    if running_time_paths:
        # main subsets
        for filename in os.listdir(pit_results_path):
            name, ext = os.path.splitext(filename)
            if ext != '.ndjson':
                continue
            
            # main subsets
            if  name.startswith('pit'):
                subset = name.split('-')[1]
            elif name.startswith('inc'):
                subset = ''.join(name.split('-')[:2])
            else: 
                continue

            filepath = os.path.join(pit_results_path, filename)
            joined['{}_runningtime'.format(subset)] = get_running_time(resultfile=filepath)
    
    return joined

def get_data_for_subset(df, subset=None, submissions=None, prefix=''):
    """Get characteristic data for the specified subset.
    Acts on data as returned by `get_mutator_specific_data`.
    
    Args:
        subset (list): A list of mutation operators
        submissions (pd.DataFrame): Web-CAT submissions. Required for
                                    efficiency and mutants per loc
    
    Returns:
        A DataFrame containing columns "{prefix}_{measure}", where measure
        is num, cov, eff, and mpl
    """
    df = df.reset_index()
    if subset is not None:
        df = df.query('mutator in @subset')
    result = df.groupby(['userName', 'assignment']) \
               .apply(aggregate_data, submissions, prefix)
    if isinstance(result, pd.Series):
        result = result.unstack()

    return result

def aggregate_data(df, submissions=None, prefix=''):
    idx = df.name
    
    if prefix:
        prefix = '{}_'.format(prefix)
    
    num = df['num'].sum()
    cov = df['killed'].sum() / num
    surv = 1 - cov
    result = {
        '{}num'.format(prefix): num,
        '{}cov'.format(prefix): cov,
        '{}surv'.format(prefix): surv
    }
    
    if submissions is not None and idx in submissions.index:
        loc = submissions.loc[idx, 'statements.nontest']
        mpl = num / loc
        efficiency = surv / mpl
        result['{}eff'.format(prefix)] = efficiency
        result['{}mpl'.format(prefix)] = mpl
    
    return pd.Series(result)

def all_mutator_data(mutators, measure):
    """Get a specific characteristic of all mutators.
    
    Use to format things for modelling.

    Args:
        mutators (pd.DataFrame): A DataFrame as returned by :meth:`get_mutator_specific_data`
    """ 
    return mutators[measure].unstack()

def factorisedsubsets(df, dv):
    """Return a DataFrame with the operator subset as a factor. Use the result
    in an ANOVA. Basically converts the data from wide to long format.

    Takes as input a DataFrame as returned by get_mutator_data.
    """
    valuecols = list(df.filter(regex='_{}$'.format(dv)).columns)
    df = df.reset_index()
    result = df[['userName'] + valuecols] \
        .melt(id_vars=['userName'], value_vars=valuecols,
              var_name='subset', value_name=dv) \
        .set_index('userName')
    result['subset'] = result['subset'].apply(__clean_subset_name)
    return result

def __clean_subset_name(n):
    if n.startswith('deletion'):
        return 'Deletion'
    if n.startswith('sufficient'):
        return 'Sufficient'
    if n.startswith('full'):
        return 'Full'

    return n

def __clean_mutator_name(name):
    """Sanitise mutation operator names."""
    # some mutants are prefixed and have subtypes, e.g., AOR1Mutator, CRCR5Mutator, etc.
    prefixes = ['AOR', 'AOD', 'ROR', 'UOI', 'OBBN', 'CRCR', 'RemoveConditional']
    name = name.split('.')[-1]
    if any([name.startswith(x) for x in prefixes]):
        match = re.match(r'^(\w+)\d+', name)
        if match:
            name = match.groups()[0]
        else:
            name = 'RemoveConditional'
    name = name.split('Mutator')[0]
    return name

