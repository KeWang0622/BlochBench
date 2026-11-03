# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_centre_first_echo | negative | timing_te_esp_tr | timing_te_esp_tr |
| neg_cp_not_cpmg | negative | echo_train_phase_coherence, image_quality | echo_train_phase_coherence, shot_steady_state, image_quality |
| neg_echo_off_readout_centre | negative | sampling_contract | sampling_contract, image_quality |
| neg_no_dummy_shot | negative | shot_steady_state | shot_steady_state |
| neg_no_pe_rewinder | negative | sampling_contract | sampling_contract, timing_te_esp_tr, image_quality, hidden_rerun_reconstruct |
| neg_no_slice_rephaser | negative | sampling_contract | sampling_contract, echo_train_phase_coherence, shot_steady_state, image_quality |
| neg_prephaser_wrong_sign | negative | sampling_contract | sampling_contract, image_quality, hidden_rerun_reconstruct |
| neg_recon_acquisition_order | negative | hidden_rerun_reconstruct | hidden_rerun_reconstruct |
| neg_simulated_other_sequence | negative | simulation_matches_replay | simulation_matches_replay, report_fields |
| pos_alt_ordering | positive | - | none (all pass) |
| pos_no_dedicated_crushers | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
| neg_no_crushers | negative | - | none (all pass) |
