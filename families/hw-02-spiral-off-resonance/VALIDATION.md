# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| ref | reference | - | none (all pass) |
| ref_arm | reference | - | none (all pass) |
| no_correction | negative | hidden_rerun_correction | public_image_fidelity, hidden_rerun_correction |
| field_sign | negative | public_field_map_accuracy | public_field_map_accuracy, public_image_fidelity, hidden_rerun_correction |
| delta_te_ms | negative | public_field_map_accuracy | public_field_map_accuracy, public_image_fidelity, hidden_rerun_correction |
| field_transposed | negative | public_field_map_accuracy | public_field_map_accuracy, public_image_fidelity, hidden_rerun_correction |
| time_from_adc_start | negative | public_image_fidelity | public_image_fidelity, hidden_rerun_correction |
| kxy_swapped | negative | hidden_rerun_correction | public_image_fidelity, hidden_rerun_correction |
| hz_as_rad | negative | simulation_matches_replay | simulation_matches_replay, public_image_fidelity |
| slew_violation | negative | sequence_hardware_limits | sequence_hardware_limits |
| undersampled_spiral | negative | trajectory_coverage_contract | trajectory_coverage_contract, public_image_fidelity, hidden_rerun_correction |
| time_segmented | positive | - | none (all pass) |
| alt_sequence | positive | - | none (all pass) |
