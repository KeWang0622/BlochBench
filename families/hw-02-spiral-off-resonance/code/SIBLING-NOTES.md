# Sealed sibling heldout-v5-spiralb0-r4 (same family, deliverables, schemas and pass rules as heldout-v5-spiralb0)

Built from the round-3 sibling's code. Grader logic unchanged; only the instance constants in grade_spiralb0.py (grid, FOV, limits, TE,
readout limit) and the schema tag changed.

New instance parameters: FOV 0.216 m, 40x40 grid (5.4 mm, kmax 92.6 cycles/m); limits 30 mT/m, 125 T/m/s, B1 peak 13 uT; TE 2.4 +- 0.05 ms;
readout <= 22 ms; coverage rule over m, n = -20..19 within 0.95 kmax (tolerance 0.75/FOV unchanged); field-mapping echo times 2.0 and 3.1 ms
(dTE 1.1 ms), field-map SNR 150 with a new phase pattern (0.4 - 1.8 x/FOV + 2.4 y/FOV + 2.5 r^2/FOV^2) and magnitude shading along x; new
public object (5 vials, labels 2..6) and field (-256..163 Hz in the object, new polynomial and line dipole at (0.118, -0.010) m, 125 Hz); new
hidden object (6 vials, labels 2..7) and field (-134..192 Hz, dipole at (-0.020, -0.115) m, -150 Hz); new field-map noise seeds 52817 / 90314.
Reference design: 0.6 ms block excitation, 4 us dwell, 92%/88% gradient/slew margins (12.5 ms readout, 3131 samples). Controls
re-parameterised: slew_violation designed for 195 T/m/s, undersampled spiral turn spacing 1.7/FOV (unchanged), alt_sequence 0.5 ms excitation.
Prompt reworded. Thresholds unchanged (field median 3 Hz / p95 8 Hz, NRMSE 7%, ratio 0.03, phase SD 0.2 rad, replay 5%, coverage 0.75/FOV).

Authoring note: a first parameter draft had weaker fields (public -168..108 Hz, hidden -87..120 Hz); the field coefficients were scaled up
before any validation run so that uncorrected reconstruction clearly fails (spans similar to rounds 1-3).

Validation (ROOT/work/radial-gre-venv/bin/python): reference passes 10/10 checks, arm wrapper passes; public field error 0.63/2.15 Hz,
NRMSE 3.0%, ratio error 0.012, phase SD 0.067 rad; hidden 0.65/2.08 Hz, 3.1%, 0.017, 0.064 rad. Negative controls 9/9 fail their targeted
check (no_correction hidden NRMSE 19.1%, field_sign 76 Hz median, delta_te_ms 38 Hz, field_transposed 57 Hz, time_from_adc_start phase SD
1.06 rad, kxy_swapped 32%, hz_as_rad replay error 77%, slew_violation 185 T/m/s, undersampled_spiral 0.87/FOV). Positive controls 2/2 pass
(time_segmented 3.1%/3.1%, alt_sequence 3.0%/3.1%). Informational: conjugate-phase reconstruction fails the targets (public NRMSE 9.6-11.7%,
ratio errors up to 0.12). Logs: private/validation/validation_log.txt and *_result.json.
