# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_distortion_wrong_sign | negative | public_geometry, hidden_case1_geometry, hidden_case2_geometry | public_geometry, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_voxelwise, hidden_case2_geometry, hidden_case2_nyquist_ghost, hidden_case2_fa_voxelwise |
| neg_ghost_constant_phase_only | negative | public_nyquist_ghost, hidden_case1_nyquist_ghost, hidden_case2_nyquist_ghost | public_geometry, public_nyquist_ghost, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case2_geometry, hidden_case2_nyquist_ghost |
| neg_ignore_blip_polarity | negative | hidden_case1_geometry | public_geometry, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_voxelwise |
| neg_negative_readouts_not_reversed | negative | public_geometry, hidden_case1_geometry, hidden_case2_geometry | public_geometry, public_nyquist_ghost, public_fa_md_rois, public_fa_voxelwise, public_v1_direction, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_md_rois, hidden_case1_fa_voxelwise, hidden_case1_v1_direction, hidden_case2_geometry, hidden_case2_nyquist_ghost, hidden_case2_fa_md_rois, hidden_case2_fa_voxelwise, hidden_case2_v1_direction |
| neg_no_distortion_correction | negative | public_geometry, hidden_case1_geometry, hidden_case2_geometry | public_geometry, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_fa_voxelwise, hidden_case2_geometry, hidden_case2_fa_voxelwise |
| neg_no_ghost_correction | negative | public_nyquist_ghost, hidden_case1_nyquist_ghost, hidden_case2_nyquist_ghost | public_geometry, public_nyquist_ghost, public_fa_md_rois, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_md_rois, hidden_case1_fa_voxelwise, hidden_case2_geometry, hidden_case2_nyquist_ghost |
| neg_no_gradient_nonlinearity | negative | public_fa_md_rois, hidden_case1_fa_md_rois, hidden_case2_fa_md_rois | public_fa_md_rois, hidden_case1_fa_md_rois, hidden_case2_fa_md_rois |
| pos_model_based_unwarp | positive | - | none (all pass) |
| pos_pooled_navigator_ols | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
