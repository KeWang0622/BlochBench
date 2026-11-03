# Sealed sibling heldout-v5-t2study-r4 (same family, deliverables and pass rules as heldout-v5-t2study)

Built from the round-3 sibling's code. The grader (grade_t2study.py, grade_t2study_arm.py) is copied unchanged apart from the image size constant
(N = 72) and the schema tag; group sizes are taken from the truth file as in rounds 2-3. Thresholds unchanged (per-scan 3 %, voxel median 6 %,
difference 1.0 ms, CI must contain the truth difference, same conclusion at 0.05, statistics relative tolerance 1e-3).

New instance parameters
- 18 participants (10 control, 8 patient; seed 16180339). Planted issue: the SECOND session of sub-11 is absent (receive-coil failure), so the
  public study has 35 scans and one participant with only ses-1; the missing-data rule applies to the public table (round 3: first session).
- 72 x 72 grid, FOV 0.216 m (3.0 mm); 9 echoes TE 9.5-85.5 ms; 12 receive coils on a ring (new geometry) with correlated noise (neighbour
  correlation 0.22 / 0.06, sigma 0.0045); R = 3 with calibration block |ky - 36| < 12.
- New anatomy: target ROI pair at (+-28, +4) mm, ventricles at (+-12, +24) mm, long-T2 (900 ms) CSF structures at (+-28, -68) mm, i.e. one
  third of the FOV from the ROI along the undersampled axis; head 69 x 89 mm; poses +-4/+-6 mm, +-6 deg.
- Patients have LOWER T2 in this instance (generative group means 82.0 / 76.5 ms, sd 2.4; round 3 had higher patient T2); brain T2 ~88 ms.
  Truth analysis: difference -5.06 ms, p = 0.0015, n 10/8.
- Hidden scans: T2 58 / 75 / 92 ms (brain 70 / 86 / 100 ms), seed 424242. Hidden tables: 8 vs 8 and 6 vs 11 subjects, one single-scan subject
  each (sub-h03, sub-h12), shuffled rows, seed 271828.
- Prompt reworded; task.json updated for the new geometry, coil count, echoes, scan count and missing session.
- Validation driver run with 1 thread (machine shared with running experiments).

Validation (private/validation, driver run_validation.sh, log validation_log.txt)
- Reference (prewhitened ESPIRiT CG-SENSE + mono-exponential fit): 9/9 checks pass, arm wrapper passes. Per-scan error mean +0.37 %, max 0.94 %;
  voxel median <= 1.8 %; hidden scans 0.63 / 0.10 / 0.47 % (voxel medians 1.4-1.8 %); difference -5.03 ms vs truth-analysis -5.06 ms,
  p = 0.0017 vs 0.0015, n 10/8.
- Negative controls: 10/10 fail their targeted check (5 at hand-offs): fft_shift, te_seconds, ses1_label (max 33 %), zero_filled (hidden 5.3 %,
  3.3 %, 1.7 %; public per-scan also fails), scans_as_units, student_t, cohen_d, wsd_no_sqrt2, drop_incomplete, sign_flip.
- Positive controls: 2/2 pass (lowres_sens max 0.68 %, grappa_rss max 1.29 %, voxel median <= 2.8 %).
- Informational: GRAPPA without prewhitening and with an unweighted log-linear fit also passes (max 0.97 %, voxel median 2.8 %).
