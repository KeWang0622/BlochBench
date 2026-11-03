# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_label_minus_control | negative | public_gm_cbf, hidden_case1_gm_cbf | public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf |
| neg_lambda_one | negative | public_gm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf | public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf |
| neg_no_bs_efficiency | negative | public_gm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf | public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf |
| neg_no_label_efficiency | negative | public_gm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf | public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf |
| neg_no_m0_tr_correction | negative | public_gm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf | public_gm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf |
| neg_no_slice_timing | negative | public_gm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf | public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf |
| neg_tissue_t1_decay | negative | public_gm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf | public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf |
| pos_glm_drift | positive | - | none (all pass) |
| pos_median_pairs | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
