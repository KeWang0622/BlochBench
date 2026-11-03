# heldout-v8-mprage-r4: sealed round-4 sibling

Family: heldout-v8-mprage (3D MP-RAGE with an inversion time that nulls one T1; Pulseq export, KomaMRI simulation of the exported file, 3D Cartesian reconstruction rerun on a hidden object).

Unchanged from the family template (round 1 logic, as parameterized in round 3): deliverables, file schemas, CLI of reconstruct.py, every check in grade_mprage.py and its tolerances (null metric <= 1%, cycle steady state within 2%, TE 5 us, TR/cycle 1 us, flips 1%/2%, sampling tolerance 0.02 cycles/m, nulled-vial endpoint <= 0.30, hidden rerun NRMSE <= 3%), the arm wrapper grade_mprage_arm.py, v8common.py and koma_replay.py. The grader reads matrix, FOV, flip angle and null T1 from task.json; the only grader constant changed is the steady-state test-column T1 list (SS_T1 = 1.9, 1.3, 0.45 s), which spans the new object T1 range as in earlier rounds.

New instance (differs from rounds 1 and 3; round 2 had no v8 sibling): matrix 20 x 12 x 6, FOV 0.240 x 0.144 x 0.054 m, 72 isochromats per 9 mm partition column, readout flip 7 deg, readout TR 6.5 ms, cycle period 2.3 s, TE 2.8 ms, null T1 0.78 s, gradient limits 30 mT/m and 110 T/m/s, object T1 range 0.45 to 1.9 s, new body/vial geometry and tissue values, seeds 94817 (public) and 94853 (hidden). Prompt changed only in the null T1.

Reference TI (cycle steady-state bisection) 0.4998 s; 5 dummy cycles; sequence duration 25.3 s; about 4.3e4 isochromats.

Validation (private/validation/VALIDATION.md, summary.json; all through grade_mprage_arm.py): reference pass; positives 2/2 pass; negatives 6/6 fail as targeted.
Controls: reference; pos_alt_design (centre-out partition order, 50 deg RF-spoiling increment, 400 cycles/m spoiler, 20 us dwell, 6 dummies); pos_alt_spoiling (117 deg, 500 cycles/m, 20 us dwell, 7 dummies); negatives neg_naive_ti, neg_ti_to_train_start, neg_two_dummy_cycles, neg_te_to_adc_start, neg_recon_kz_order, neg_simulated_other_sequence, each failing its targeted check(s).

Regenerate: python private/generate.py; validate: python private/validation/run_validation.py (radial-gre-venv interpreter, KomaMRI via juliacall, one thread).

