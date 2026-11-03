# heldout-v7-dixonraw-r4 (private)

Family: fat-water imaging + raw-data reconstruction (multi-area). Sealed sibling instance: same deliverables, entrypoint, grader and pass rules as its family template, with new seeds and new acquisition, tissue and noise parameters (see gen_data.py CASES).

Layout: gen_data.py regenerates public/inputs, truth/public_truth.* and hidden/case1, hidden/case2 (inputs plus truth) with fixed seeds. reference/dixon_pdff.py is the reference solution; reference_ws/ is the reference workspace built from it on the public inputs. controls/ holds the positive and negative control workspaces; validation/summary.json and validation/eval/<control>/grade.json hold their grades.

Grade one arm (run with the radial-gre-venv interpreter):

    python grade_dixonraw_arm.py <workspace_dir> <eval_dir>    # writes <eval_dir>/grade.json

Regenerate data: python gen_data.py. Rebuild and regrade controls: python validate.py [control names].

## Validation outcome

- reference (positive): expectation met = True; ; failed checks: none
- pos_refcoil_unwhitened (positive): expectation met = True; reference-coil phase, smoothed sensitivities, no prewhitening; failed checks: none
- pos_refcoil_whitened_sigma6 (positive): expectation met = True; prewhitened reference-coil combination, stronger field-map regularisation; failed checks: none
- neg_single_peak_fat (negative, domain-correction omission): expectation met = True; single-peak fat model; failed checks: public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials
- neg_chemical_shift_sign (negative, domain-correction omission): expectation met = True; fat placed at positive frequency offsets; failed checks: public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials
- neg_no_t1_correction (negative, domain-correction omission): expectation met = True; signal fat fraction reported as PDFF (T1 weighting ignored); failed checks: public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials
- neg_t1_correction_nominal_flip (negative, domain-correction omission): expectation met = True; T1 correction with nominal flip angle (B1 map ignored); failed checks: public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials
- neg_rss_coil_combination (negative, domain-correction omission): expectation met = True; root-sum-of-squares combination destroys the echo phase evolution; failed checks: public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials
- neg_kspace_crop_oversampling (negative): expectation met = True; readout oversampling removed by cropping k-space; failed checks: public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials
- neg_even_echoes_not_reversed (negative): expectation met = True; bipolar readout ordering ignored; failed checks: public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials
