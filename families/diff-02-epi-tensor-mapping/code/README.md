# heldout-v7-epidti-r4 (private)

Family: EPI correction + diffusion MRI (multi-area). Sealed sibling instance: same deliverables, entrypoint, grader and pass rules as its family template, with new seeds and new acquisition, tissue and noise parameters (see gen_data.py CASES).

Layout: gen_data.py regenerates public/inputs, truth/public_truth.* and hidden/case1, hidden/case2 (inputs plus truth) with fixed seeds. reference/epi_dti.py is the reference solution; reference_ws/ is the reference workspace built from it on the public inputs. controls/ holds the positive and negative control workspaces; validation/summary.json and validation/eval/<control>/grade.json hold their grades.

Grade one arm (run with the radial-gre-venv interpreter):

    python grade_epidti_arm.py <workspace_dir> <eval_dir>    # writes <eval_dir>/grade.json

Regenerate data: python gen_data.py. Rebuild and regrade controls: python validate.py [control names].

## Validation outcome

- reference (positive): expectation met = True; ; failed checks: none
- pos_model_based_unwarp (positive): expectation met = True; regularised model-based inversion of the off-resonance encoding per column; failed checks: none
- pos_pooled_navigator_ols (positive): expectation met = True; navigator phase pooled over volumes; unweighted log-linear tensor fit; failed checks: none
- neg_no_ghost_correction (negative, domain-correction omission): expectation met = True; navigators ignored; failed checks: public_geometry, public_nyquist_ghost, public_fa_md_rois, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_md_rois, hidden_case1_fa_voxelwise, hidden_case2_geometry, hidden_case2_nyquist_ghost
- neg_ghost_constant_phase_only (negative, domain-correction omission): expectation met = True; only a constant odd/even phase removed (echo shift ignored); failed checks: public_geometry, public_nyquist_ghost, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case2_geometry, hidden_case2_nyquist_ghost
- neg_no_distortion_correction (negative, domain-correction omission): expectation met = True; field map not used; failed checks: public_geometry, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_fa_voxelwise, hidden_case2_geometry, hidden_case2_fa_voxelwise
- neg_distortion_wrong_sign (negative, domain-correction omission): expectation met = True; displacement applied in the wrong direction; failed checks: public_geometry, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_voxelwise, hidden_case2_geometry, hidden_case2_nyquist_ghost, hidden_case2_fa_voxelwise
- neg_ignore_blip_polarity (negative, domain-correction omission): expectation met = True; phase-encoding polarity assumed positive; failed checks: public_geometry, public_fa_voxelwise, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_voxelwise
- neg_no_gradient_nonlinearity (negative, domain-correction omission): expectation met = True; nominal b-matrix; failed checks: public_fa_md_rois, hidden_case1_fa_md_rois, hidden_case2_fa_md_rois
- neg_negative_readouts_not_reversed (negative): expectation met = True; alternate EPI lines not time-reversed; failed checks: public_geometry, public_nyquist_ghost, public_fa_md_rois, public_fa_voxelwise, public_v1_direction, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_md_rois, hidden_case1_fa_voxelwise, hidden_case1_v1_direction, hidden_case2_geometry, hidden_case2_nyquist_ghost, hidden_case2_fa_md_rois, hidden_case2_fa_voxelwise, hidden_case2_v1_direction
