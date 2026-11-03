# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_assume_sorted | negative | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise |
| neg_asym_sign | negative | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise |
| neg_b0_wrong_sign | negative | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise | public_mtrasym_rois, public_mtrasym_voxelwise, public_b0_map, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case1_b0_map, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise, hidden_case2_b0_map |
| neg_no_b0 | negative | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise | public_mtrasym_rois, public_b0_map, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case1_b0_map, hidden_case2_mtrasym_rois, hidden_case2_b0_map |
| neg_norm_far_offset | negative | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise | public_mtrasym_rois, hidden_case1_mtrasym_rois |
| neg_wassr_hz_as_ppm | negative | public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise, public_b0_map | public_mtrasym_rois, public_mtrasym_voxelwise, public_b0_map, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case1_b0_map, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise, hidden_case2_b0_map |
| pos_lorentz_wassr_linear | positive | - | none (all pass) |
| pos_parabola_wassr | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
