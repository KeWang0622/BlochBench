# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| ref | reference | - | none (all pass) |
| ref_arm | reference | - | none (all pass) |
| no_half_shift | negative | trajectory_contract | trajectory_contract |
| b1_violation | negative | sequence_hardware_limits | sequence_hardware_limits |
| no_dummy | negative | periodic_state_preparation | periodic_state_preparation, public_t1_accuracy |
| swap_xy_sim | negative | simulation_matches_replay | simulation_matches_replay, public_t1_accuracy |
| recon_swap | negative | hidden_rerun_t1_accuracy | public_t1_accuracy, hidden_rerun_t1_accuracy |
| twoparam | negative | public_t1_accuracy | public_t1_accuracy, hidden_rerun_t1_accuracy, hidden_fit_only_accuracy |
| naive_mag | negative | hidden_fit_only_accuracy | public_t1_accuracy, hidden_rerun_t1_accuracy, hidden_fit_only_accuracy |
| magnitude_fit | positive | - | none (all pass) |
| direct_recon | positive | - | none (all pass) |
| alt_sequence | positive | - | none (all pass) |
