# heldout-v8-epinav-r4: sealed round-4 sibling

Family: heldout-v8-epinav (single-shot GRE EPI with ramp sampling and navigator echoes: KomaMRI simulation, reconstruction rerun on hidden measurements with unknown gradient delays).

Unchanged from the family template (round 1 logic, as parameterized in round 3): deliverables, file schemas, the CLI of reconstruct.py, every check in grade_epinav.py and its tolerances, the arm wrapper, v8common.py and koma_replay.py, and the reference design logic. The grader reads the matrix from task.json and the hidden delays from private/hidden/hidden_params.json; no grader constant changed.

New instance (differs from rounds 1 and 3; round 2 had no v8 sibling): matrix 24 x 24, FOV 0.21 m, slice 4.5 mm, 31 isochromats per column over +-6.75 mm, effective TE 24 ms, echo spacing at most 0.40 ms, gradient limits 28 mT/m and 140 T/m/s, hidden delays -4.6 us and +3.1 us (bound 6 us, unchanged), new geometry and tissues, seeds 96601 (public) and 96691 (hidden). The prompt has no instance numbers and is unchanged.

Reference: ramp-sampled EPI with 120 us ramps and 120 us flat top (ESP 0.36 ms), 4 us dwell, three navigator echoes; about 1e4 isochromats. Author note: a first draft used 160 us ramps with a 40 us flat top; with this smaller matrix the family positive control pos_linear_phase_nav (classic linear-phase navigator correction) then exceeded the 8% background limit on the delayed hidden measurements, so the reference readout was changed to a longer flat top and validation was rerun from scratch.

Validation (private/validation/VALIDATION.md, summary.json; all through the _arm grader with KomaMRI replay): reference pass; positives 2/2 pass; negatives 7/7 fail as targeted.
Controls: reference; pos_alt_design (140 us ramps, 100 us flat top, ESP 0.38 ms, 3 us dwell); pos_linear_phase_nav; negatives neg_no_ghost_correction, neg_uniform_kx_recon, neg_flat_top_only, neg_blip_during_adc, neg_te_wrong_echo, neg_no_slice_rephaser, neg_simulated_other_sequence, each failing its targeted check(s).

Regenerate: python private/generate.py; validate: python private/validation/run_validation.py (radial-gre-venv interpreter, KomaMRI via juliacall, one thread).

