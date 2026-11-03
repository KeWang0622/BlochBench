# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_adc_on_flat_top | negative | sampling_contract_te_coverage | sampling_contract_te_coverage |
| neg_late_te | negative | sampling_contract_te_coverage, hidden_rerun_reconstruct_short_t2 | sampling_contract_te_coverage, hidden_rerun_reconstruct_short_t2 |
| neg_no_polarity_alternation | negative | half_pulse_pair_slice_profile | half_pulse_pair_slice_profile |
| neg_no_ramp_compensation | negative | half_pulse_pair_slice_profile | sampling_contract_te_coverage, half_pulse_pair_slice_profile |
| neg_simulated_other_sequence | negative | simulation_matches_replay | simulation_matches_replay, hidden_rerun_reconstruct_short_t2, public_image_and_report_ratios, report_fields |
| neg_too_few_spokes | negative | sampling_contract_te_coverage | sampling_contract_te_coverage |
| pos_alt_design | positive | - | none (all pass) |
| pos_alt_design2 | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
