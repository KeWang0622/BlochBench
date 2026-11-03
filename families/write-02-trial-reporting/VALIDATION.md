# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| reference_arm | reference | - | none (all pass) |
| reference | reference | - | none (all pass) |
| trend_language_for_null_secondary | negative | no_effect_claim_when_ci_includes_zero | no_effect_claim_when_ci_includes_zero |
| within_group_change_used_as_effect | negative | no_effect_claim_when_ci_includes_zero | no_effect_claim_when_ci_includes_zero |
| percentage_points_written_as_percent | negative | percentage_point_units | percentage_point_units |
| water_t2_left_in_seconds | negative | converted_unit_reported | claim_values_match, claim_units_correct, no_effect_claim_when_ci_includes_zero, converted_unit_reported |
| fabricated_citation_key | negative | citations_only_supplied | citations_only_supplied |
| subgroup_overclaimed_unlabelled | negative | exploratory_labelled | exploratory_labelled |
| unadjusted_secondary_p_value | negative | claim_values_match | claim_values_match |
| null_key_secondary_omitted_from_abstract | negative | required_results_reported | required_results_reported |
| abstract_over_word_limit | negative | abstract_word_limit | abstract_word_limit |
| invented_derived_number | negative | no_unsupported_numbers | no_unsupported_numbers |
| randomised_n_instead_of_analysed_n | negative | claim_values_match | claim_values_match |
| primary_without_uncertainty_in_abstract | negative | primary_uncertainty_reported | required_results_reported, primary_uncertainty_reported |
| null_result_interpreted_as_effect | negative | interpretation_consistent | interpretation_consistent |
| claim_ci_transcription_error | negative | claim_values_match | claim_values_match |
| relative_change_not_labelled | negative | percentage_point_units | percentage_point_units |
