#!/usr/bin/env python3
"""Reference solution for the MS myelin-imaging honest-results task."""
import json, sys, platform
from pathlib import Path
HERE = Path(__file__).resolve().parent
OUT = HERE / 'validation' / 'reference'

ABSTRACT = """# Abstract

**Background:** Chronic multiple sclerosis lesions often remain demyelinated; myelin water imaging estimates the myelin water fraction (MWF) of tissue [@mackay1994invivo].

**Methods:** In this randomised, double-blind, placebo-controlled trial (synthetic data), 136 adults with relapsing multiple sclerosis were allocated 1:1 to an oral remyelinating study drug or placebo for 52 weeks. The primary endpoint was the week-52 MWF of chronic lesions from 3D GRASE myelin water imaging [@prasloski2012rapid], analysed by ANCOVA adjusted for baseline value and site. Lesion T1 from MP2RAGE [@marques2010mp2rage] was the key secondary endpoint; secondary endpoints were Holm-adjusted [@holm1979simple].

**Results:** In the 121 participants analysed, week-52 lesion MWF was higher with the drug than with placebo (adjusted difference 0.9 percentage points, 95% CI 0.2 to 1.6; p = 0.011). Lesion T1 did not differ between groups (adjusted difference -18.2 ms, 95% CI -41.5 to 5.1; Holm-adjusted p = 0.12; n = 121).

**Conclusions:** Over 52 weeks the study drug increased the myelin water fraction of chronic lesions compared with placebo. No difference in lesion T1 was detected, which does not exclude a small effect [@altman1995absence].
"""

RESULTS = """# Results

## Participants

Of 136 randomised participants (68 per arm), 121 (drug 59, placebo 62) had analysable week-52 myelin water and T1 maps; whole-brain volume was analysable in 118 (58 and 60). Baseline lesion MWF was 6.4% (SD 2.1; n = 68) in the drug arm and 6.6% (SD 2.3; n = 68) in the placebo arm. Baseline lesion T1 was 1304.6 ms (SD 112.4; n = 68) and 1298.1 ms (SD 108.7; n = 68), respectively. Median adherence by tablet count was 94% of doses (IQR 87 to 98; n = 68).

## Primary endpoint

Week-52 lesion MWF was higher with the drug than with placebo (adjusted difference 0.9 percentage points, 95% CI 0.2 to 1.6; p = 0.011; n = 121). Mean within-group changes were 0.5 percentage points (SD 1.3; n = 59) with the drug and -0.4 percentage points (SD 1.7; n = 62) with placebo. The corresponding mean relative changes were 7.9% (SD 22.0) and -6.1% (SD 23.5) of the baseline value.

## Secondary endpoints

Lesion T1 did not differ between groups (adjusted difference -18.2 ms, 95% CI -41.5 to 5.1; Holm-adjusted p = 0.12; n = 121). Mean within-group changes in lesion T1 were -21.4 ms (SD 61.1; n = 59) with the drug and -3.5 ms (SD 58.8; n = 62) with placebo. Whole-brain volume at week 52 was higher with the drug (adjusted difference 4 mL, 95% CI 1 to 7; Holm-adjusted p = 0.042; n = 118) [@smith2002sienax].

## Exploratory subgroup analysis

In a post hoc exploratory analysis by disease duration, the adjusted difference in week-52 lesion MWF was 1.5 percentage points (95% CI 0.4 to 2.6; n = 57) in participants with a disease duration below 10 years and 0.3 percentage points (95% CI -0.7 to 1.3; n = 64) in those with 10 years or more (interaction p = 0.21) [@pocock2002subgroup].

## Safety

Adverse events occurred in 14 of 68 participants in the drug arm (mostly transient nausea) and in 10 of 68 in the placebo arm; 1 serious adverse event (a hospitalisation for a urinary tract infection) occurred in the drug arm.
"""

