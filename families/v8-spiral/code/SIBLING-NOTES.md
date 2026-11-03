# heldout-v8-spiral-r4: sealed round-4 sibling

Family: heldout-v8-spiral (interleaved spiral-out GRE with slew-limited design and known gradient delay: KomaMRI simulation, non-Cartesian reconstruction rerun on hidden delayed measurements).

Unchanged from the family template (round 1 logic, as parameterized in round 3): deliverables, file schemas, the CLI of reconstruct.py, every check in grade_spiral.py and its tolerances, the arm wrapper, v8common.py and koma_replay.py, and the reference design logic. The grader reads the matrix from task.json and the hidden delays from private/hidden/hidden_params.json; no grader constant changed.

New instance (differs from rounds 1 and 3; round 2 had no v8 sibling): matrix 36 x 36, FOV 0.234 m, slice 4.5 mm, 11 isochromats per column over +-3.6 mm, TE 2.7 ms, TR 3.0 s (T1 <= 0.6 s), readout at most 9 ms, gradient limits 22 mT/m and 90 T/m/s, coverage disc 18/fov_m, interleaves 1 to 36, hidden gradient delays -4 us and +10 us (bound 11 us), new geometry and tissues, seeds 95601 (public) and 95691 (hidden). The prompt has no instance numbers and is unchanged.

Reference: 6 interleaves of a time-optimal Archimedean spiral (2.28 ms readout, 4 us dwell); about 8e3 isochromats.

Validation (private/validation/VALIDATION.md, summary.json; all through the _arm grader with KomaMRI replay): reference pass; positives 2/2 pass; negatives 6/6 fail as targeted.
Controls: reference; pos_alt_design (12 interleaves, 2 us dwell); pos_gridding_dcf; negatives neg_slew_violation, neg_undersampled, neg_no_slice_rephaser, neg_recon_ignores_delay, neg_recon_delay_wrong_sign, neg_simulated_other_sequence, each failing its targeted check(s).

Regenerate: python private/generate.py; validate: python private/validation/run_validation.py (radial-gre-venv interpreter, KomaMRI via juliacall, one thread).

