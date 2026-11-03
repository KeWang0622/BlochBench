# Sealed sibling heldout-v4-qsm-r4 (same family, deliverables, schemas, checks and tolerances as heldout-v4-qsm)

Built from the round-3 sibling's code (round 1 heldout-v4-qsm; no round-2 sibling exists). Grader logic is copied unchanged (grade_qsm.py,
grade_qsm_arm.py); only the schema tag, instance data, instance parameters and prompt wording changed. All thresholds are the round-1 values
(inner region > 12 mm from the mask edge and <= 7.5 mm from deep-grey/CSF ROIs; local field smoothed r >= 0.85 and slope 0.75-1.25;
ROI-minus-CSF slope 0.65-1.35 and r >= 0.95; chi map smoothed r >= 0.80; same checks on the hidden rerun).

New instance parameters
- Public: seed 7272, matrix 112 x 124 x 60, voxels 1.3 x 1.4 x 2.1 mm, B0 direction (0.40, 0.42, 1.0) normalised (30.1 deg from the third axis,
  tilted in both in-plane axes), 6 echoes TE 3.6 / 8.1 / 12.6 / 17.1 / 21.6 / 26.1 ms, noise 0.0045, head shifted (-2, 1.5, -1) mm.
- Hidden: seed 9494, matrix 100 x 116 x 64, voxels 1.6 x 1.5 x 2.0 mm, B0 direction (-sin 14 deg, sin 18 deg, 1) normalised, 4 echoes TE 4.5 /
  10.5 / 16.5 / 22.5 ms, noise 0.0060, head shifted (2.5, -4, 3) mm.
- New numerical head: a third (small frontal) air cavity added, head 68 x 84 x 61 mm semi-axes, new nuclei/ventricle geometry; susceptibilities
  caudate 0.07, putamen 0.065, globus pallidus 0.18, thalamus 0.02, red nucleus 0.12, substantia nigra 0.15, WM -0.030, grey default +0.010 ppm,
  CSF 0; new receive-phase offset field, proton density and R2* (nuclei 24 + 75 x chi s^-1).
- task.json changed only in its id (all acquisition values are read from acquisition.json). Prompt reworded.
- Validation harness scratch workspaces are under sealed-r4/_trash/r4_author_ext (validation_harness.py TMPROOT).

Authoring notes (drafts discarded before freezing; their files are in sealed-r4/_trash): draft 1 used public voxels 1.3 x 1.5 x 2.4 mm, which
lowered the reference public local-field r to 0.86 (threshold 0.85); the voxel size was changed to 1.3 x 1.4 x 2.1 mm (r 0.95). Drafts 2-3
used a public B0 direction (0.48, -0.33, 1.0); with it the closed-form Tikhonov positive control failed the public chi-map check (r 0.79,
insensitive to its regularisation weight and to the noise level). Two alternative tilt directions of the same ~30 deg magnitude were checked
offline (reference, Tikhonov and wrong-B0 control only) and (0.40, 0.42, 1.0) was adopted; draft 3 also lowered the public noise from 0.0060
to 0.0045, which is kept.

Validation (private/validation, driver run_validation.sh, log validation_log.txt; each case is run as qsm.py in a clean workspace with its own
.venv and graded with grade_qsm_arm.py)
- Reference (echo differences, SHARP 5 mm, CG gradient-regularised dipole inversion): all 11 checks pass. Public local field r 0.967 / slope
  0.99, ROI slope 0.87 / r 0.998, chi map r 0.90; hidden local field r 0.978 / slope 0.99, ROI slope 0.82 / r 0.996, chi map r 0.89.
- Negative controls: 6/6 fail all their targeted checks: no background removal, wrong B0 direction (public ROI slope 0.41, chi r 0.41), isotropic
  voxel assumption, raw integer phase, Hz-to-ppm with 2 pi (rad/s) gamma, field sign flipped.
- Positive controls: 2/2 pass (TKD: public ROI slope 0.87, chi r 0.90; closed-form Tikhonov: ROI slope 0.90, chi r 0.88; hidden passes for both,
  Tikhonov hidden ROI slope 0.73).
