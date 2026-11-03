# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| grade_reference | reference | - | none (all pass) |
| grade_reference_arm | reference | - | none (all pass) |
| monoexp_all | negative | public_t2_low_b1_bias, public_roi_t2_endpoint | public_t2_voxel_accuracy, public_t2_label_bias, public_t2_low_b1_bias, public_b1_accuracy, public_roi_t2_endpoint, hidden_t2_voxel_accuracy, hidden_t2_label_bias, hidden_t2_low_b1_bias, hidden_b1_accuracy, hidden_roi_t2_endpoint |
| monoexp_skip_first | negative | public_t2_low_b1_bias, public_roi_t2_endpoint | public_t2_voxel_accuracy, public_t2_label_bias, public_t2_low_b1_bias, public_b1_accuracy, public_roi_t2_endpoint, hidden_t2_label_bias, hidden_t2_low_b1_bias, hidden_b1_accuracy, hidden_roi_t2_endpoint |
| epg_b1_fixed | negative | public_t2_low_b1_bias, public_b1_accuracy | public_t2_voxel_accuracy, public_t2_label_bias, public_t2_low_b1_bias, public_b1_accuracy, public_roi_t2_endpoint, hidden_t2_low_b1_bias, hidden_b1_accuracy, hidden_roi_t2_endpoint |
| cp_phase | negative | public_t2_voxel_accuracy, public_b1_accuracy | public_t2_voxel_accuracy, public_t2_label_bias, public_t2_low_b1_bias, public_b1_accuracy, public_roi_t2_endpoint, hidden_t2_voxel_accuracy, hidden_t2_label_bias, hidden_t2_low_b1_bias, hidden_b1_accuracy, hidden_roi_t2_endpoint |
| esp_full_each_half | negative | public_t2_voxel_accuracy, public_roi_t2_endpoint | public_t2_voxel_accuracy, public_t2_label_bias, public_t2_low_b1_bias, public_roi_t2_endpoint, hidden_t2_voxel_accuracy, hidden_t2_label_bias, hidden_t2_low_b1_bias, hidden_roi_t2_endpoint |
| hardcoded_protocol | negative | hidden_t2_voxel_accuracy, hidden_roi_t2_endpoint | hidden_t2_voxel_accuracy, hidden_t2_label_bias, hidden_t2_low_b1_bias, hidden_b1_accuracy, hidden_roi_t2_endpoint |
| epg_gauss_newton | positive | - | none (all pass) |
| epg_dictionary_noise_truncated | positive | - | none (all pass) |
