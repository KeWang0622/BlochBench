# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_dummies_dropped_onsets_unshifted | negative | public_psc_bias, hidden_case1_psc_bias, hidden_case2_psc_bias | public_psc_bias, public_psc_mae, hidden_case1_psc_bias, hidden_case1_psc_mae, hidden_case2_psc_bias, hidden_case2_psc_mae |
| neg_dummies_kept | negative | public_psc_bias, hidden_case1_psc_bias, hidden_case2_psc_bias | public_psc_bias, public_psc_mae, public_null_calibration, hidden_case1_psc_bias, hidden_case1_psc_mae, hidden_case1_null_calibration, hidden_case2_psc_bias, hidden_case2_psc_mae, hidden_case2_null_calibration |
| neg_no_highpass | negative | hidden_case1_null_calibration | public_null_calibration, hidden_case1_null_calibration, hidden_case2_null_calibration |
| neg_no_motion_regressors | negative | public_psc_mae, public_null_calibration, hidden_case1_psc_mae, hidden_case2_null_calibration | public_psc_mae, public_null_calibration, hidden_case1_psc_mae, hidden_case1_null_calibration, hidden_case2_psc_mae, hidden_case2_null_calibration |
| neg_no_slice_timing | negative | public_psc_bias, hidden_case1_psc_bias, hidden_case2_psc_bias | public_psc_bias, public_psc_mae, hidden_case1_psc_bias, hidden_case1_psc_mae, hidden_case2_psc_bias, hidden_case2_psc_mae |
| neg_ols_white_noise | negative | public_null_calibration, hidden_case1_null_calibration | public_null_calibration |
| pos_dummy_spikes_legendre | positive | - | none (all pass) |
| pos_pooled_ar1 | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
