# heldout-v8-ute-r4: sealed round-4 sibling

Family: heldout-v8-ute (2D UTE with half-pulse pairs and radial centre-out spokes: slice profile of the summed pair, KomaMRI simulation, non-Cartesian reconstruction rerun on a hidden object).

Unchanged from the family template (round 1 logic, as parameterized in round 3): deliverables, file schemas, the CLI of reconstruct.py, every check in grade_ute.py and its tolerances, the arm wrapper, v8common.py and koma_replay.py, and the reference design logic. The grader reads matrix, flip angle and the out-of-slice bound from task.json; the only grader constant changed is the slice-profile z grid (61 points at 0.55 mm, matching the new object z sampling as in round 3).

New instance (differs from rounds 1 and 3; round 2 had no v8 sibling): matrix 26 x 26, FOV 0.208 m, slice 5.5 mm (FWHM window 4.4 to 7.7 mm, out-of-slice bound 8.25 mm), 61 isochromats per column at 0.55 mm over +-16.5 mm, flip 11 deg, TR 6.5 ms, UTE echo time at most 0.24 ms, gradient limits 34 mT/m and 135 T/m/s, coverage disc 13/fov_m, T1 0.3 to 1.05 s and T2 0.65 ms to 0.09 s, new geometry and tissues, seeds 98601 (public) and 98691 (hidden). The prompt has no instance numbers and is unchanged.

Reference: 0.6 ms half sinc pulse pairs with alternating slice polarity and ramp compensation, 80 spoke pairs, 10 mT/m readout, 2 us dwell, 240 dummy excitations, RF spoiling 117 deg; about 2.3e4 isochromats over about 400 repetitions.

Validation (private/validation/VALIDATION.md, summary.json; all through the _arm grader with KomaMRI replay): reference pass; positives 2/2 pass; negatives 6/6 fail as targeted.
Controls: reference; pos_alt_design (96 spokes, 14 mT/m readout, 450 cycles/m spoiler); pos_alt_design2 (0.8 ms half pulse, 88 spokes, 3 us dwell); negatives neg_no_polarity_alternation, neg_no_ramp_compensation, neg_late_te, neg_adc_on_flat_top, neg_too_few_spokes (44 spokes), neg_simulated_other_sequence, each failing its targeted check(s).

Regenerate: python private/generate.py; validate: python private/validation/run_validation.py (radial-gre-venv interpreter, KomaMRI via juliacall, one thread).

