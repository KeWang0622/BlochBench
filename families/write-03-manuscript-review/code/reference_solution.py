#!/usr/bin/env python3
"""Reference solution for the MS central-vein-sign methodological-review task."""
import json, sys, platform
from pathlib import Path
HERE = Path(__file__).resolve().parent
OUT = HERE / 'validation' / 'reference'

ISSUES = [
 ('K1', 'P06', 'test_set_leakage_or_tuning', 'highest agreement with the expert CVS consensus reads of the 118 study patients',
  'The checkpoint and denoising weight were tuned on the evaluation cohort and its reference reads, so agreement and accuracy are optimistically biased.', 'Fix the model on the external training data or tune on a separate validation set.'),
 ('K2', 'P11', 'statistical_unit_pseudoreplication', 'each lesion counted as an independent observation',
  'Lesions of one participant are clustered; pooling them inflates n and significance.', 'Compare participant-level proportions or use a mixed model.'),
 ('K2b', 'P19', 'statistical_unit_pseudoreplication', '1,084 of 1,562 lesions, 69%, vs 81 of 497, 16%; p < 0.001, chi-square test',
  'The p value treats about 2,000 clustered lesions as independent.', 'Analyse at the participant level.'),
 ('K3', 'P09', 'inappropriate_statistical_test', 'was assessed with the Pearson correlation coefficient',
  'Correlation measures association, not agreement; systematic differences go undetected.', 'Use Bland-Altman analysis or an agreement ICC.'),
 ('K3b', 'P17', 'inappropriate_statistical_test', 'demonstrating that DL-FLAIR* and conventional FLAIR* can be used interchangeably',
  'A high correlation does not demonstrate interchangeability.', 'Report bias and limits of agreement.'),
 ('K4', 'P14', 'text_table_inconsistency', '71 received a final diagnosis of MS and 47 had a mimic',
  'Table 1 lists 68 participants with MS and 50 with mimics (32 with small vessel disease).', 'Reconcile the counts.'),
 ('K5', 'P21', 'unit_error', 'Median total FLAIR lesion volume was 6.8 mm3',
  'Table 3 gives the same values in mL; a total lesion volume of a few cubic millimetres is implausible.', 'Report lesion volume in mL.'),
 ('K6', 'P16', 'undefined_or_post_hoc_exclusion', 'were classified as indeterminate and removed from the accuracy analysis',
  'Removing borderline participants after comparison with the reference inflates sensitivity and specificity.', 'Include all participants or use a prespecified indeterminate category reported separately.'),
 ('K7', 'P08', 'circular_analysis', 'we analysed only lesions in which the senior neuroradiologist had marked a central vein on DL-FLAIR*',
  'Selecting lesions by a visible vein on one reconstruction guarantees 100% visibility for that reconstruction and biases the comparison.', 'Compare vein visibility on all lesions or on lesions selected independently of both reconstructions.'),
 ('K7b', 'P18', 'circular_analysis', 'DL-FLAIR* depicted 36% more central veins than the conventional reconstruction',
  'The difference is created by the selection rule.', 'Repeat on an unbiased lesion sample.'),
 ('K8', 'P24', 'unsupported_causal_or_clinical_claim', 'makes lumbar puncture and follow-up MRI unnecessary',
  'A diagnostic accuracy study in one referral cohort cannot show that other diagnostic tests or criteria can be dropped.', 'Restrict the conclusion to diagnostic accuracy and call for prospective impact studies.'),
]

def build(issues=ISSUES, rec='major_revision'):
    return {'recommendation': rec, 'summary': 'Useful acceleration, but tuning on the study cohort, lesion-level pseudoreplication, correlation used as agreement, circular lesion selection, post hoc exclusion of indeterminate cases, count and unit errors and an unsupported clinical claim must be addressed.',
            'issues': [{'issue_id': a, 'paragraph_id': b, 'category': c, 'quote': d, 'justification': e, 'suggested_fix': f} for a, b, c, d, e, f in issues],
            'limitations': ['Review based on the manuscript text only; no access to data or code.']}

def to_md(R):
    L = ['# Referee report', '', f"Recommendation: {R['recommendation']}", '', R['summary'], '', '## Issues', '']
    for i in R['issues']:
        L += [f"- [{i['paragraph_id']}] ({i['category']}) \"{i['quote']}\": {i['justification']} Fix: {i['suggested_fix']}"]
    L += ['', '## Limitations of this review', ''] + [f'- {x}' for x in R['limitations']] + ['']
    return '\n'.join(L)

def write(R, md, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'review.json').write_text(json.dumps(R, indent=1) + '\n'); (out / 'review.md').write_text(md)
    (out / 'environment.txt').write_text(f'python {platform.python_version()}\n')

if __name__ == '__main__':
    R = build(); write(R, to_md(R), OUT)
    sys.path.insert(0, str(HERE)); from grade_methodreview import grade
    g = grade(OUT)
    (OUT.parent / 'reference_grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']}, 'recall': g['measurements'].get('recall')}))

