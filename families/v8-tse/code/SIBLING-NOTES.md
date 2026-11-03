# heldout-v8-tse-r4: sealed round-4 sibling

Family: heldout-v8-tse (2D multi-shot turbo spin echo: Pulseq export, KomaMRI simulation, Cartesian reconstruction rerun on a hidden object).

Unchanged from the family template (round 1 logic, as parameterized in round 3): deliverables, file schemas, the CLI of reconstruct.py, every check in grade_tse.py and its tolerances, the arm wrapper, v8common.py and koma_replay.py, and the reference design logic. The grader reads matrix, echo-train length, shot count, refocusing angle and echo-spacing limit from task.json; the only grader constant changed is the list of echo-train test columns (T1, T2) = (1.6, 0.28), (0.35, 0.045), (1.0, 0.14), (0.7, 0.07) s, which spans the new stated T1/T2 ranges as in earlier rounds.

New instance (differs from rounds 1 and 3; round 2 had no v8 sibling): matrix 18 x 18, FOV 0.216 m, slice 3.5 mm, 105 isochromats per column over +-5.25 mm, 2 acquired shots of 9 echoes (echo-train length 9), refocusing flip 135 deg, effective TE 44 ms, TR 2.0 s, echo spacing at most 13 ms, gradient limits 26 mT/m and 150 T/m/s, test-column ranges 0.35 <= T1 <= 1.6 s and 0.045 <= T2 <= 0.28 s, new body/vial geometry and tissue values, seeds 93201 (public) and 93291 (hidden). The prompt has no instance numbers and is unchanged.

Reference: CPMG train with ESP 8.8 ms and linear segmented ordering (ky = 0 on echo 5 of shot 2), 2 ms refocusing pulses, 800 cycles/m crushers, 30 us dwell, one dummy shot; about 2e4 isochromats.

Validation (private/validation/VALIDATION.md, summary.json; all through the _arm grader with KomaMRI replay): reference pass; positives 2/2 pass; negatives 9/9 fail as targeted.
Controls: reference; pos_alt_ordering (ESP 11 ms with ky = 0 on echo 4, 1.8 ms refocusing pulses, 1200 cycles/m crushers); pos_no_dedicated_crushers; negatives neg_cp_not_cpmg, neg_echo_off_readout_centre, neg_prephaser_wrong_sign, neg_no_pe_rewinder, neg_no_slice_rephaser, neg_no_dummy_shot, neg_centre_first_echo, neg_recon_acquisition_order, neg_simulated_other_sequence, each failing its targeted check(s).

Regenerate: python private/generate.py; validate: python private/validation/run_validation.py (radial-gre-venv interpreter, KomaMRI via juliacall, one thread).

