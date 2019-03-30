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
    'BooleanTrueReturn',
    'BooleanFalseReturn',
    'PrimitiveReturns',
    'EmptyObjectReturn'
]

pit_sufficient = ['ABS', 'ROR', 'AOD', 'UOI']

pit_default = [
    'ConditionalsBoundary',
    'IncrementsMutator',
    'MathMutator',
    'NegateConditionals',
    'ReturnVals',
    'VoidMethodCall'
]
def mutator_in_subset(mutator, subset):
    return any([x in mutator for x in subset])

def main_subset_data(pit_mutations=None, submissions=None):
    """Get data for full, default, deletion, and sufficient operator
    subsets.

    Returns a DataFrame containing, for each main operator subset, in each project, 
    the coverage achieved, running time, efficiency, and the number of mutants
    (total and per loc).
    """
    if pit_mutations is None:
        pit_mutations = pd.read_csv(pit_mutations_path)
    if submissions is None:
        submissions = getsubmissions(webcat_path, list(pit_mutations.userName.unique()), ['Project 2'])
    
    deletion = pit_mutations.groupby('userName') \
                            .apply(data_for_subset, submissions, subset=pit_deletion, prefix='deletion')
    sufficient = pit_mutations.groupby('userName') \
                              .apply(data_for_subset, submissions, subset=pit_sufficient, prefix='sufficient')
    default = pit_mutations.groupby('userName') \
                           .apply(data_for_subset, submissions, subset=pit_default, prefix='default')
    full = pit_mutations.groupby('userName') \
                        .apply(data_for_subset, submissions, prefix='full')
    
    mutdata = deletion.merge(right=sufficient, right_index=True, left_index=True) \
                      .merge(right=default, right_index=True, left_index=True) \
                      .merge(right=full, right_index=True, left_index=True)
    
    # populate running time columns for each subset
    mutdata = __get_running_time('pit-all-results.ndjson', 'full_runningTime', mutdata)
    mutdata = __get_running_time('pit-default-results.ndjson', 'default_runningTime', mutdata)
    mutdata = __get_running_time('pit-deletion-results.ndjson', 'deletion_runningTime', mutdata)
    mutdata = __get_running_time('pit-sufficient-results.ndjson', 'sufficient_runningTime', mutdata)
    
    return mutdata.merge(right=submissions, right_index=True, left_index=True)

def __get_running_time(resultfile, colname, mutdata):
    with open(os.path.join(pit_results_path, resultfile)) as infile:
        for line in infile:
            result = json.loads(line)
            username = os.path.basename(result['projectPath'])
            runningtime = result['runningTime']
            mutdata.loc[username, colname] = runningtime
    return mutdata
    
def per_user_mutator_subset_data(subset, pit_mutations=None, submissions=None):
    """Get summary data for the specified subset, for each student."""
    if pit_mutations is None:
        pit_mutations = pd.read_csv(pit_mutations_path, index_col=['userName'])
    if submissions is None:
        submissions = getsubmissions(webcat_path, list(pit_mutations.userName.unique()), ['Project 2'])
    mutdata = pit_mutations.groupby('userName').apply(data_for_subset, submissions, subset)
    
    return mutdata

def data_for_subset(df, submissions, subset=None, prefix=''):
    """Gets number of mutants, coverage, survival, and efficiency for the given
    subset of mutation operators.
    
    This function acts on the given DataFrame without grouping by any fields. Can
    use this as a lambda in an outer split-apply operation.
    
    Args:
        df (pd.DataFrame): A dataframe of "raw" PIT mutations.csv data
        submissions (int, pd.DataFrame): Submissions 
        subset (list, default=None): A list of mutation operators in the subset, omit for
                                     all operators.
        prefix (str, default=''): A prefix for output items (prefix_num, prefix_cov, etc.)
    
    Returns:
        A Series or dict containing the obtained information, with keys prefixed by `prefix`.
    """
    username = df.name
    if subset is not None:
        df = df[df.apply(lambda r: mutator_in_subset(r.mutator, subset), axis=1)]

    if prefix:
        prefix = '{}_'.format(prefix)

    # compute subset specific data
    num = df.shape[0]
    cov = df.query('killed not in ["SURVIVED", "NO_COVERAGE"]').shape[0] / num
    survival = 1 - cov
    result = {
        '{}num'.format(prefix): num,
        '{}cov'.format(prefix): cov,
        '{}survival'.format(prefix): survival
    }
    
    if submissions is not None:
        loc = submissions.loc[username]['statements.nontest']
        eff = efficiency(num, loc, cov)
        mpl = num / loc
        result['{}eff'.format(prefix)] = eff
        result['{}mpl'.format(prefix)] = mpl
    
    return pd.Series(result)

def efficiency(mutantcount, loc, coverage):
    survival = 1 - coverage
    mpl = mutantcount / loc
    return survival / mpl

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

def get_mutator_specific_data(pit_mutations=None, joined=None):
    """Get characteristics of individual mutation operators,
    averaged across student projects.
    """
    if pit_mutations is None:
        pit_mutations = pd.read_csv(pit_mutations_path)
    pit_mutations['mutator'] = pit_mutations['mutator'].apply(clean_mutator_name)
    return pit_mutations.groupby(['userName', 'mutator']).apply(__mut_user_data, joined)

def all_mutator_data(mutators, measure):
    """Get the mean of mutator data across projects.""" 
    return mutators[measure].reset_index() \
                            .pivot(index='userName', columns='mutator', values=measure)
    
def __mut_user_data(mutations, joined):
    username, _ = mutations.name
    total = mutations.shape[0]
    survived = mutations.query('killed == "SURVIVED"').shape[0]
    killed = total - survived
    loc = joined.loc[username, 'statements.nontest']
    survival = survived / total
    coverage = killed / total
    mpl = total / loc
    return pd.Series({
        'num_mutants': total,
        'num_killed': killed,
        'coverage': coverage,
        'mutantsPerLoc': mpl,
        'efficiency': survival / mpl
    })

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

