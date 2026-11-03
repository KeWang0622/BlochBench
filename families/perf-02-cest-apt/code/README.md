# heldout-v7-cestapt-r4 (private)

Family: CEST / MT (APT asymmetry with WASSR B0 correction). Sealed sibling instance: same deliverables, entrypoint, grader and pass rules as its family template, with new seeds and new acquisition, tissue and noise parameters (see gen_data.py CASES).

Layout: gen_data.py regenerates public/inputs, truth/public_truth.* and hidden/case1, hidden/case2 (inputs plus truth) with fixed seeds. reference/cest_apt.py is the reference solution; reference_ws/ is the reference workspace built from it on the public inputs. controls/ holds the positive and negative control workspaces; validation/summary.json and validation/eval/<control>/grade.json hold their grades.

Grade one arm (run with the radial-gre-venv interpreter):

    python grade_cestapt_arm.py <workspace_dir> <eval_dir>    # writes <eval_dir>/grade.json

Regenerate data: python gen_data.py. Rebuild and regrade controls: python validate.py [control names].

## Validation outcome

- reference (positive): expectation met = True; ; failed checks: none
- pos_lorentz_wassr_linear (positive): expectation met = True; Lorentzian WASSR fit and linear interpolation; failed checks: none
- pos_parabola_wassr (positive): expectation met = True; three-point parabolic WASSR minimum; failed checks: none
- neg_no_b0 (negative, domain-correction omission): expectation met = True; no B0 correction of the Z-spectrum; failed checks: public_mtrasym_rois, public_b0_map, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case1_b0_map, hidden_case2_mtrasym_rois, hidden_case2_b0_map
- neg_b0_wrong_sign (negative, domain-correction omission): expectation met = True; B0 shift applied in the wrong direction; failed checks: public_mtrasym_rois, public_mtrasym_voxelwise, public_b0_map, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case1_b0_map, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise, hidden_case2_b0_map
- neg_wassr_hz_as_ppm (negative, domain-correction omission): expectation met = True; WASSR offsets in Hz used as ppm; failed checks: public_mtrasym_rois, public_mtrasym_voxelwise, public_b0_map, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case1_b0_map, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise, hidden_case2_b0_map
- neg_norm_far_offset (negative, domain-correction omission): expectation met = True; Z normalised by the most negative saturated image instead of the unsaturated S0; failed checks: public_mtrasym_rois, hidden_case1_mtrasym_rois
- neg_assume_sorted (negative): expectation met = True; images assumed stored in ascending offset order; failed checks: public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise
- neg_asym_sign (negative): expectation met = True; Z(+3.5) - Z(-3.5); failed checks: public_mtrasym_rois, public_mtrasym_voxelwise, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise
