# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| N1_per_echo_intensity_normalisation | negative | public_learned_downstream, hidden_learned_downstream | public_data_consistency, public_learned_downstream, hidden_learned_downstream |
| N2_magnitude_only_network_output | negative | public_learned_downstream, hidden_learned_downstream | public_data_consistency, public_learned_downstream, hidden_learned_downstream |
| N3_classical_uses_one_fixed_mask | negative | public_classical_downstream, public_data_consistency, hidden_classical_downstream | public_classical_downstream, hidden_classical_downstream |
| N4_missing_ifftshift_in_learned_output | negative | public_data_consistency, public_learned_downstream, hidden_learned_downstream | public_data_consistency, public_learned_downstream, hidden_learned_downstream |
| N5_slice_level_train_validation_split | negative | split_by_subject | split_by_subject, validation_comparison_reported |
| N6_r2s_reported_in_per_ms | negative | reported_downstream_matches_recon | reported_downstream_matches_recon |
| N7_zero_filled_submitted_as_classical | negative | public_classical_downstream, hidden_classical_downstream | public_classical_downstream, hidden_classical_downstream |
| P1_single_cascade_wider_unet_with_dc | positive | - | none (all pass) |
| P2_per_echo_l1_wavelet_classical | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
