#!/usr/bin/env python3
"""Positive controls for heldout-v6-pilotdesign: valid alternatives that must pass."""
import json, math, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
import pilot_stats as S
from grade_pilotdesign import grade
OUT = HERE / 'validation' / 'positive'
NE = RS.TASK['nonevaluable_fraction']
AP = RS.TASK['studies_to_design']['group_difference']['alpha']; PW = RS.TASK['studies_to_design']['group_difference']['power']

def exact_t_welch_centered():
    D = RS.solve(exact_t=True, ci_variant='welch')
    ep = S.endpoint_tr(S.read_csv(RS.INP / 'pilot_test_retest.csv'))
    wc, wcci, _, _ = S.wsd(ep, centered=True)
    r = D['repeatability']; r.update({'within_subject_sd': round(wc, 2), 'within_subject_sd_ci95': [round(x, 2) for x in wcci], 'repeatability_coefficient': round(2.77 * wc, 2),
                                      'icc': round(S.icc21(ep)[0], 2), 'icc_ci95': [round(x, 2) for x in S.icc21(ep)[1]], 'icc_form': 'ICC(A,1)'})
    d = np.array([v[2] - v[1] for v in ep.values()]); sdd = float(np.std(d, ddof=1))
    A = D['designs']['acute_challenge']; A['sd_used'] = round(sdd, 2)
    A['n_evaluable'] = S.n_paired_t(sdd, A['effect'], AP, PW); A['n_enrol'] = math.ceil(A['n_evaluable'] / (1 - NE))
    return D

def conservative_rounding():
    D = RS.solve()
    A = D['designs']['acute_challenge']; A['n_enrol'] = A['n_enrol'] + 1
    G = D['designs']['group_difference']; G['sd_used'] = round(G['sd_used'], 2); G['n_evaluable_per_group'] = S.n_two_z(G['sd_used'], G['effect'], AP, PW) ; G['n_enrol_per_group'] = math.ceil(G['n_evaluable_per_group'] / (1 - NE))
    D['repeatability']['icc_form'] = 'Shrout-Fleiss ICC(2,1)'
    D['pilot_group_comparison']['mean_difference_ci95'] = [round(x, 1) for x in D['pilot_group_comparison']['mean_difference_ci95']]
    return D

CONTROLS = [('exact_t_welch_ci_centered_wsd_two_decimal_icc', exact_t_welch_centered), ('normal_approx_rounded_inputs_conservative_enrolment', conservative_rounding)]

if __name__ == '__main__':
    res = []
    for name, f in CONTROLS:
        D = f(); d = OUT / name; RS.write(D, RS.to_md(D), d)
        g = grade(d)
        res.append({'control': name, 'overall_pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']},
                    'acute': [D['designs']['acute_challenge']['n_evaluable'], D['designs']['acute_challenge']['n_enrol']], 'group': [D['designs']['group_difference']['n_evaluable_per_group'], D['designs']['group_difference']['n_enrol_per_group']]})
    ok = all(r['overall_pass'] for r in res)
    (HERE / 'validation' / 'positive_controls.json').write_text(json.dumps({'all_positive_controls_pass': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r)
    print('ALL_OK', ok, len(res))

