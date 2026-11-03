# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| reference_arm | reference | - | none (all pass) |
| reference | reference | - | none (all pass) |
| knee_as_statistical_unit | negative | unit_of_analysis_participant | qc_exclusions_applied, unit_of_analysis_participant, within_subject_sd_correct, repeatability_coefficient_correct, icc_correct, pilot_group_estimates_correct, acute_design_correct, acute_sample_size_correct, group_design_correct, group_sample_size_correct |
| qc_rule_ignored | negative | qc_exclusions_applied | qc_exclusions_applied, within_subject_sd_correct, repeatability_coefficient_correct, icc_correct, pilot_group_estimates_correct, acute_design_correct, acute_sample_size_correct, group_design_correct, group_sample_size_correct |
| acute_challenge_as_parallel_groups | negative | acute_design_correct | acute_design_correct, acute_sample_size_correct |
| within_subject_sd_used_as_sd_of_differences | negative | acute_sample_size_correct | acute_design_correct, acute_sample_size_correct |
| group_design_with_test_retest_sd | negative | group_design_correct | group_design_correct, group_sample_size_correct |
| no_nonevaluable_inflation | negative | acute_sample_size_correct | acute_sample_size_correct |
| group_formula_missing_factor_two | negative | group_sample_size_correct | group_sample_size_correct |
| icc_on_single_knee_values | negative | icc_correct | icc_correct |
| repeatability_coefficient_without_sqrt2 | negative | repeatability_coefficient_correct | repeatability_coefficient_correct |
| observed_pilot_effect_instead_of_stated_effect | negative | group_sample_size_correct | group_sample_size_correct |
| group_difference_sign_reversed | negative | pilot_group_estimates_correct | pilot_group_estimates_correct |
