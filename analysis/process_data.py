"""Utilities for managing mutation testing data."""
import os
import re
import sys
import json

import pandas as pd

modulepath = os.path.expanduser(os.path.join('~', 'Developer'))
if os.path.exists(modulepath) and modulepath not in sys.path:
    sys.path.append(modulepath)
from sensordata import consolidate_sensordata

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

def getsubmissions(webcat_path, users, assignments): 
    """Get Web-CAT submissions for the specified users on the specified assignments.""" 
    pluscols = ['statements', 'statements.test', 'statements.nontest', 
                'methods.test', 'methods.nontest']
    submissions = consolidate_sensordata \
            .load_submission_data(webcat_path, pluscols=pluscols) \
            .reset_index() \
            .query('userName in @users and assignment in @assignments')
    cols = ['userName', 'score.correctness', 'methods.test', 'methods.nontest', 
            'statements', 'statements.test', 'statements.nontest', 
            'elementsCovered']
    return submissions[cols].set_index('userName')

def get_mutator_specific_data(pit_mutations=None, submissions=None):
    """Get characteristics of individual mutation operators, for each project."""
    if pit_mutations is None:
        pit_mutations = pd.read_csv(pit_mutations_path)

    if submissions is None:
        submissions = getsubmissions(webcat_path=webcat_path, users=pit_mutations.userName.unique(),
                                     assignments=['Project 2'])
    pit_mutations['mutator'] = pit_mutations['mutator'].apply(clean_mutator_name)
    return pit_mutations.groupby(['userName', 'mutator']).apply(__mutator_specific_data_helper, submissions)

def __mutator_specific_data_helper(mutations, joined):
    username, _ = mutations.name
    total = mutations.shape[0]
    survived = mutations.query('killed == "SURVIVED"').shape[0]
    killed = total - survived
    loc = joined.loc[username, 'statements.nontest']
    survival = survived / total
    mpl = total / loc
    return pd.Series({
        'num_mutants': total,
        'num_killed': killed,
        'coverage': killed / total,
        'mutantsPerLoc': mpl,
        'efficiency': survival / mpl
    })

def get_data_for_subset(df, subset=None, submissions=None, prefix=''):
    """Get characteristic data for the specified subset.
    
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
    return df.groupby('userName').apply(aggregate_data, submissions, prefix)

def aggregate_data(df, submissions=None, prefix=''):
    username = df.name
    
    if prefix:
        prefix = '{}_'.format(prefix)
    
    num = df['num_mutants'].sum()
    cov = df['num_killed'].sum() / num
    result = {
        '{}num'.format(prefix): num,
        '{}cov'.format(prefix): cov,
    }
    
    if submissions is not None:
        loc = submissions.loc[username, 'statements.nontest']
        mpl = num / loc
        efficiency = (1 - cov) / mpl
        result['{}eff'.format(prefix)] = efficiency
        result['{}mpl'.format(prefix)] = mpl
    
    return pd.Series(result)

def all_mutator_data(mutators, measure):
    """Get a specific characteristic of all mutators.
    
    Use to format things for modelling.
    """ 
    return mutators[measure].reset_index() \
                            .pivot(index='userName', columns='mutator', values=measure)

def factorisedsubsets(df, dv):
    """Return a DataFrame with the operator subset as a factor. Use the result
    in an ANOVA. Basically converts the data from wide to long format.

    Takes as input a DataFrame as returned by get_mutator_data.
    """
    df = df.reset_index()
    deletion = 'deletion_{}'.format(dv)
    default = 'default_{}'.format(dv)
    sufficient = 'sufficient_{}'.format(dv)
    full = 'full_{}'.format(dv)
    result = df[['userName', deletion, default, sufficient, full]] \
        .melt(id_vars=['userName'], value_vars=[deletion, default, sufficient, full], 
              var_name='op_subset', value_name='value') \
        .set_index('userName')
    return result

def clean_mutator_name(name):
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

# mutdata.to_csv(os.path.join(pit_results_path, 'overall_results.csv'), index=True)

