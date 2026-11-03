# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_no_csf_partial_volume | negative | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations |
| neg_no_eddy_current_correction | negative | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations |
| neg_no_proton_count | negative | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations |
| neg_no_relaxation_correction | negative | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations |
| neg_no_transient_alignment | negative | public_concentrations, hidden_case1_concentrations | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations |
| neg_pure_water_concentration | negative | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations | public_concentrations, hidden_case1_concentrations, hidden_case2_concentrations |
| pos_time_domain_fit | positive | - | none (all pass) |
| pos_unweighted_coil_sum | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
