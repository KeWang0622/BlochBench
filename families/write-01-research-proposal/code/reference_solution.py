#!/usr/bin/env python3
"""Reference solution for the cardiac-inflammation gap/proposal task."""
import json, math, sys, platform
from pathlib import Path
from scipy.stats import norm
HERE = Path(__file__).resolve().parent
OUT = HERE / 'validation' / 'reference'

GROUPS = {'M03': [(33, 3.6), (45, 3.1)], 'M08': [(28, 4.1), (36, 3.4)], 'M14': [(41, 3.9), (55, 3.2)], 'M21': [(30, 3.7), (40, 3.3)]}
DELTA = {'M03': (78, 4.3), 'M08': (64, 4.4), 'M14': (96, 5.4), 'M21': (70, 3.4)}
POWER = 0.9


def n_formula(delta, sd, alpha=0.05, power=POWER, z=None):
    zz = z if z is not None else norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return 2 * zz * zz * sd * sd / (delta * delta)


def build(delta=None, sd=None, dsrc=None, ssrc=None, frac=None, fsrc=None, nonev=None, nsrc=None, z=None):
    if delta is None:
        delta = round(sum(n * d for n, d in DELTA.values()) / sum(n for n, _ in DELTA.values()), 2); dsrc = ['M03', 'M08', 'M14', 'M21']
    if sd is None:
        num = sum((n - 1) * s * s for g in GROUPS.values() for n, s in g); den = sum(n - 1 for g in GROUPS.values() for n, _ in g)
        sd = round(math.sqrt(num / den), 2); ssrc = ['M03', 'M08', 'M14', 'M21']
    if frac is None:
        frac = round((30 + 29) / (83 + 88), 4); fsrc = ['M16', 'M24']
    if nonev is None:
        nonev = round(1 - (1 - (4 + 4) / (80 + 53)) * (1 - (5 + 7) / (88 + 95)), 4); nsrc = ['M13', 'M22', 'M16', 'M24']
    npg = math.ceil(n_formula(delta, sd, z=z))
    ntot = math.ceil(npg / (frac * (1 - nonev)))
    return {
     'evidence_audit': {
      'replicated_findings': [{'technique': 'T2', 'population': 'MYO', 'reference': 'BX', 'record_ids': ['M03', 'M08', 'M14', 'M21'],
                               'finding': 'Myocardial T2 is higher with active inflammation on endomyocardial biopsy than without in suspected acute myocarditis (differences 3.4-5.4 ms).'}],
      'contradictions': [{'technique': 'T1', 'population': 'MYO', 'reference': 'BX', 'significant_record_ids': ['M06', 'M12', 'M27'], 'null_record_ids': ['M10', 'M17', 'M30'],
                          'explaining_factor': 'mri_to_biopsy_interval',
                          'explanation': 'All significant studies performed MRI within 3 days of the biopsy, all null studies 14 to 30 days after it; field strength, vendor, T1 sequence (MOLLI or ShMOLLI), slice thickness and sample size are mixed across both sets, and ROI placement and histology criteria are identical. Native T1 falls quickly after the acute phase, so late MRI no longer reflects the inflammation present at biopsy.',
                          'explanation_support_ids': ['M35']}],
      'underpowered_claims': [{'record_id': 'M19', 'dependent_record_ids': ['M28', 'M32'], 'reason': 'Significant difference with groups of 7 and 9.'},
                              {'record_id': 'M33', 'dependent_record_ids': ['M26'], 'reason': 'Significant correlation without groups in only 22 participants (fewer than 30).'}]},
     'gap': {'technique': 'T2', 'population': 'ICI', 'reference': 'BX',
             'statement': 'Myocardial T2 has been validated against biopsy inflammation in suspected myocarditis and in recent-onset dilated cardiomyopathy without contradiction, is technically feasible in patients receiving immune checkpoint inhibitors, and endomyocardial biopsies are obtained in this population, but no study has related T2 to biopsy inflammation in these patients.',
             'supporting_record_ids': ['M03', 'M08', 'M14', 'M21', 'M11', 'M13', 'M22', 'M16', 'M24']},
     'hypothesis': {'statement': 'In patients receiving immune checkpoint inhibitors with suspected myocarditis, myocardial T2 is higher with active inflammation on endomyocardial biopsy than without.', 'direction': 'higher'},
     'primary_endpoint': {'name': 'global myocardial T2', 'technique': 'T2', 'unit': 'ms', 'definition': 'Mean T2 from T2-prepared bSSFP mapping at 1.5 T in mid-wall ROIs excluding blood pool on three short-axis slices, after 48 h without strenuous exercise and before corticosteroids, measured blinded to histology.',
                          'reference': 'BX', 'reference_positive_definition': 'at least 14 leukocytes/mm2 including at least 7 CD3+ T lymphocytes/mm2 on an adequate endomyocardial biopsy'},
     'design': {'type': 'prospective_cross_sectional', 'unit_of_analysis': 'participant', 'recruitment': 'consecutive',
                'description': 'Consecutive patients receiving immune checkpoint inhibitors who are referred for endomyocardial biopsy for suspected myocarditis undergo T2 mapping within 3 days before biopsy and before corticosteroids.'},
     'sample_size': {'alpha': 0.05, 'power': POWER, 'sided': 2, 'target_difference': delta, 'target_difference_source_ids': dsrc, 'sd': sd, 'sd_source_ids': ssrc,
                     'n_per_group': npg, 'smaller_group_fraction': frac, 'smaller_group_fraction_source_ids': fsrc, 'nonevaluable_fraction': nonev,
                     'nonevaluable_fraction_source_ids': nsrc, 'n_total_to_enrol': ntot, 'formula': 'n = ceil(2 (z0.975 + z0.90)^2 SD^2 / Delta^2); N = ceil(n / (fraction * (1 - nonevaluable)))'},
     'controls': [
      {'code': 'blinded_image_analysis', 'record_ids': [], 'justification': 'Readers blinded to histology.'},
      {'code': 'exercise_abstinence_before_mri', 'record_ids': ['M04'], 'justification': 'Endurance exercise raises myocardial T2 by 2.1 ms.'},
      {'code': 'corticosteroid_timing_control', 'record_ids': ['M23'], 'justification': 'High-dose corticosteroids lower T2 within days, independently of the inflammation at biopsy.'},
      {'code': 'fixed_field_strength_and_sequence', 'record_ids': ['M02'], 'justification': 'T2 depends on field strength and sequence.'},
      {'code': 'mri_close_in_time_to_reference', 'record_ids': ['M16', 'M24', 'M35'], 'justification': 'MRI within 3 days of biopsy; mapping values normalise within weeks.'},
      {'code': 'consecutive_recruitment', 'record_ids': [], 'justification': 'Avoid spectrum bias.'}],
     'risks': [{'risk': 'Fewer inflamed biopsies than expected.', 'mitigation': 'Monitor the fraction and extend recruitment.'},
               {'risk': 'Non-analysable T2 maps.', 'mitigation': 'Repeat acquisitions and inflated enrolment.'}],
     'limitations': ['Target difference transferred from myocarditis and dilated cardiomyopathy; checkpoint-inhibitor myocarditis may differ.', 'Biopsy sampling error.']}


