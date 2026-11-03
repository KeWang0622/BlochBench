# heldout-v7-pcasl-r4 (private)

Family: perfusion (pCASL CBF). Sealed sibling instance: same deliverables, entrypoint, grader and pass rules as its family template, with new seeds and new acquisition, tissue and noise parameters (see gen_data.py CASES).

Layout: gen_data.py regenerates public/inputs, truth/public_truth.* and hidden/case1, hidden/case2 (inputs plus truth) with fixed seeds. reference/asl_cbf.py is the reference solution; reference_ws/ is the reference workspace built from it on the public inputs. controls/ holds the positive and negative control workspaces; validation/summary.json and validation/eval/<control>/grade.json hold their grades.

Grade one arm (run with the radial-gre-venv interpreter):

    python grade_pcasl_arm.py <workspace_dir> <eval_dir>    # writes <eval_dir>/grade.json

Regenerate data: python gen_data.py. Rebuild and regrade controls: python validate.py [control names].

## Validation outcome

- reference (positive): expectation met = True; reference solution; failed checks: none
- pos_median_pairs (positive): expectation met = True; median of pairwise control-label differences; failed checks: none
- pos_glm_drift (positive): expectation met = True; GLM with label regressor and linear drift; failed checks: none
- neg_no_slice_timing (negative, domain-correction omission): expectation met = True; same PLD for every slice of the 2D multislice readout; failed checks: public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf
- neg_no_bs_efficiency (negative, domain-correction omission): expectation met = True; background-suppression inversion losses ignored; failed checks: public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf
- neg_no_m0_tr_correction (negative, domain-correction omission): expectation met = True; short-TR M0 used without saturation-recovery correction; failed checks: public_gm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf
- neg_no_label_efficiency (negative, domain-correction omission): expectation met = True; pCASL labeling efficiency set to 1; failed checks: public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf
- neg_tissue_t1_decay (negative, domain-correction omission): expectation met = True; label decay with tissue T1 instead of blood T1; failed checks: public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf
- neg_label_minus_control (negative): expectation met = True; label minus control (sign error); failed checks: public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf
- neg_lambda_one (negative): expectation met = True; blood-brain partition coefficient 1.0 instead of supplied 0.9; failed checks: public_gm_cbf, public_wm_cbf, hidden_case1_gm_cbf, hidden_case1_wm_cbf, hidden_case2_gm_cbf, hidden_case2_wm_cbf
