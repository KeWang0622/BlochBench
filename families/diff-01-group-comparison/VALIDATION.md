# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| N1_bvec_normalised_no_bscale | negative | public_md_accuracy, hidden_md_accuracy | public_md_accuracy, hidden_fa_accuracy, hidden_md_accuracy, hidden_maps |
| N2_lps_read_as_ras | negative | public_v1_accuracy, hidden_v1_accuracy | public_v1_accuracy, hidden_v1_accuracy, hidden_maps |
| N3_scanner_dirs_used_as_voxel_axes | negative | public_v1_accuracy, hidden_v1_accuracy | public_v1_accuracy, hidden_v1_accuracy, hidden_maps |
| N4_no_drift_correction | negative | public_md_accuracy, hidden_md_accuracy | public_fa_accuracy, public_md_accuracy, hidden_fa_accuracy, hidden_md_accuracy, hidden_maps |
| N5_drift_fit_on_all_volumes | negative | public_md_accuracy, public_fa_accuracy | public_fa_accuracy, public_md_accuracy, public_v1_accuracy, group_difference_accuracy, hidden_fa_accuracy, hidden_md_accuracy, hidden_v1_accuracy, hidden_maps |
| N6_md_reported_in_mm2_per_s | negative | public_md_accuracy, hidden_md_accuracy, hidden_maps | public_md_accuracy, hidden_md_accuracy, hidden_maps |
| N7_v1_reported_in_voxel_axes | negative | public_v1_accuracy, hidden_v1_accuracy | public_v1_accuracy, hidden_v1_accuracy, hidden_maps |
| N8_group_difference_sign_reversed | negative | group_difference_accuracy | group_difference_accuracy, group_welch_consistency |
| N9_entrypoint_hardcodes_public_gradient_table | negative | hidden_rerun_runs | hidden_rerun_runs, hidden_fa_accuracy, hidden_md_accuracy, hidden_v1_accuracy, hidden_maps |
| P1_ols_fit_b0_interpolated_drift | positive | - | none (all pass) |
| P2_nlls_fit_linear_drift | positive | - | none (all pass) |
| P3_fit_in_voxel_frame_rotated_back | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