def to_md(P):
    s = P['sample_size']; g = P['gap']
    L = ['# Proposal: myocardial T2 and biopsy inflammation in patients receiving immune checkpoint inhibitors', '', '## Evidence audit', '',
         'Replicated: myocardial T2 is higher with active inflammation on biopsy in suspected acute myocarditis [M03] [M08] [M14] [M21].',
         'Contradiction: native T1 versus biopsy inflammation in suspected myocarditis is significant in [M06] [M12] [M27] and null in [M10] [M17] [M30]; only the significant studies scanned within 3 days of the biopsy, consistent with the rapid normalisation shown in [M35].',
         'Underpowered: [M19] (7 vs 9), on which [M28] and [M32] depend, and [M33] (correlation in 22 participants), on which [M26] depends.', '',
         '## Gap', '', g['statement'] + ' Support: ' + ' '.join(f'[{i}]' for i in g['supporting_record_ids']) + '.', '',
         '## Hypothesis', '', P['hypothesis']['statement'], '', '## Primary endpoint', '', P['primary_endpoint']['definition'], '',
         '## Design', '', P['design']['description'], '', '## Sample size', '',
         f"Two-sided alpha 0.05, power {s['power']}, Delta = {s['target_difference']} ms, SD = {s['sd']} ms: n per group = {s['n_per_group']}. "
         f"With a smaller-group fraction of {s['smaller_group_fraction']} and a non-evaluable fraction of {s['nonevaluable_fraction']}, total to enrol = {s['n_total_to_enrol']}.", '',
         '## Controls', ''] + [f"- {c['code']}: {c['justification']} " + ' '.join(f'[{i}]' for i in c['record_ids']) for c in P['controls']] + [
         '', '## Risks', ''] + [f"- {r['risk']} Mitigation: {r['mitigation']}" for r in P['risks']] + ['', '## Limitations', ''] + [f'- {x}' for x in P['limitations']] + ['']
    return '\n'.join(L)


def write(P, md, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'proposal.json').write_text(json.dumps(P, indent=1) + '\n'); (out / 'proposal.md').write_text(md)
    (out / 'environment.txt').write_text(f'python {platform.python_version()}\n')


if __name__ == '__main__':
    P = build(); write(P, to_md(P), OUT)
    sys.path.insert(0, str(HERE)); from grade_gapproposal import grade
    g = grade(OUT)
    (OUT.parent / 'reference_grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']}, 'n': [P['sample_size'][k] for k in ('target_difference', 'sd', 'n_per_group', 'smaller_group_fraction', 'nonevaluable_fraction', 'n_total_to_enrol')]}))

