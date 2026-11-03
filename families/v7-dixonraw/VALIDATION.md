# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_chemical_shift_sign | negative | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials | public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials |
| neg_even_echoes_not_reversed | negative | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials | public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials |
| neg_kspace_crop_oversampling | negative | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials | public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials |
| neg_no_t1_correction | negative | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials |
| neg_rss_coil_combination | negative | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials | public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials |
| neg_single_peak_fat | negative | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials | public_pdff_vials, public_r2s_vials, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials |
| neg_t1_correction_nominal_flip | negative | public_pdff_vials, hidden_case2_pdff_vials | public_pdff_vials, hidden_case1_pdff_vials, hidden_case2_pdff_vials |
| pos_refcoil_unwhitened | positive | - | none (all pass) |
| pos_refcoil_whitened_sigma6 | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
