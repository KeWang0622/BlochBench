# Sealed sibling heldout-v5-irt1-r4 (same family, deliverables, schemas and pass rules as heldout-v5-irt1)

Built from the round-3 sibling's code. Grader logic unchanged; only the instance constants in grade_irt1.py (grid, FOV, spoke/sample counts,
inversion times, recovery delay, hardware limits, TE limit, periodic-state T1 set, fit-only image phase/echo weighting/noise seed) and the
schema tag changed.

New instance parameters: FOV 0.200 m, 40x40 grid (5 mm); 40 spokes x 40 samples per inversion time (sample 20 at k = 0, angles pi*s/40);
five inversion times 45, 130, 330, 800, 1600 ms (200 ADCs); recovery delay 2.4 s; TE <= 3.2 ms; limits 36 mT/m, 150 T/m/s, B1 peak 8.0 uT
(inversion block >= 1.47 ms); periodic-state range T1 0.35-2.0 s (grader T1 set 0.35, 0.7, 1.1, 1.5, 2.0 s); new public object (6 vials,
labels 2..7: a central vial and a ring of five, T1 0.40-1.92 s, body 1.10 s, body rotated -0.35 rad) and new hidden object (4 vials on a ring,
T1 0.50-1.80 s, body 0.90 s, rotated 0.4 rad); fit-only grader images with a new phase pattern (0.3 - 1.4 x/FOV + 1.9 y/FOV), echo weighting
exp(-1.0 ms/T2) and noise seed 6211. Reference design: 1.8 ms block inversion (6.5 uT), 1.0 ms block excitation, 20 us dwell, one
non-acquired 90 deg preparation (TE 1.28 ms). Controls re-parameterised: b1_violation 1.0 ms inversion block (11.7 uT > 8 uT), alt_sequence
2.4 ms inversion / 1.3 ms excitation / 16 us dwell. Prompt reworded. Thresholds unchanged (vial 6%, voxel median 4%, fit-only 3% / 1.5%,
replay 5%, trajectory 0.05 cycles/m, TI 0.5 ms, TD 1 ms, periodic 0.5%).

Validation (grader interpreter ROOT/work/radial-gre-venv/bin/python): reference passes 11/11 checks, arm wrapper passes; public vial max
1.1%, voxel median 1.2%; hidden vial max 2.3%, voxel median 0.6%; fit-only vial max 0.9%, voxel median 0.2%. Negative controls 7/7 fail
their targeted check (no_half_shift 2.50 cycles/m, b1_violation 11.7 uT, no_dummy periodic deviation 43%, swap_xy_sim replay error 20%,
recon_swap, twoparam, naive_mag). Positive controls 3/3 pass (magnitude_fit, direct_recon public 2.8%/1.6%, alt_sequence).
Informational: non-iterative DCF gridding fails (public vial max 11.0%, hidden 13.0%). A first validation launch was interrupted during the
reference simulation (process ended with its shell); its partial workspace was moved to sealed-r4/_trash and the full run repeated.
Logs in private/validation/.
