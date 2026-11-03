#!/usr/bin/env python3
"""Positive controls for the cardiac-inflammation gap/proposal task."""
import json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
from grade_gapproposal import grade
OUT = HERE / 'validation' / 'positive'

def p_conservative():
    P = RS.build(delta=3.4, sd=4.1, dsrc=['M21'], ssrc=['M08'], frac=0.330, fsrc=['M24'], nonev=0.124, nsrc=['M13', 'M24'], z=1.96 + 1.28)
    P['gap']['supporting_record_ids'] = ['M21', 'M22', 'M24']
    P['gap']['statement'] = 'Myocardial T2 has never been compared with biopsy inflammation in checkpoint-inhibitor patients, although validation in myocarditis, feasibility in these patients and biopsies all exist.'
    P['primary_endpoint']['unit'] = 'milliseconds'
    return P

def p_alternative():
    nonev = round(1 - (1 - 4 / 53) * (1 - 5 / 88), 4)
    P = RS.build(delta=4.3, sd=3.6, dsrc=['M03'], ssrc=['M13'], frac=36.1, fsrc=['M16'], nonev=nonev, nsrc=['M22', 'M16'])
    s = P['sample_size']; s['n_total_to_enrol'] = math.ceil(s['n_per_group'] / (0.361 * (1 - nonev)))
    P['evidence_audit']['replicated_findings'].append({'technique': 'T1', 'population': 'MYO', 'reference': 'BX', 'record_ids': ['M06', 'M12', 'M27'], 'finding': 'Native T1 measured within 3 days of biopsy is higher with active inflammation.'})
    P['evidence_audit']['contradictions'][0]['null_record_ids'] = ['M10', 'M17', 'M30', 'M35']
    P['controls'].append({'code': 'free_breathing_or_motion_corrected_acquisition', 'record_ids': ['M34'], 'justification': 'Breath-hold mapping fails with respiratory misregistration.'})
    P['controls'].append({'code': 'blood_pool_excluded_roi_placement', 'record_ids': ['M13', 'M03'], 'justification': 'Blood-pool partial volume biases myocardial T2.'})
    P['gap']['supporting_record_ids'] = ['M03', 'M11', 'M13', 'M24', 'M04', 'M02']
    return P

CONTROLS = [('conservative_inputs_rounded_z_additive_losses', p_conservative), ('alternative_valid_sources_and_extra_audit_entries', p_alternative)]

if __name__ == '__main__':
    res = []
    for name, f in CONTROLS:
        P = f(); d = OUT / name; RS.write(P, RS.to_md(P), d)
        g = grade(d)
        res.append({'control': name, 'overall_pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']},
                    'n_per_group': P['sample_size']['n_per_group'], 'n_total_to_enrol': P['sample_size']['n_total_to_enrol']})
    ok = all(r['overall_pass'] for r in res)
    (HERE / 'validation' / 'positive_controls.json').write_text(json.dumps({'all_positive_controls_pass': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r)
    print('ALL_OK', ok, len(res))

