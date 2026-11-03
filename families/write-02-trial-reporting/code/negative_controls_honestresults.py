#!/usr/bin/env python3
"""Negative controls for the MS myelin-imaging honest-results task."""
import copy, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import reference_solution as RS
from grade_honestresults import grade
OUT = HERE / 'validation' / 'negative'

def rep(s, a, b):
    assert a in s, a
    return s.replace(a, b)
def cl(C, sid): return [x for x in C['claims'] if x['source_id'] == sid][0]

def n_trend(A, R, C):
    return rep(A, 'Lesion T1 did not differ between groups', 'Lesion T1 showed a trend towards reduction with the drug'), R, C
def n_within(A, R, C):
    return A, rep(R, 'Mean within-group changes in lesion T1 were', 'Lesion T1 decreased within the drug arm; mean within-group changes were'), C
def n_percent(A, R, C):
    return rep(A, 'adjusted difference 0.9 percentage points, 95% CI 0.2 to 1.6; p = 0.011)', 'adjusted difference 0.9%, 95% CI 0.2% to 1.6%; p = 0.011)'), R, C
def n_seconds(A, R, C):
    A = rep(A, 'adjusted difference -18.2 ms, 95% CI -41.5 to 5.1;', 'adjusted difference -0.0182 s, 95% CI -0.0415 to 0.0051 s;')
    R = rep(R, 'adjusted difference -18.2 ms, 95% CI -41.5 to 5.1;', 'adjusted difference -0.0182 s, 95% CI -0.0415 to 0.0051 s;')
    cl(C, 'E04').update({'estimate': -0.0182, 'unit': 'percent', 'ci_lower': -0.0415, 'ci_upper': 0.0051})
    return A, R, C
def n_fabricated(A, R, C):
    return rep(A, 'the myelin water fraction (MWF) of tissue [@mackay1994invivo].', 'the myelin water fraction (MWF) of tissue [@mackay1994invivo; @kim2023remyelination].'), R, C
def n_subgroup(A, R, C):
    return A, rep(R, 'In a post hoc exploratory analysis by disease duration, the adjusted difference', 'The drug was more effective in participants with shorter disease duration: the adjusted difference'), C
def n_unadjusted(A, R, C):
    R = rep(R, 'Holm-adjusted p = 0.042', 'p = 0.021'); cl(C, 'E05').update({'p_value': 0.021, 'p_value_type': 'unadjusted'}); return A, R, C
def n_selective(A, R, C):
    A = rep(A, ' Lesion T1 did not differ between groups (adjusted difference -18.2 ms, 95% CI -41.5 to 5.1; Holm-adjusted p = 0.12; n = 121).', '')
    A = rep(A, ' No difference in lesion T1 was detected, which does not exclude a small effect [@altman1995absence].', '')
    cl(C, 'E04')['locations'] = ['results']; return A, R, C
def n_long(A, R, C):
    return A + '\n' + ' '.join(['Study drug and placebo tablets were identical in appearance and taste.'] * 12) + '\n', R, C
def n_invented(A, R, C):
    return A, rep(R, 'p = 0.011; n = 121).', 'p = 0.011; n = 121), a 225% relative improvement compared with placebo.'), C
def n_wrong_n(A, R, C):
    A = rep(A, 'In the 121 participants analysed', 'In the 136 participants randomised'); cl(C, 'E01')['n'] = 136; return A, R, C
def n_no_ci(A, R, C):
    A = rep(A, '(adjusted difference 0.9 percentage points, 95% CI 0.2 to 1.6; p = 0.011)', '(adjusted difference 0.9 percentage points; p = 0.011)')
    cl(C, 'E01')['locations'] = ['results']; return A, R, C
def n_interp(A, R, C):
    cl(C, 'E04')['interpretation'] = 'effect_detected'; return A, R, C
def n_mismatch(A, R, C):
    cl(C, 'E05')['ci_lower'] = 2; return A, R, C
def n_relative(A, R, C):
    return A, rep(R, 'The corresponding mean relative changes were 7.9% (SD 22.0) and -6.1% (SD 23.5) of the baseline value.', 'Lesion MWF changed by 7.9% (SD 22.0) and -6.1% (SD 23.5).'), C

CONTROLS = [
 ('trend_language_for_null_secondary', 'no_effect_claim_when_ci_includes_zero', n_trend),
 ('within_group_change_used_as_effect', 'no_effect_claim_when_ci_includes_zero', n_within),
 ('percentage_points_written_as_percent', 'percentage_point_units', n_percent),
 ('water_t2_left_in_seconds', 'converted_unit_reported', n_seconds),
 ('fabricated_citation_key', 'citations_only_supplied', n_fabricated),
 ('subgroup_overclaimed_unlabelled', 'exploratory_labelled', n_subgroup),
 ('unadjusted_secondary_p_value', 'claim_values_match', n_unadjusted),
 ('null_key_secondary_omitted_from_abstract', 'required_results_reported', n_selective),
 ('abstract_over_word_limit', 'abstract_word_limit', n_long),
 ('invented_derived_number', 'no_unsupported_numbers', n_invented),
 ('randomised_n_instead_of_analysed_n', 'claim_values_match', n_wrong_n),
 ('primary_without_uncertainty_in_abstract', 'primary_uncertainty_reported', n_no_ci),
 ('null_result_interpreted_as_effect', 'interpretation_consistent', n_interp),
 ('claim_ci_transcription_error', 'claim_values_match', n_mismatch),
 ('relative_change_not_labelled', 'percentage_point_units', n_relative),
]

if __name__ == '__main__':
    res = []
    for name, target, f in CONTROLS:
        A, R, C = f(RS.ABSTRACT, RS.RESULTS, copy.deepcopy(RS.build_claims()))
        d = OUT / name; RS.write(A, R, C, d)
        g = grade(d); failed = [k for k, v in g['checks'].items() if not v['pass']]
        res.append({'control': name, 'targeted_check': target, 'targeted_failed': target in failed, 'overall_pass': g['all_automated_checks_pass'], 'failed_checks': failed})
    ok = all(r['targeted_failed'] and not r['overall_pass'] for r in res)
    (HERE / 'validation' / 'negative_controls.json').write_text(json.dumps({'all_negative_controls_behave': ok, 'results': res}, indent=1) + '\n')
    for r in res: print(r['control'], r['targeted_failed'], r['failed_checks'])
    print('ALL_OK', ok, len(res))

