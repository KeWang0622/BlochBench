# Sealed sibling heldout-v5-safecpmg-r4 (same family, deliverables, schemas, checks and tolerances as heldout-v5-safecpmg)

Built from the round-3 sibling's code. Grader logic (grade_safecpmg.py, grade_safecpmg_arm.py) unchanged; the instance limits live in
seqcheck.LIM and the hidden noise in hidden/hidden_samples.json.

New instance parameters: hardware 38 mT/m and 150 T/m/s; B1+rms limit 0.55 uT, B1 peak 12.0 uT; PNS model S_r 52 T/m/s, c 0.34 ms (limit 0.80
unchanged); Gz rms 7.0 mT/m; ESP <= 12 ms; 26 <= N <= 40 echoes; TR <= 1.0 s; crusher moments 800-2000 cycles/m; sample layout unchanged
(12 mm, 2000 Hann-weighted isochromats); new public samples (T2 48-265 ms, B1 0.79-1.19, T1 0.70-2.00 s) and hidden samples (8 samples, T2
29-290 ms, B1 0.79-1.21, T1 0.4-2.2 s drawn with seed 81233), hidden noise sigma 0.0008 with seed 5309. Reference design: 1 ms 90 deg block,
28 block refocusing pulses of 120 deg / 7.0 ms (CPMG phase), ESP 12 ms, z crushers 1000 cycles/m at 20 mT/m and 60 T/m/s, TR 1.0 s
(B1+rms 0.529 uT, PNS 0.56, Gz rms 4.86 mT/m). Controls re-parameterised: N1 180 deg / 3.5 ms refocusing (B1+rms 1.07 uT), N2 TR 0.6 s with
B1+rms reported over 1.0 s (0.68 uT), N3 crushers at 38 mT/m and 150 T/m/s (PNS 1.21), N6 model ESP 11 ms, N8 simulated 180 deg / 3.5 ms
variant, N9 crushers 400 cycles/m; positives P1 100 deg / 5.5 ms / ESP 11 ms / 32 echoes and P2 122 deg / 7.5 ms / 0.8 ms excitation /
ESP 12 ms / 28 echoes / 5-sample ADC / 900 cycles/m crushers. Prompt reworded. Grader logic and tolerances unchanged (T2 3%, B1 0.03,
report 3%, simulation 0.01, timing 2 us).

Validation (ROOT/work/radial-gre-venv/bin/python, KomaMRI replay): reference passes all 15 checks through grade_safecpmg_arm.py (public T2
error 0.04%, hidden T2 max 0.34%, hidden B1 max 0.002). Negative controls 10/10 fail their targeted check (N1, N2, N3, N4 hidden T2 30%,
N5, N6 hidden T2 12%, N7, N8, N9, N10). Positive controls 2/2 pass (P1 B1+rms 0.531 uT, hidden T2 max 0.36%; P2 B1+rms 0.529 uT, hidden T2
max 0.32%). Logs and summaries in private/validation/.
