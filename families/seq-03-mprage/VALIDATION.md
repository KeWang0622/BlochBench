# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_naive_ti | negative | t1_null_at_kspace_centre, hidden_rerun_reconstruct | t1_null_at_kspace_centre, hidden_rerun_reconstruct |
| neg_recon_kz_order | negative | hidden_rerun_reconstruct | hidden_rerun_reconstruct |
| neg_simulated_other_sequence | negative | simulation_matches_replay | simulation_matches_replay, report_fields |
| neg_te_to_adc_start | negative | flips_and_timing | flips_and_timing |
| neg_ti_to_train_start | negative | t1_null_at_kspace_centre | t1_null_at_kspace_centre, hidden_rerun_reconstruct |
| neg_two_dummy_cycles | negative | cycle_steady_state | cycle_steady_state |
| pos_alt_design | positive | - | none (all pass) |
| pos_alt_spoiling | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
