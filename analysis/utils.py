"""Utilities for managing mutation testing data."""
import os
import re
import sys
import json
import glob

import pandas as pd

modulepath = os.path.expanduser(os.path.join('~', 'Developer'))
if os.path.exists(modulepath) and modulepath not in sys.path:
    sys.path.append(modulepath)
from sensordata import load_datasets   

pit_deletion = [
    'RemoveConditional',
    'VoidMethodCall',
    'NonVoidMethodCall',
    'ConstructorCall',
    'AOD',
    'OBBN2', 'OBBN3',
    'MemberVariable'
]

pit_sufficient = [
        'ABS', 
        'ROR',
        'AOR',
        'UOI'
    ]

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
    'AOR2', 'AOR3', 'AOR4',
    'BooleanTrueReturnVals',
    'CRCR',
    'RemoveConditional',
    'ConstructorCall',
    'EmptyObjectReturnVals',
    'Increments',
    'InlineConstant',
    'Math',
    'NonVoidMethodCall',
    'ROR',
    'ReturnVals',
    'UOI',
    'VoidMethodCall',
    'MemberVariable',
    'Switch'
]

has_sub_mutators = [
    'AOD', 'AOR', 'ROR', 'CRCR', 'OBBN', 'UOI'
]

def getsubmissions(webcat_path, keepassignments=[], users=None): 
    """Get Web-CAT submissions for the specified users on the specified assignments.""" 
    pluscols = ['statements', 'statements.test', 'statements.nontest', 
                'methods.test', 'methods.nontest', 'conditionals.nontest']
    submissions = load_datasets.load_submission_data(webcat_path, pluscols=pluscols, 
                    keepassignments=keepassignments).reset_index()
    submissions['assignment'] = submissions['assignment'] \
            .apply(lambda a: re.search(r'Project \d', a).group())
    if users is not None:
        submissions = submissions.query('userName in @users')
    cols = ['userName', 'assignment', 'score', 'methods.test', 'methods.nontest', 'statements', 
            'statements.test', 'statements.nontest', 'elementsCovered', 'conditionals.nontest']
    return submissions[cols].set_index(['userName', 'assignment'])

