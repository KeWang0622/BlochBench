# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| N10_monoexponential_fit | negative | hidden_t2_accuracy | public_fit_accuracy, hidden_t2_accuracy, hidden_b1_accuracy |
| N1_refocusing_180deg_3p5ms_exceeds_b1rms | negative | b1_rms_limit | b1_rms_limit, public_fit_accuracy, hidden_b1_accuracy |
| N2_b1rms_evaluated_over_wrong_window | negative | b1_rms_limit, report_matches_sequence | b1_rms_limit, report_matches_sequence |
| N3_crushers_at_max_slew_exceed_pns | negative | pns_limit | pns_limit |
| N4_instantaneous_pulse_epg_for_long_pulses | negative | hidden_t2_accuracy, public_fit_accuracy | public_fit_accuracy, hidden_t2_accuracy, hidden_b1_accuracy |
| N5_model_assumes_nominal_180_refocusing | negative | hidden_b1_accuracy | public_fit_accuracy, hidden_t2_accuracy, hidden_b1_accuracy |
| N6_stale_echo_spacing_in_model | negative | hidden_t2_accuracy | public_fit_accuracy, hidden_t2_accuracy |
| N7_b1_not_estimated | negative | hidden_t2_accuracy, hidden_b1_accuracy | public_fit_accuracy, hidden_t2_accuracy, hidden_b1_accuracy |
| N8_simulated_a_different_sequence_than_exported | negative | simulation_matches_replay | simulation_matches_replay, public_fit_accuracy |
| N9_crushers_below_required_moment | negative | crusher_moments | crusher_moments |
| P1_100deg_5p5ms_esp11_32echoes | positive | - | none (all pass) |
| P2_122deg_7p5ms_esp12_28echoes_5sample_adc | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
