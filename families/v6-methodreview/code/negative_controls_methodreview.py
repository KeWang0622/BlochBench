#!/usr/bin/env python3
"""Negative controls for the MS central-vein-sign methodological-review task."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
from grade_methodreview import grade
OUT = HERE / 'validation' / 'negative'
I = RS.ISSUES
PARA = json.loads((HERE / 'key.json').read_text())['paragraphs']

def drop(ids): return [x for x in I if x[0] not in ids]
def recat(m): return [(a, b, m.get(a, c), d, e, f) for a, b, c, d, e, f in I]

CONTROLS = [
 ('missed_two_planted_issues', 'recall_planted_issues', lambda: RS.build(drop({'K4', 'K6'}))),
 ('false_accusations_of_sound_decoys', 'false_accusations_limited', lambda: RS.build(I + [
   ('X1', 'P05', 'test_set_leakage_or_tuning', 'none of them took part in the present study', 'Leakage.', 'x'),
   ('X2', 'P12', 'multiple_comparisons_uncorrected', 'with Holm correction for the two tests', 'Many tests.', 'x'),
   ('X3', 'P07', 'inadequate_blinding', 'blinded to the clinical diagnosis and to the reconstruction method', 'Unblinded.', 'x')])),
 ('wrong_categories', 'recall_planted_issues', lambda: RS.build(recat({'K2': 'inappropriate_statistical_test', 'K2b': 'unsupported_causal_or_clinical_claim', 'K6': 'other_methodological'}))),
 ('fabricated_quote', 'quotes_verbatim', lambda: RS.build([(a, b, c, ('the checkpoint was tuned on the test patients' if a == 'K1' else d), e, f) for a, b, c, d, e, f in I])),
 ('nonexistent_paragraph_id', 'schema_valid', lambda: RS.build(I + [('X4', 'P29', 'other_methodological', 'validation on other vendors', 'x', 'y')])),
 ('lenient_recommendation', 'recommendation_consistent', lambda: RS.build(I, rec='accept')),
 ('category_outside_list', 'schema_valid', lambda: RS.build(recat({'K3': 'p_hacking'}))),
 ('shotgun_review_every_paragraph', 'false_accusations_limited', lambda: RS.build(I + [('S' + pid, pid, 'other_methodological', PARA[pid][:40], 'generic concern', 'clarify') for pid in ['P01', 'P02', 'P03', 'P04', 'P05', 'P07', 'P10', 'P13', 'P15', 'P22', 'P23', 'P25']])),
 ('issues_at_wrong_location', 'recall_planted_issues', lambda: RS.build([(a, ('P04' if a in ('K4', 'K5', 'K6') else b), c, ('each acquired once fully sampled and once with threefold' if a in ('K4', 'K5', 'K6') else d), e, f) for a, b, c, d, e, f in I])),
]

if __name__ == '__main__':
    res = []
    for name, target, f in CONTROLS:
        R = f(); d = OUT / name; RS.write(R, RS.to_md(R), d)
        g = grade(d); failed = [k for k, v in g['checks'].items() if not v['pass']]
        res.append({'control': name, 'targeted_check': target, 'targeted_failed': target in failed, 'overall_pass': g['all_automated_checks_pass'], 'failed_checks': failed})
    ok = all(r['targeted_failed'] and not r['overall_pass'] for r in res)
    (HERE / 'validation' / 'negative_controls.json').write_text(json.dumps({'all_negative_controls_behave': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r['control'], r['targeted_failed'], r['failed_checks'])
    print('ALL_OK', ok, len(res))

