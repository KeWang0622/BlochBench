#!/usr/bin/env python3
"""Positive controls for the MS myelin-imaging honest-results task."""
import copy, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
from grade_honestresults import grade
OUT = HERE / 'validation' / 'positive'

A1 = """# Abstract

Background: Whether an oral remyelinating study drug restores myelin in chronic multiple sclerosis lesions is unknown.

Methods: We randomised 136 adults with relapsing multiple sclerosis 1:1 to drug or placebo for 52 weeks (synthetic trial). Lesion myelin water fraction (MWF) from myelin water imaging \\cite{mackay1994invivo} at week 52 was the primary endpoint; lesion T1 from MP2RAGE \\cite{marques2010mp2rage} was the key secondary endpoint.

Results: Lesion MWF at week 52 was 0.90 pp higher with the drug (95% CI 0.20 to 1.60 pp; P = 0.011; n = 121). For lesion T1 there was no evidence of a between-group difference: \u221218.2 ms (95% CI \u221241.5 to 5.1 ms; Holm-adjusted P = 0.12; n = 121).

Conclusion: The drug increased lesion MWF over 52 weeks; an effect on lesion T1 was not detected.
"""

R1 = """# Results

| Endpoint | Drug vs placebo (95% CI) | p | n |
|---|---|---|---|
| Lesion MWF, primary | 0.9 pp (0.2 to 1.6) | 0.011 | 121 |
| Lesion T1, key secondary: no significant difference | \u221218.2 ms (\u221241.5 to 5.1) | Holm 0.12 | 121 |
| Whole-brain volume, secondary | 4 mL (1 to 7) | Holm 0.042 | 118 |
| Lesion MWF with disease duration below 10 years (post hoc, exploratory) | 1.5 pp (0.4 to 2.6) | interaction 0.21 | 57 |
| Lesion MWF with disease duration of 10 years or more (post hoc, exploratory) | 0.3 pp (\u22120.7 to 1.3) | interaction 0.21 | 64 |

The primary endpoint favoured the drug: week-52 lesion MWF was 0.9 pp higher (95% CI 0.2 to 1.6 pp higher; p = 0.011; n = 121). Lesion T1 did not differ significantly between arms (\u221218.2 ms, 95% CI \u221241.5 to 5.1; Holm-adjusted p = 0.12; n = 121) \\cite{altman1995absence}. Whole-brain volume was higher with the drug (4 mL, 95% CI 1 to 7; Holm-adjusted p = 0.042; n = 118). In exploratory, post hoc analyses by disease duration the differences were 1.5 pp (95% CI 0.4 to 2.6; n = 57) below 10 years and 0.3 pp (95% CI \u22120.7 to 1.3; n = 64) at 10 years or more (interaction p = 0.21); these estimates are hypothesis generating \\cite{pocock2002subgroup}.
"""

def p_minimal():
    C = RS.build_claims()
    C['claims'] = [c for c in C['claims'] if c['source_id'] in {'E01', 'E04', 'E05', 'E12', 'E13'}]
    return A1, R1, C

def p_variant():
    A = RS.ABSTRACT.replace(' -', ' \u2212').replace('(-', '(\u2212').replace('percentage points', 'pp')
    A = A.replace('did not differ between groups', 'showed no significant difference between groups')
    R = RS.RESULTS.replace('percentage points', 'pp').replace('In a post hoc exploratory analysis', 'In an exploratory (post hoc) analysis')
    C = RS.build_claims()
    for c in C['claims']:
        if c['source_id'] == 'E01': c['estimate'] = 0.90
    return A, R, C

CONTROLS = [('table_based_minimal_ledger_cite_commands', p_minimal), ('unicode_minus_pp_abbreviation_rephrased', p_variant)]

if __name__ == '__main__':
    res = []
    for name, f in CONTROLS:
        A, R, C = f(); d = OUT / name; RS.write(A, R, C, d)
        g = grade(d)
        res.append({'control': name, 'overall_pass': g['all_automated_checks_pass'], 'failed': {k: v['detail'] for k, v in g['checks'].items() if not v['pass']}})
    ok = all(r['overall_pass'] for r in res)
    (HERE / 'validation' / 'positive_controls.json').write_text(json.dumps({'all_positive_controls_pass': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r)
    print('ALL_OK', ok, len(res))

