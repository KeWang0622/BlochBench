# Sealed sibling heldout-v5-learnrecon-r4 (same family, deliverables, schemas, checks and tolerances as heldout-v5-learnrecon)

Built from the round-3 sibling's code. Grader logic (grade_learnrecon.py, grade_learnrecon_arm.py) is copied unchanged; only instance data,
instance parameters and the prompt wording changed. Tolerances unchanged (per method: R2* median <= 3.5 %, p90 <= 11 %; dB0 median <= 0.5 Hz,
p90 <= 1.5 Hz; k-space residual <= 0.35; reported ROI values match within 2 % / 0.3 Hz for >= 95 % of ROIs; split by subject; hidden reruns).
private/refenv is a symlink to the round-1 private venv (torch CPU, sigpy), as in rounds 2-3; it is used only by the reference solution and
is not part of FROZEN-SHA256.txt (symlink).

New instance parameters
- 5-echo GRE with TE 4.0 / 9.9 / 15.8 / 21.7 / 27.6 ms (dTE 5.9 ms); noise sd 0.018; |dB0| clipped at 72 Hz (task.json states < 75 Hz).
- Sampling distribution unchanged from round 3 (fully sampled disc of radius 5.5 samples, remaining samples with probability ~ 1/(1 + (r/8)^2),
  1024 samples per echo, R = 4); masks are new draws.
- 30 training subjects (A401-A430, 180 slices), 8 test subjects (B501-B508) and 8 hidden subjects (C601-C608), 4 slices each; seed 737373.
- Tissue: R2* 22 / 32 / 18.5 / 52 s^-1 (x U(0.9, 1.1); lesions x U(0.88, 1.12)), PD 0.68 / 0.76 / 0.86 / 0.70; head shape and rotation ranges
  changed; field: polynomial sd 11 Hz plus a lateral air-tissue-like bump (22-48 Hz) near x = +-0.42-0.62; lesion sizes 0.06-0.11.
- Prompt reworded; task.json updated for the training-set size, TE, dTE, noise and dB0 bound.

Validation (private/validation, driver run_validation.sh, logs full_run.log, ref_run.log, neg_run.log, pos_run.log)
- Reference (2-cascade residual U-Net with data consistency, 30 CPU epochs; joint-sparsity wavelet CS with lambda tuned on validation
  subjects): all 13 checks pass through grade_learnrecon_arm.py. Learned R2* median / p90: public 1.8 % / 6.2 %, hidden 2.3 % / 5.9 %;
  classical 1.7 % / 8.1 % and 1.9 % / 6.6 %; dB0 p90 <= 0.41 Hz; k-space residual 0.0 (learned, hard DC) and 0.033 (classical).
- Negative controls: 7/7 fail their targeted checks (5 are hand-off errors): N1 per-echo intensity normalisation, N2 magnitude-only network
  output, N3 classical recon uses one fixed mask, N4 missing ifftshift on the learned output, N5 slice-level train/validation split, N6 R2*
  reported in 1/ms, N7 zero filling submitted as the classical method (R2* median / p90 3.9 % / 16.5 % public, 4.9 % / 14.1 % hidden).
- Positive controls: 2/2 pass (P1 single-cascade wider U-Net with DC, retrained: learned R2* median 2.1 % public / 2.4 % hidden;
  P2 per-echo L1-wavelet classical: R2* median 2.0 % / 3.4 %, p90 9.1 % / 8.1 %; its hidden median is close to the 3.5 % limit).