def get_mutator_specific_data(pit_mutations, submissions=None, **kwargs):
    """Get characteristics of individual mutation operators, for each project."""
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
    mpl = total / loc
    return pd.Series({
        'num': total,
        'killed': killed,
        'cov': killed / total,
        'mpl': mpl
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

def get_main_subset_data(mutators, submissions):
    """Gets aggregate data for the main subsets: deletion, default, sufficient, full.
    
    Args:
        mutators (pd.DataFrame): Per-mutator, per-project data, as returned by 
                                 `get_mutator_specific_data`
        submissions (pd.DataFrame): Submission data for student projects, as 
                                    returned by `getsubmissions`
    
    Returns:
        A DataFrame containing columns {subset}_cov, {subset}_surv, {subset}_mpl, 
        {subset}_num, and {subset}_runningTime, where subset is each of the main subsets.
    """
    deletion = get_data_for_subset(mutators, submissions=submissions, subset=pit_deletion, prefix='deletion')
    default = get_data_for_subset(mutators, submissions=submissions, subset=pit_default, prefix='default')
    sufficient = get_data_for_subset(mutators, submissions=submissions, subset=pit_sufficient, 
                                     prefix='sufficient')
    full = get_data_for_subset(mutators, submissions=submissions, subset=pit_full, prefix='full')
    joined = deletion.merge(right=default, right_index=True, left_index=True) \
                     .merge(right=sufficient, right_index=True, left_index=True) \
                     .merge(right=full, right_index=True, left_index=True)

    return joined

def get_data_for_subset(df, subset=None, submissions=None, prefix=''):
    """Get characteristic data for the specified subset.
    Acts on data as returned by `get_mutator_specific_data`.
    
    Args:
        df (pd.DataFrame): Mutator specific data
        subset (list): A list of mutation operators
        submissions (pd.DataFrame): Web-CAT submissions. Required for
                                    efficiency and mutants per loc
    
    Returns:
        A DataFrame containing columns "{prefix}_{measure}", where measure
        is num, cov, eff, and mpl
    """
    df = df.reset_index()
    if subset is not None:
        r = '|'.join(['^{}'.format(m) for m in subset])
        df = df[df.mutator.str.match(r)]
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
    result = {
        '{}num'.format(prefix): num,
        '{}cov'.format(prefix): cov,
    }
    
    if submissions is not None and idx in submissions.index:
        loc = submissions.loc[idx, 'statements.nontest']
        mpl = num / loc
        result['{}mpl'.format(prefix)] = mpl
    
    return pd.Series(result)

def mutator_coverage_for_subset(mutators, subset=None):
    """Get a specific characteristic of all mutators.
    
    Use to format things for modelling.

    Args:
        mutators (pd.DataFrame): A DataFrame as returned by :meth:`get_mutator_specific_data`
    """
    mutators = mutators.reset_index()
    coverages = mutators.groupby(['userName', 'assignment']).apply(get_coverage_for_mutators, subset=subset)

    return coverages 

def get_coverage_for_mutators(df, subset=None):
    covs = {}
    done = []
    subset = subset or pit_full
    for item in subset:
        op = re.match(r'([a-zA-Z]+)\d*', item).groups()[0]
        if op in done:
            continue
        opdata = df[df.mutator.str.match(r'^{}'.format(op))]
        covs[op] = opdata['killed'].sum() / opdata['num'].sum()
        done.append(op)
    return pd.Series(covs)

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
    prefixes = ['AOD', 'ROR', 'UOI', 'OBBN', 'CRCR']
    name = name.split('.')[-1]
    name = name.split('Mutator')[0]
    if name in prefixes:
        match = re.match(r'^(\w+)\d$', name)
        if match:
            name = match.groups()[0]
    return name

def load_mutation_data(term, course, project):
    outerdir = '../data/icse-seet/{}/{}/p{}'.format(course, term, project)
    mutation_csvs = glob.glob('{outerdir}/*/pitReports/mutations.csv'.format(outerdir=outerdir))
    webcat_path = glob.glob('/home/ayaankazerouni/Developer/sensordata/data/{}/{}/submissions.csv' \
            .format(course, term))

    pit_mutations = []
    columns = pit_results_header
    for datafile in mutation_csvs:
        assignment = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(datafile))))
        if '2114' in datafile and assignment == 'p1':
            continue
        course_name = 'CS 2114' if '2114' in datafile else 'CS 3114'
        try:
            username = os.path.dirname(os.path.dirname(datafile))
            assignment = 'Project {}'.format(os.path.basename(os.path.dirname(username))[1])
            username = os.path.basename(username)
            userdata = pd.read_csv(datafile, names=columns)
            userdata['userName'] = username
            userdata['assignment'] = assignment
            pit_mutations.append(userdata)
            del userdata
        except pd.errors.EmptyDataError:
            pass
    pit_mutations = pd.concat(pit_mutations, sort=False).set_index(['userName', 'assignment'])
    pit_mutations['mutator'] = pit_mutations['mutator'].apply(__clean_mutator_name) 
    print('Loaded {} mutations'.format(pit_mutations.shape[0]))

    submissions = pd.concat([getsubmissions(webcat_path=p) for p in webcat_path], sort=False,
                            ignore_index=False)
    if project != '*':
        submissions = submissions.xs(key='Project {}'.format(project[0]), level='assignment', drop_level=False)
    print('Loaded submissions')

    mutators = get_mutator_specific_data(pit_mutations=pit_mutations, submissions=submissions)
    print('Got mutator specific data. Getting main subsets...')
    joined = get_main_subset_data(mutators, submissions=submissions)
    print('Done. {} data points'.format(joined.shape[0]))
    
    return (mutators, joined, submissions)

