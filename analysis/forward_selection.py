"""Simple implementation of forward selection using statsmodels."""
import sys
import pandas as pd
import statsmodels.formula.api as smf
import utils

class CandidateModel:
    def __init__(self, score, candidate, model, cost, coverage):
        self.score = score 
        self.candidate = candidate 
        self.model = model 
        self.cost = cost 
        self.coverage = coverage 

def forward_selection(data, response, mutators=None, full_num=None, del_num=None):
    """Linear model designed by forward selection.
    Credit: https://planspace.org/20150423-forward_selection_with_statsmodels/
    """
    candidates = list(data.columns)
    candidates.remove(response)
    print('{} data points'.format(len(data)))
    print('Initial candidates: {}'.format(candidates))
    initial_mutators = len(candidates)
    selected = []
    maxint = sys.maxsize
    current_score = maxint
    best = None
    
    models = []
    while candidates and (best is None or current_score == best.score):
        scores_with_candidates = []
        for candidate in candidates:
            features = selected + [candidate]
            formula = '{} ~ {} + 1'.format(response, ' + '.join(features))
            cost = None
            coverage = None
            if full_num is not None:
                subset_data = utils.get_data_for_subset(mutators, subset=features)
                subset_data = subset_data.loc[data.index]
                cost = subset_data['num'].sum()
                coverage = (subset_data['cov'].mean(), subset_data['cov'].std())
            model = smf.ols(formula, data=data).fit()
            score = model.bic
            candidate_model = CandidateModel(score, candidate, model, cost, coverage)
            scores_with_candidates.append(candidate_model)
       
        # sort by cost
        if full_num is not None:
            scores_with_candidates = sorted(scores_with_candidates, key=lambda c: c.cost)
        # sort by score
        scores_with_candidates = sorted(scores_with_candidates, key=lambda c: c.score)
        
        best = scores_with_candidates[0]
        if current_score > best.score:
            candidates.remove(best.candidate)
            selected.append(best.candidate)
            current_score = best.score 
            print('Add {}.'.format(best.candidate))
            if best.cost is not None:
                print('\t{:.2%} of FULL.'.format(best.cost / full_num), end=' ')
                if del_num is not None:
                    print('{:.2%} of DELETION.'.format(best.cost / del_num))
                print('\tCoverage: {}'.format(best.coverage))
            print('\tR^2 = {:.2%}.'.format(best.model.rsquared_adj))
            models.append(best.model)

    print('Selected {} / {} mutators'.format(len(selected), initial_mutators))
    
    return models, selected

