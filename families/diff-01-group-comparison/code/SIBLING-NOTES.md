# Sealed sibling heldout-v5-dwigroup-r4 (same family, deliverables, schemas, checks and tolerances as heldout-v5-dwigroup)

Built from the round-3 sibling's code. Grader logic (grade_dwigroup.py, grade_dwigroup_arm.py) is copied unchanged; only instance data,
instance parameters and the prompt wording changed.

New instance parameters
- Grid 50 x 44 x 16 at 2.0 mm isotropic, Rician noise sigma 16, field strength label 1.5 T; new main seed 60721, subject seeds 5100+, hidden
  seeds 9700+.
- 14 public subjects (7 control, 7 patient, shuffled order), affine reflection pattern s % 3 == 1, oblique rotations up to 12-20 deg on the
  largest axis, translations +-7 mm.
- Public protocol: nominal b 1000 s/mm2, two shells acquired in sequence with |g|^2 = 0.42 (b 420) and 1.0 (b 1000), 16 directions each,
  3 leading b0 and one b0 after every 8 diffusion volumes, 330 s run.
- Hidden protocol: nominal b 1100, |g|^2 = 0.33 (b 363) and 1.0, 14 directions per shell, 2 leading b0, b0 every 7 volumes, 400 s run;
  hidden subjects control/patient/control with reflections True/True/False and the largest rotation about the third axis.
- Drift: 1 + c1 tau + c2 tau^2 with c1 in [-0.20, -0.14] and c2 in [+0.02, +0.05] (signal loss that decelerates during the run, 9-18 % at the
  end; round 3 used accelerating loss).
- New tract geometry (tract A axis ~(0.7, 0.8, -0.25) through centre + (6, -5, 0) vox, radius 2.8; tract B axis ~(0.95, -0.35, 0.3) through
  centre + (-5, 7, 0) vox, radius 2.6), new deep-grey and CSF ellipsoids, brain ellipsoid 22.5 x 19.5 x 7.8 vox.
- Tissue eigenvalues (um2/ms): tract A 1.74 / 0.29 / 0.29 with patients axial x0.94 and radial x1.12; tract B 1.46/0.38/0.31; deep grey
  0.90/0.76/0.66; CSF 3.00/2.92/2.84; other 1.05/0.60/0.49; subject random effect sd 3 %. S0 860/900/1040/1600/940.
- Ground-truth group differences (patient - control, tract A): FA -0.0355, MD +0.0045 um2/ms.
- Prompt reworded; task.json changed only in id and subject count (14).

Validation (private/validation, driver run_validation.sh, log full_run.log)
- Reference: all 13 checks pass through grade_dwigroup_arm.py (public FA max abs err 0.0079, MD max rel err 0.24 %, V1 max 0.09 deg; hidden
  FA 0.0092, MD 0.18 %, V1 0.08 deg; group FA diff err 0.0003, MD diff err 0.0004).
- Negative controls: 9/9 fail their targeted checks (6 are hand-off errors): N1 bvec normalised without b scaling, N2 LPS read as RAS, N3
  scanner directions used as voxel axes, N4 no drift correction, N5 drift fitted on all volumes, N6 MD in mm2/s, N7 V1 in voxel axes, N8 group
  difference sign reversed, N9 entrypoint hard-codes the public gradient table.
- Positive controls: 3/3 pass (P1 OLS fit + b0-interpolated drift, P2 NLLS fit + linear drift, P3 fit in the voxel frame rotated back).
