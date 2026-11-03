# Sealed sibling heldout-v6-gapproposal-r4 (same family, deliverables, schema, checks and tolerances as heldout-v6-gapproposal)

New instance: a new synthetic corpus of 35 cardiac-MRI records on myocardial inflammation (M01..M35; rounds 1-3 used renal, liver and kidney
corpora) with new technique, population and reference codes (T2, T1, ECV, LGE, STRAIN, EDR; HV, MYO, DCM, ICI, SARC; BX = at least 14
leukocytes/mm2 including at least 7 CD3+ T lymphocytes/mm2 on endomyocardial biopsy, EVENT = cardiovascular death, heart-failure hospitalisation or
sustained ventricular arrhythmia; new TREAT code for a before/after-treatment study), a new explaining-factor vocabulary (exercise_before_mri,
mri_to_biopsy_interval, histology_criteria added) and a new controls vocabulary (exercise abstinence, corticosteroid timing and blood-pool-excluded
ROI placement added). Planted structure: replicated finding T2/MYO/BX (M03, M08, M14, M21); contradiction T1/MYO/BX (significant M06, M12, M27;
null M10, M17, M30) explained by mri_to_biopsy_interval (MRI within 3 days of biopsy vs 14-30 days after; supporting record M35; field strength,
vendor, MOLLI/ShMOLLI, slice thickness and sample size mixed; ROI placement and histology criteria identical); M12 is a boundary decoy (smallest
group exactly 15, not underpowered); underpowered records M19 (groups 7 and 9; dependents M28, M32) and M33 (a new feature: a correlation study
without groups in 22 participants, located in the target population; dependent M26); unique gap T2/ICI/BX (G3: M03, M08, M14, M21, M11; G4: M13,
M22; G5: M16, M24), checked by enumeration in build_inputs.py. Within-subject studies have n >= 30 so that the underpowered definition is
unambiguous. Sample-size rules now use power 0.90; accepted Delta 3.4-5.4 ms (sources M03, M08, M14, M21, M11), SD 3.0-4.1 ms, tolerance 0.1 ms
(key range_tol; the grader already reads it), smaller-group fraction 0.325-0.366, non-evaluable fraction 0.100-0.154. Required controls: blinded
analysis, exercise abstinence (M04), corticosteroid timing (M23), fixed field strength and sequence (M02). Prompt reworded. Grader unchanged
except the schema label.

Validation (ROOT/work/radial-gre-venv/bin/python): reference passes 17/17 checks (Delta 4.46 ms, SD 3.50 ms, 13 per group, 43 to enrol;
also through grade_gapproposal_arm.py); negative controls 17/17 fail their targeted check; positive controls 2/2 pass. Outputs in
private/validation/ (summary.json).
