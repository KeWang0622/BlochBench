# heldout-v8-sedwi-r4: sealed round-4 sibling

Family: heldout-v8-sedwi (single-shot spin-echo EPI diffusion: b-values from the exported waveforms, KomaMRI simulation with the stated per-volume diffusion attenuation, ADC fit rerun on a hidden object).

Unchanged from the family template (round 1 logic, as parameterized in round 3): deliverables, file schemas, the CLI of reconstruct.py, every check in grade_sedwi.py and its tolerances, the arm wrapper, v8common.py and koma_replay.py, and the reference design logic. The grader reads matrix and b target from task.json; no grader constant changed.

New instance (differs from rounds 1 and 3; round 2 had no v8 sibling): matrix 24 x 24, FOV 0.204 m, slice 4.5 mm, 135 isochromats per column over +-6.75 mm, TE 72 ms, TR 3.2 s, b = 1200 s/mm2, gradient limits 42 mT/m and 160 T/m/s, new body/vial geometry, T1, T2 and diffusivities (0.4e-3 to 2.8e-3 mm2/s), seeds 94401 (public) and 94491 (hidden). The prompt has no instance numbers and is unchanged.

Reference: diffusion amplitudes iterated on the waveform b-matrix to 1200 s/mm2 per direction, 1600 cycles/m crushers, one dummy repetition; about 4.3e4 isochromats. Author note: a first draft used b = 900 s/mm2, where the reference z-diffusion lobe moment after the refocusing pulse (about 3.0e4 cycles/m) coincided with a multiple of the inverse 0.1 mm isochromat spacing, so the discretized object failed to dephase the refocusing pulse FID and the reference ADC map failed; b was moved to 1200 s/mm2 (residual z-volume deviation 0.8%) and validation was rerun from scratch.

Validation (private/validation/VALIDATION.md, summary.json; all through the _arm grader with KomaMRI replay): reference pass; positives 2/2 pass; negatives 6/6 fail as targeted.
Controls: reference; pos_alt_timing (diffusion lobes 4 ms shorter, 2200 cycles/m crushers); pos_alt_crushers (1000 cycles/m); negatives neg_nominal_stejskal_tanner, neg_no_dummy_volume, neg_diffusion_lobes_opposite_polarity, neg_spin_echo_misaligned, neg_no_slice_rephaser, neg_simulated_other_sequence, each failing its targeted check(s).

Regenerate: python private/generate.py; validate: python private/validation/run_validation.py (radial-gre-venv interpreter, KomaMRI via juliacall, one thread).

