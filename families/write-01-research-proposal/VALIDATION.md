# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| reference_arm | reference | - | none (all pass) |
| reference | reference | - | none (all pass) |
| overclaimed_strain_gap | negative | gap_identified | gap_identified, gap_support_valid |
| fabricated_citation | negative | citations_within_corpus | citations_within_corpus, controls_support_valid |
| wrong_statistical_unit_roi | negative | design_correct | design_correct |
| effect_from_healthy_volunteer_comparison | negative | sample_size_inputs_valid | sample_size_inputs_valid |
| formula_missing_factor_two | negative | sample_size_arithmetic | sample_size_arithmetic |
| test_retest_sd_used_as_between_subject_sd | negative | sample_size_inputs_valid | sample_size_inputs_valid |
| ignored_smaller_group_fraction | negative | sample_size_arithmetic | sample_size_arithmetic |
| wrong_contradiction_factor | negative | contradiction_correct | contradiction_correct |
| missed_underpowered_record | negative | underpowered_claims_correct | underpowered_claims_correct |
| missed_dependent_record | negative | underpowered_claims_correct | underpowered_claims_correct |
| missing_exercise_control | negative | controls_required_present | controls_required_present |
| underpowered_record_used_as_support | negative | gap_support_valid | gap_support_valid |
| underpowered_record_counted_as_replication | negative | replicated_finding_correct | replicated_finding_correct |
| one_sided_test | negative | sample_size_inputs_valid | sample_size_inputs_valid, sample_size_arithmetic |
| mri_failure_only_nonevaluable | negative | recruitment_inputs_valid | recruitment_inputs_valid |
| control_with_unrelated_record | negative | controls_support_valid | controls_support_valid |
| healthy_volunteer_sd_used | negative | sample_size_inputs_valid | sample_size_inputs_valid |
