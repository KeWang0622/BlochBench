#!/usr/bin/env python3
"""Positive controls for the MS central-vein-sign methodological-review task."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
from grade_methodreview import grade
OUT = HERE / 'validation' / 'positive'

ALT = [
 ('A1', 'P06', 'test_set_leakage_or_tuning', 'The final network checkpoint and the denoising weight', 'Tuned on the evaluation cohort.', 'Use a separate validation set.'),
 ('A2', 'P19', 'statistical_unit_pseudoreplication', '[P19] CVS-positive lesions were more frequent in MS than in mimics', 'Lesions analysed as independent.', 'Participant level.'),
 ('A3', 'P17', 'inappropriate_statistical_test', 'Pearson r = 0.96, p < 0.001', 'Correlation is not agreement.', 'Bland-Altman.'),
 ('A4', 'T1', 'text_table_inconsistency', '| Participants | 68 | 50 |', 'Differs from 71/47 in P14.', 'Reconcile.'),
 ('A5', 'P21', 'text_table_inconsistency', '1.9 MM3 (IQR 0.8-3.6) in mimics', 'Table 3 gives volumes in mL.', 'Use mL.'),
 ('A6', 'P16', 'undefined_or_post_hoc_exclusion', 'leaving 109 participants', 'Post hoc exclusion.', 'Prespecify.'),
 ('A7', 'P18', 'circular_analysis', 'Among the selected lesions, a central vein was also seen', 'Selection on the DL result.', 'Unbiased sample.'),
 ('A8', 'P24', 'missing_reference_standard', 'should replace the McDonald criteria in routine practice', 'No study against the full diagnostic work-up.', 'Diagnostic impact study.'),
 ('A9', 'P20', 'undefined_or_post_hoc_exclusion', 'in the 109 participants analysed', 'Computed after the exclusions.', 'Repeat with all participants.'),
 ('A10', 'P23', 'unsupported_causal_or_clinical_claim', 'with good inter-reader agreement for the CVS', 'Overstated.', 'Qualify.'),
]

CONTROLS = [('alternative_locations_categories_two_false_accusations', lambda: RS.build(ALT, rec='reject')),
            ('seven_of_eight_found', lambda: RS.build([x for x in RS.ISSUES if x[0] not in ('K3', 'K3b')]))]

if __name__ == '__main__':
    res = []
    for name, f in CONTROLS:
        R = f(); d = OUT / name; RS.write(R, RS.to_md(R), d)
        g = grade(d)
        res.append({'control': name, 'overall_pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']}, 'recall': g['measurements']['recall'], 'false_accusations': g['measurements']['false_accusations']})
    ok = all(r['overall_pass'] for r in res)
    (HERE / 'validation' / 'positive_controls.json').write_text(json.dumps({'all_positive_controls_pass': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r)
    print('ALL_OK', ok, len(res))

