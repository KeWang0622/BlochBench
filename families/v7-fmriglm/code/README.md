# heldout-v7-fmriglm-r4 (private)

Family: functional MRI (event-related GLM). Sealed sibling instance: same deliverables, entrypoint, grader and pass rules as its family template, with new seeds and new acquisition, tissue and noise parameters (see gen_data.py CASES).

Layout: gen_data.py regenerates public/inputs, truth/public_truth.* and hidden/case1, hidden/case2 (inputs plus truth) with fixed seeds. reference/fmri_glm.py is the reference solution; reference_ws/ is the reference workspace built from it on the public inputs. controls/ holds the positive and negative control workspaces; validation/summary.json and validation/eval/<control>/grade.json hold their grades.

Grade one arm (run with the radial-gre-venv interpreter):

    python grade_fmriglm_arm.py <workspace_dir> <eval_dir>    # writes <eval_dir>/grade.json

Regenerate data: python gen_data.py. Rebuild and regrade controls: python validate.py [control names].

## Validation outcome

- reference (positive): expectation met = True; ; failed checks: none
- pos_pooled_ar1 (positive): expectation met = True; slice-pooled AR(1) prewhitening; failed checks: none
- pos_dummy_spikes_legendre (positive): expectation met = True; dummy volumes modelled with spike regressors; Legendre drift basis; failed checks: none
- neg_no_slice_timing (negative, domain-correction omission): expectation met = True; regressor sampled at volume start for every slice; failed checks: public_psc_bias, public_psc_mae, hidden_case1_psc_bias, hidden_case1_psc_mae, hidden_case2_psc_bias, hidden_case2_psc_mae
- neg_dummies_dropped_onsets_unshifted (negative, domain-correction omission): expectation met = True; dummy volumes discarded but event onsets not re-referenced; failed checks: public_psc_bias, public_psc_mae, hidden_case1_psc_bias, hidden_case1_psc_mae, hidden_case2_psc_bias, hidden_case2_psc_mae
- neg_dummies_kept (negative, domain-correction omission): expectation met = True; pre-steady-state volumes analysed as data; failed checks: public_psc_bias, public_psc_mae, public_null_calibration, hidden_case1_psc_bias, hidden_case1_psc_mae, hidden_case1_null_calibration, hidden_case2_psc_bias, hidden_case2_psc_mae, hidden_case2_null_calibration
- neg_no_motion_regressors (negative, domain-correction omission): expectation met = True; stimulus-correlated motion left in the model residual; failed checks: public_psc_mae, public_null_calibration, hidden_case1_psc_mae, hidden_case1_null_calibration, hidden_case2_psc_mae, hidden_case2_null_calibration
- neg_ols_white_noise (negative, domain-correction omission): expectation met = True; OLS statistics assuming white noise; failed checks: public_null_calibration
- neg_no_highpass (negative, domain-correction omission): expectation met = True; no drift model; failed checks: public_null_calibration, hidden_case1_null_calibration, hidden_case2_null_calibration
