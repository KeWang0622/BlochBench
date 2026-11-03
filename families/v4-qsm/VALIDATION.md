# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| neg_hz_to_ppm_rad | negative | public_roi_susceptibility, hidden_roi_susceptibility | public_roi_susceptibility, hidden_roi_susceptibility |
| neg_isotropic_voxel | negative | public_local_field, public_chi_map, hidden_local_field, hidden_chi_map | public_local_field, public_roi_susceptibility, public_chi_map, hidden_local_field, hidden_roi_susceptibility, hidden_chi_map |
| neg_no_background_removal | negative | public_local_field, public_roi_susceptibility, public_chi_map, hidden_local_field | public_local_field, public_roi_susceptibility, public_chi_map, hidden_local_field, hidden_roi_susceptibility, hidden_chi_map |
| neg_phase_raw_int | negative | public_local_field, public_roi_susceptibility, public_chi_map, hidden_local_field | public_local_field, public_roi_susceptibility, public_chi_map, hidden_local_field, hidden_roi_susceptibility, hidden_chi_map |
| neg_sign_flip | negative | public_local_field, public_roi_susceptibility, public_chi_map, hidden_roi_susceptibility | public_local_field, public_roi_susceptibility, public_chi_map, hidden_local_field, hidden_roi_susceptibility, hidden_chi_map |
| neg_wrong_b0_direction | negative | public_roi_susceptibility, public_chi_map | public_roi_susceptibility, public_chi_map, hidden_roi_susceptibility, hidden_chi_map |
| pos_closed_form_tikhonov | positive | - | none (all pass) |
| pos_tkd | positive | - | none (all pass) |
| reference | reference | - | none (all pass) |
