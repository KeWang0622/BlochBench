#!/usr/bin/env python3
"""Negative controls for heldout-v6-pilotdesign."""
import copy, json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
import pilot_stats as S
from grade_pilotdesign import grade
OUT = HERE / 'validation' / 'negative'
NE = RS.TASK['nonevaluable_fraction']
AP = RS.TASK['studies_to_design']['group_difference']['alpha']; PW = RS.TASK['studies_to_design']['group_difference']['power']

def no_inflation():
    D = RS.solve(); D['designs']['acute_challenge']['n_enrol'] = D['designs']['acute_challenge']['n_evaluable']; return D
def no_factor_two():
    D = RS.solve(); G = D['designs']['group_difference']
    G['n_evaluable_per_group'] = math.ceil((S.zsum(AP, PW) * G['sd_used'] / G['effect']) ** 2); G['n_enrol_per_group'] = math.ceil(G['n_evaluable_per_group'] / (1 - NE)); return D
def rc_without_sqrt2():
    D = RS.solve(); D['repeatability']['repeatability_coefficient'] = round(1.96 * D['repeatability']['within_subject_sd'], 3); return D
def pilot_effect_used():
    D = RS.solve(); G = D['designs']['group_difference']; eff = abs(D['pilot_group_comparison']['mean_difference'])
    G['n_evaluable_per_group'] = S.n_two_z(G['sd_used'], eff, AP, PW); G['n_enrol_per_group'] = math.ceil(G['n_evaluable_per_group'] / (1 - NE)); return D
def welch_wrong_sign():
    D = RS.solve(); pg = D['pilot_group_comparison']; pg['mean_difference'] = -pg['mean_difference']; pg['mean_difference_ci95'] = sorted(-x for x in pg['mean_difference_ci95']); return D

CONTROLS = [
 ('knee_as_statistical_unit', 'unit_of_analysis_participant', lambda: RS.solve(unit='knee')),
 ('qc_rule_ignored', 'qc_exclusions_applied', lambda: RS.solve(qc=False)),
 ('acute_challenge_as_parallel_groups', 'acute_design_correct', lambda: RS.solve(acute_paired=False, acute_sd='between')),
 ('within_subject_sd_used_as_sd_of_differences', 'acute_sample_size_correct', lambda: RS.solve(acute_sd='wsd')),
 ('group_design_with_test_retest_sd', 'group_design_correct', lambda: RS.solve(group_sd='wsd')),
 ('no_nonevaluable_inflation', 'acute_sample_size_correct', no_inflation),
 ('group_formula_missing_factor_two', 'group_sample_size_correct', no_factor_two),
 ('icc_on_single_knee_values', 'icc_correct', lambda: RS.solve(icc_hemi=True)),
 ('repeatability_coefficient_without_sqrt2', 'repeatability_coefficient_correct', rc_without_sqrt2),
 ('observed_pilot_effect_instead_of_stated_effect', 'group_sample_size_correct', pilot_effect_used),
 ('group_difference_sign_reversed', 'pilot_group_estimates_correct', welch_wrong_sign),
]

if __name__ == '__main__':
    res = []
    for name, target, f in CONTROLS:
        D = f(); d = OUT / name; RS.write(D, RS.to_md(D), d)
        g = grade(d); failed = [k for k, v in g['checks'].items() if not v['pass']]
        res.append({'control': name, 'targeted_check': target, 'targeted_failed': target in failed, 'overall_pass': g['all_automated_checks_pass'], 'failed_checks': failed})
    ok = all(r['targeted_failed'] and not r['overall_pass'] for r in res)
    (HERE / 'validation' / 'negative_controls.json').write_text(json.dumps({'all_negative_controls_behave': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r['control'], r['targeted_failed'], r['failed_checks'])
    print('ALL_OK', ok, len(res))

