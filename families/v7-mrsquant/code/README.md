# heldout-v7-mrsquant-r4 (private)

Family: MR spectroscopy (single-voxel quantification). Sealed sibling instance: same deliverables, entrypoint, grader and pass rules as its family template, with new seeds and new acquisition, tissue and noise parameters (see gen_data.py CASES).

Layout: gen_data.py regenerates public/inputs, truth/public_truth.* and hidden/case1, hidden/case2 (inputs plus truth) with fixed seeds. reference/mrs_quant.py is the reference solution; reference_ws/ is the reference workspace built from it on the public inputs. controls/ holds the positive and negative control workspaces; validation/summary.json and validation/eval/<control>/grade.json hold their grades.

Grade one arm (run with the radial-gre-venv interpreter):

    python grade_mrsquant_arm.py <workspace_dir> <eval_dir>    # writes <eval_dir>/grade.json

Regenerate data: python gen_data.py. Rebuild and regrade controls: python validate.py [control names].

## Validation outcome

- reference (positive): expectation met = True; ; failed checks: none
- pos_time_domain_fit (positive): expectation met = True; time-domain VARPRO with separate residual-water component; failed checks: none
- pos_unweighted_coil_sum (positive): expectation met = True; unweighted coil sum (valid, lower SNR); failed checks: none
- neg_no_eddy_current_correction (negative, domain-correction omission): expectation met = True; no water-referenced eddy-current phase correction; failed checks: public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations
- neg_no_transient_alignment (negative, domain-correction omission): expectation met = True; transients averaged without frequency/phase alignment; failed checks: public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations
- neg_no_relaxation_correction (negative, domain-correction omission): expectation met = True; no T1/T2 correction of water or metabolites; failed checks: public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations
- neg_no_csf_partial_volume (negative, domain-correction omission): expectation met = True; voxel treated as pure tissue (CSF ignored); failed checks: public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations
- neg_pure_water_concentration (negative, domain-correction omission): expectation met = True; 55.5 M used for every compartment (tissue water content ignored); failed checks: public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations
- neg_no_proton_count (negative, domain-correction omission): expectation met = True; number of contributing protons ignored; failed checks: public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations
