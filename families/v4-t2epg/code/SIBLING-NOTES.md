# Sealed sibling heldout-v4-t2epg-r4 (same family, deliverables, schemas, checks and tolerances as heldout-v4-t2epg)

Built from the round-3 sibling's code (round 1 heldout-v4-t2epg; no round-2 sibling exists). Grader logic is copied unchanged (grade_t2epg.py,
grade_t2epg_arm.py); only the schema tag, instance data, instance parameters and prompt wording changed. All tolerances are the round-1 values
(T2 median |rel err| 3 %, per-label bias 3 %, lowest-B1-quartile bias 3 %, B1 median |err| 0.03, every label-mean T2 within 3 %, public rerun
reproduces within 1 %).

New instance parameters
- Public: seed 83, grid 92 x 104 x 4, voxels 2.1 x 1.9 x 4.0 mm with a +9 deg in-plane rotation in the affine; ESP 9.5 ms, 30 echoes, nominal
  refocusing 165 deg, AssumedT1_s 1.25 (rounds 1-3: 1.1); label T2 76 / 44 / 105 / 140 / 210 ms (+-4 % smooth variation), T1 1.10 / 0.95 / 1.30 /
  1.45 / 1.60 s; new insert positions and radii; B1+ 0.45-1.05 (B1 x 165 <= 173 deg); Rician sigma 2.1.
- Hidden: seed 71, grid 86 x 94 x 4, voxels 2.5 x 2.2 x 3.6 mm, -15 deg rotation; ESP 12.0 ms, 26 echoes, nominal refocusing 155 deg; label T2
  52 / 34 / 90 / 120 / 245 ms, T1 0.92-1.58 s; B1+ 0.60-1.15 (B1 x 155 <= 178 deg); sigma 2.0.
- task.json conventions updated to the new limits: 0.45 <= B1 <= 1.15, T2 between 0.03 and 0.26 s, T1 between 0.9 and 1.65 s. Prompt reworded.
- Control scaffolding: the hard-coded-protocol negative control now hard-codes the round-4 public values (9.5 ms, 165 deg); control scratch
  workspaces are created under sealed-r4/_trash.

Validation (private/validation, driver run_validation.sh, log validation_log.txt)
- Reference (EPG dictionary matching): all checks pass, also through grade_t2epg_arm.py. Public T2 median |rel err| 0.37 %, low-B1 bias -0.17 %,
  B1 median |err| 0.004, label-mean errors <= 0.4 %; hidden 0.42 %, +0.04 %, 0.004.
- Negative controls: 6/6 fail their targeted checks (and the overall grade): mono-exponential fit over all echoes, mono-exponential fit
  skipping echo 1, EPG with B1 fixed to 1, CP instead of CPMG refocusing phase, full echo spacing relaxation in each half interval, protocol
  hard-coded from the public data (hidden rerun fails).
- Positive controls: 2/2 pass (EPG coarse grid + Gauss-Newton: public 0.26 %, hidden 0.32 % median |rel err|; noise-truncated dictionary
  matching).