def claim(cid, sid, est, unit, at, interp, locs, n, ci=None, sd=None, iqr=None, p=None, pt=None):
    return {'claim_id': cid, 'source_id': sid, 'estimate': est, 'unit': unit, 'ci_lower': ci[0] if ci else None, 'ci_upper': ci[1] if ci else None,
            'sd': sd, 'iqr_lower': iqr[0] if iqr else None, 'iqr_upper': iqr[1] if iqr else None, 'p_value': p, 'p_value_type': pt, 'n': n,
            'analysis_type': at, 'interpretation': interp, 'locations': locs}

def build_claims():
    R = ['results']; AR = ['abstract', 'results']
    return {'claims': [
     claim('C01', 'E01', 0.9, 'percentage_points', 'primary', 'effect_detected', AR, 121, ci=(0.2, 1.6), p=0.011, pt='unadjusted'),
     claim('C02', 'E02', 6.4, 'percent', 'descriptive', 'descriptive', R, 68, sd=2.1),
     claim('C03', 'E03', 6.6, 'percent', 'descriptive', 'descriptive', R, 68, sd=2.3),
     claim('C04', 'E04', -18.2, 'ms', 'secondary', 'no_effect_detected', AR, 121, ci=(-41.5, 5.1), p=0.12, pt='holm'),
     claim('C05', 'E05', 4, 'mL', 'secondary', 'effect_detected', R, 118, ci=(1, 7), p=0.042, pt='holm'),
     claim('C06', 'E06', 0.5, 'percentage_points', 'descriptive', 'descriptive', R, 59, sd=1.3),
     claim('C07', 'E07', -0.4, 'percentage_points', 'descriptive', 'descriptive', R, 62, sd=1.7),
     claim('C08', 'E08', 7.9, 'percent', 'descriptive', 'descriptive', R, 59, sd=22.0),
     claim('C09', 'E09', -6.1, 'percent', 'descriptive', 'descriptive', R, 62, sd=23.5),
     claim('C10', 'E10', -21.4, 'ms', 'descriptive', 'descriptive', R, 59, sd=61.1),
     claim('C11', 'E11', -3.5, 'ms', 'descriptive', 'descriptive', R, 62, sd=58.8),
     claim('C12', 'E12', 1.5, 'percentage_points', 'exploratory', 'exploratory', R, 57, ci=(0.4, 2.6), p=0.21, pt='interaction'),
     claim('C13', 'E13', 0.3, 'percentage_points', 'exploratory', 'exploratory', R, 64, ci=(-0.7, 1.3), p=0.21, pt='interaction'),
     claim('C14', 'E14', 94, 'percent', 'descriptive', 'descriptive', R, 68, iqr=(87, 98)),
     claim('C15', 'E15', 14, 'count', 'safety', 'descriptive', R, 68),
     claim('C16', 'E16', 10, 'count', 'safety', 'descriptive', R, 68),
     claim('C17', 'E17', 1304.6, 'ms', 'descriptive', 'descriptive', R, 68, sd=112.4),
     claim('C18', 'E18', 1298.1, 'ms', 'descriptive', 'descriptive', R, 68, sd=108.7)],
     'limitations': ['Complete-case analysis; 15 participants lacked analysable week-52 myelin water and T1 maps.', 'The lesion T1 CI does not exclude small effects.', 'The disease-duration subgroup analysis was post hoc.']}

def write(abstract, results, claims, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'abstract.md').write_text(abstract); (out / 'results.md').write_text(results)
    (out / 'claims.json').write_text(json.dumps(claims, indent=1) + '\n')
    (out / 'environment.txt').write_text(f'python {platform.python_version()}\n')

if __name__ == '__main__':
    write(ABSTRACT, RESULTS, build_claims(), OUT)
    sys.path.insert(0, str(HERE)); from grade_honestresults import grade
    g = grade(OUT)
    (OUT.parent / 'reference_grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']}, 'words': g['measurements'].get('abstract_words')}))

