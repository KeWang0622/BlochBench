#!/usr/bin/env python3
"""Reference solution for heldout-v6-pilotdesign: recomputes everything from the public CSV files."""
import json, math, sys, platform
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pilot_stats as S
INP = HERE.parent / 'public' / 'inputs'
TASK = json.loads((HERE.parent / 'public' / 'task.json').read_text())
OUT = HERE / 'validation' / 'reference'


def solve(unit='participant', qc=True, acute_paired=True, acute_sd='diff', group_sd='pooled', ci_variant='pooled', exact_t=False, icc_hemi=False):
    tr = S.read_csv(INP / 'pilot_test_retest.csv'); gr = S.read_csv(INP / 'pilot_groups.csv')
    ep = S.endpoint_tr(tr, qc=qc, unit=unit)
    w, wci, df, n = S.wsd(ep)
    icc, icci = S.icc21(S.endpoint_tr(tr, qc=qc, unit='knee' if icc_hemi else unit))
    G = S.group_diff(S.endpoint_groups(gr, qc=qc, unit=unit))
    st = TASK['studies_to_design']; a = st['acute_challenge']['alpha']; p = st['acute_challenge']['power']; ne = TASK['nonevaluable_fraction']
    dA, dG = st['acute_challenge']['effect'], st['group_difference']['effect']
    sdd = math.sqrt(2) * w if acute_sd == 'diff' else (w if acute_sd == 'wsd' else G['sd_pooled'])
    if acute_paired:
        nA = S.n_paired_t(sdd, dA, a, p) if exact_t else S.n_paired_z(sdd, dA, a, p)
    else:
        nA = S.n_two_t(sdd, dA, a, p) if exact_t else S.n_two_z(sdd, dA, a, p)
    sdg = G['sd_pooled'] if group_sd == 'pooled' else w
    nG = S.n_two_t(sdg, dG, a, p) if exact_t else S.n_two_z(sdg, dG, a, p)
    excl_tr = sorted({r['subject_id'] for r in tr if r['qc_pass'].lower() != 'true'}) if qc else []
    excl_gr = sorted({r['subject_id'] for r in gr if r['qc_pass'].lower() != 'true'}) if qc else []
    D = {
     'endpoint_unit_of_analysis': unit,
     'qc_exclusions': {'test_retest': excl_tr, 'groups': excl_gr},
     'repeatability': {'n_participants': n, 'within_subject_sd': round(w, 3), 'within_subject_sd_ci95': [round(x, 3) for x in wci],
                       'repeatability_coefficient': round(1.96 * math.sqrt(2) * w, 3), 'icc_form': 'ICC(2,1) two-way random, absolute agreement, single measurement',
                       'icc': round(icc, 4), 'icc_ci95': [round(x, 4) for x in icci]},
     'pilot_group_comparison': {'n_patients': G['n_patients'], 'n_controls': G['n_controls'], 'mean_difference': round(G['diff'], 3),
                                'mean_difference_ci95': [round(x, 3) for x in (G['ci_pooled'] if ci_variant == 'pooled' else G['ci_welch'])], 'pooled_sd': round(G['sd_pooled'], 3)},
     'designs': {
      'acute_challenge': {'design': 'paired_crossover' if acute_paired else 'parallel_groups', 'unit_of_analysis': unit,
                          'sd_type': {'diff': 'sd_of_within_participant_differences', 'wsd': 'within_subject_sd', 'between': 'between_participant_sd'}[acute_sd],
                          'sd_used': round(sdd, 3), 'effect': dA, 'alpha': a, 'power': p, 'n_evaluable': nA, 'n_enrol': math.ceil(nA / (1 - ne)),
                          'rationale': 'Each participant serves as own control; SD of differences = sqrt(2) x within-subject SD from the test-retest pilot.'},
      'group_difference': {'design': 'parallel_groups', 'unit_of_analysis': unit, 'sd_type': 'between_participant_sd' if group_sd == 'pooled' else 'within_subject_sd',
                           'sd_used': round(sdg, 3), 'effect': dG, 'alpha': a, 'power': p, 'n_evaluable_per_group': nG, 'n_enrol_per_group': math.ceil(nG / (1 - ne)),
                           'rationale': 'Independent groups; pooled within-group SD of the participant-level endpoint from the group pilot.'}},
     'assumptions': ['No carryover or period effect in the crossover.', 'Day-to-day variability in the challenge study equals the test-retest variability.', 'Normally distributed endpoint.'],
     'limitations': ['Pilot SDs are imprecise (wide CIs); sample sizes inherit this uncertainty.', 'Pilot patients may not represent the target population.'],
     'units': 'ms'}
    return D


def to_md(D):
    A = D['designs']['acute_challenge']; G = D['designs']['group_difference']; r = D['repeatability']
    return '\n'.join(['# Study plan', '',
        f"Repeatability: within-subject SD {r['within_subject_sd']} ms (95% CI {r['within_subject_sd_ci95'][0]} to {r['within_subject_sd_ci95'][1]}), ICC(2,1) {r['icc']}.", '',
        f"Acute challenge: {A['design']} with SD of differences {A['sd_used']}; {A['n_evaluable']} evaluable participants, enrol {A['n_enrol']}.", '',
        f"Patient-control comparison: {G['design']} with pooled SD {G['sd_used']}; {G['n_evaluable_per_group']} evaluable per group, enrol {G['n_enrol_per_group']} per group.", '',
        '## Assumptions', ''] + [f'- {x}' for x in D['assumptions']] + ['', '## Limitations', ''] + [f'- {x}' for x in D['limitations']] + [''])


def write(D, md, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'design.json').write_text(json.dumps(D, indent=1) + '\n'); (out / 'plan.md').write_text(md)
    (out / 'environment.txt').write_text(f'python {platform.python_version()}\n')


if __name__ == '__main__':
    D = solve(); write(D, to_md(D), OUT)
    from grade_pilotdesign import grade
    g = grade(OUT)
    (OUT.parent / 'reference_grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']}, 'windows': g['measurements'],
                      'n': [D['designs']['acute_challenge']['n_evaluable'], D['designs']['acute_challenge']['n_enrol'], D['designs']['group_difference']['n_evaluable_per_group'], D['designs']['group_difference']['n_enrol_per_group']]}))

