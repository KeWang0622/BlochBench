# Sealed sibling heldout-v6-pilotdesign-r4 (same family, deliverables, schema, checks and tolerances as heldout-v6-pilotdesign)

Built from the round-3 sibling's code. Grader logic (grade_pilotdesign.py, grade_pilotdesign_arm.py) unchanged; it reads instance data from
key.json/task.json and the column names from pilot_stats.py.

New instance: biomarker femorotibial cartilage T2 (ms), the two knees as the paired sub-unit (column knee, value cartilage_t2_ms; groups early_oa
and control). Test-retest pilot of 22 volunteers (V01..V22, 6 days apart; QC failure V15 session 1, a low outlier), group pilot of 18 early
knee-osteoarthritis patients (OA01..OA18; QC failure OA07) and 15 controls (CT01..CT15). Generator seed 70455 (seeds 70451-70454 were screened
and discarded only for implausible pilot differences or variance mixes), variance components mu 41.5, between 2.3, asymmetry 0.8, session 0.55,
side 0.85 ms; true group difference 2.9 ms. Studies: acute treadmill-loading challenge (effect 1.1 ms) and early-OA versus control comparison
(effect 2.0 ms), alpha 0.05, power 0.85 (rounds 1-3 used 0.90/0.90/0.80), non-evaluable fraction 0.15. Vocabulary unit 'leg' replaced by 'knee'.
Prompt reworded. Controls renamed for the knee sub-unit (knee_as_statistical_unit, icc_on_single_knee_values), otherwise unchanged.

Key values: n = 21 analysable test-retest participants, within-subject SD 0.850 ms (CI 0.654-1.214), RC 2.355 ms, ICC(2,1) 0.913
(0.801-0.963); pilot difference 3.47 ms (pooled CI 1.82-5.12), pooled SD 2.280 ms, n 17/15; acute paired n 11 evaluable / 13 enrolled
(accepted 10-15); group n 24 per group / 29 enrolled (accepted 22-27).

Validation (ROOT/work/radial-gre-venv/bin/python): reference passes 14/14 checks (also through grade_pilotdesign_arm.py);
negative controls 11/11 fail their targeted check; positive controls 2/2 pass. Outputs in private/validation/ (summary.json).
