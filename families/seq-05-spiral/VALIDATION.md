# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_no_slice_rephaser | negative | sampling_contract_te_coverage | sampling_contract_te_coverage |
| neg_recon_delay_wrong_sign | negative | hidden_rerun_reconstruct_with_delay | hidden_rerun_reconstruct_with_delay |
| neg_recon_ignores_delay | negative | hidden_rerun_reconstruct_with_delay | hidden_rerun_reconstruct_with_delay |
| neg_simulated_other_sequence | negative | simulation_matches_replay | simulation_matches_replay, hidden_rerun_reconstruct_with_delay, report_fields |
| neg_slew_violation | negative | hardware_limits | hardware_limits |
| neg_undersampled | negative | sampling_contract_te_coverage | sampling_contract_te_coverage |
| pos_alt_design | positive | - | none (all pass) |
| pos_gridding_dcf | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
