# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_blip_during_adc | negative | sampling_contract | sampling_contract |
| neg_flat_top_only | negative | te_and_echo_spacing | te_and_echo_spacing |
| neg_no_ghost_correction | negative | hidden_delayed_rerun_reconstruct | hidden_delayed_rerun_reconstruct |
| neg_no_slice_rephaser | negative | sampling_contract | sampling_contract |
| neg_simulated_other_sequence | negative | simulation_matches_replay | simulation_matches_replay, report_fields |
| neg_te_wrong_echo | negative | te_and_echo_spacing | te_and_echo_spacing |
| neg_uniform_kx_recon | negative | hidden_delayed_rerun_reconstruct | hidden_delayed_rerun_reconstruct, public_image_and_report_ratios |
| pos_alt_design | positive | - | none (all pass) |
| pos_linear_phase_nav | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
