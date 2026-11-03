#!/usr/bin/env python3
"""Negative controls for the cardiac-inflammation gap/proposal task."""
import copy, json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
from grade_gapproposal import grade
OUT = HERE / 'validation' / 'negative'

def recompute(P, sided_one=False):
    s = P['sample_size']; zz = None
    if sided_one:
        from scipy.stats import norm; zz = norm.ppf(0.95) + norm.ppf(RS.POWER)
    s['n_per_group'] = math.ceil(RS.n_formula(s['target_difference'], s['sd'], z=zz))
    s['n_total_to_enrol'] = math.ceil(s['n_per_group'] / (s['smaller_group_fraction'] * (1 - s['nonevaluable_fraction'])))
    return P
def c_gap(P):
    P['gap'].update({'technique': 'STRAIN', 'population': 'ICI', 'reference': 'EVENT', 'supporting_record_ids': ['M19', 'M01', 'M05'], 'statement': 'Strain predicts events in cardiac sarcoidosis, so it should predict outcomes in checkpoint-inhibitor myocarditis.'}); return P
def c_fab(P):
    P['controls'][1]['record_ids'] = ['M04', 'M36']; P['_md'] = 'Exercise effects are well known (Smith et al., 2020; https://example.org).'; return P
def c_unit(P): P['design']['unit_of_analysis'] = 'roi'; return P
def c_hvdiff(P): P['sample_size'].update({'target_difference': 4.2, 'target_difference_source_ids': ['M22']}); return recompute(P)
def c_formula(P):
    s = P['sample_size']; s['n_per_group'] = math.ceil(RS.n_formula(s['target_difference'], s['sd']) / 2)
    s['n_total_to_enrol'] = math.ceil(s['n_per_group'] / (s['smaller_group_fraction'] * (1 - s['nonevaluable_fraction']))); return P
def c_wsd(P): P['sample_size'].update({'sd': 1.2, 'sd_source_ids': ['M13']}); return recompute(P)
def c_prev(P):
    s = P['sample_size']; s['n_total_to_enrol'] = math.ceil(2 * s['n_per_group'] / (1 - s['nonevaluable_fraction'])); return P
def c_factor(P): P['evidence_audit']['contradictions'][0]['explaining_factor'] = 'field_strength'; return P
def c_missed(P): P['evidence_audit']['underpowered_claims'] = P['evidence_audit']['underpowered_claims'][:1]; return P
def c_dep(P): P['evidence_audit']['underpowered_claims'][0]['dependent_record_ids'] = ['M28']; return P
def c_hyd(P): P['controls'] = [c for c in P['controls'] if c['code'] != 'exercise_abstinence_before_mri']; return P
def c_sup(P): P['gap']['supporting_record_ids'] = P['gap']['supporting_record_ids'] + ['M33']; return P
def c_rep(P): P['evidence_audit']['replicated_findings'][0]['record_ids'].append('M33'); return P
def c_one(P): P['sample_size']['sided'] = 1; return recompute(P, sided_one=True)
def c_loss(P): P['sample_size'].update({'nonevaluable_fraction': 0.05, 'nonevaluable_fraction_source_ids': ['M13']}); return recompute(P)
def c_ctl(P): P['controls'][3]['record_ids'] = ['M02', 'M05']; return P
def c_hvsd(P): P['sample_size'].update({'sd': 2.6, 'sd_source_ids': ['M22']}); return recompute(P)

CONTROLS = [
 ('overclaimed_strain_gap', 'gap_identified', c_gap), ('fabricated_citation', 'citations_within_corpus', c_fab), ('wrong_statistical_unit_roi', 'design_correct', c_unit),
 ('effect_from_healthy_volunteer_comparison', 'sample_size_inputs_valid', c_hvdiff), ('formula_missing_factor_two', 'sample_size_arithmetic', c_formula),
 ('test_retest_sd_used_as_between_subject_sd', 'sample_size_inputs_valid', c_wsd), ('ignored_smaller_group_fraction', 'sample_size_arithmetic', c_prev),
 ('wrong_contradiction_factor', 'contradiction_correct', c_factor), ('missed_underpowered_record', 'underpowered_claims_correct', c_missed),
 ('missed_dependent_record', 'underpowered_claims_correct', c_dep), ('missing_exercise_control', 'controls_required_present', c_hyd),
 ('underpowered_record_used_as_support', 'gap_support_valid', c_sup), ('underpowered_record_counted_as_replication', 'replicated_finding_correct', c_rep),
 ('one_sided_test', 'sample_size_inputs_valid', c_one), ('mri_failure_only_nonevaluable', 'recruitment_inputs_valid', c_loss),
 ('control_with_unrelated_record', 'controls_support_valid', c_ctl), ('healthy_volunteer_sd_used', 'sample_size_inputs_valid', c_hvsd),
]

if __name__ == '__main__':
    res = []
    for name, target, f in CONTROLS:
        P = f(copy.deepcopy(RS.build())); extra = P.pop('_md', '')
        md = RS.to_md(P) + ('\n' + extra + '\n' if extra else '')
        d = OUT / name; RS.write(P, md, d)
        g = grade(d); failed = [k for k, v in g['checks'].items() if not v['pass']]
        res.append({'control': name, 'targeted_check': target, 'targeted_failed': target in failed, 'overall_pass': g['all_automated_checks_pass'], 'failed_checks': failed})
    ok = all(r['targeted_failed'] and not r['overall_pass'] for r in res)
    (HERE / 'validation' / 'negative_controls.json').write_text(json.dumps({'all_negative_controls_behave': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r['control'], r['targeted_failed'], r['failed_checks'])
    print('ALL_OK', ok, len(res))

