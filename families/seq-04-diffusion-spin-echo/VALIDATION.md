# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_diffusion_lobes_opposite_polarity | negative | sampling_contract | sampling_contract, te_and_spin_echo_timing, b_values_from_waveforms, archive_b_values_match, bloch_replay, simulation_matches_replay, public_adc_map, hidden_rerun_adc |
| neg_no_dummy_volume | negative | hidden_rerun_adc | public_adc_map, hidden_rerun_adc |
| neg_no_slice_rephaser | negative | sampling_contract | sampling_contract, public_adc_map, hidden_rerun_adc |
| neg_nominal_stejskal_tanner | negative | b_values_from_waveforms | b_values_from_waveforms, public_adc_map, hidden_rerun_adc |
| neg_simulated_other_sequence | negative | simulation_matches_replay | simulation_matches_replay |
| neg_spin_echo_misaligned | negative | te_and_spin_echo_timing | te_and_spin_echo_timing |
| pos_alt_crushers | positive | - | none (all pass) |
| pos_alt_timing | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
