# Sealed sibling heldout-v6-honestresults-r4 (same family, deliverables, schema, checks and rules as heldout-v6-honestresults)

New instance: a new synthetic trial, REMYEL-52 (52-week oral remyelinating study drug versus placebo in relapsing multiple sclerosis, 136
randomised, 5 sites; rounds 1-3 were a liver trial, an antifibrotic cardiac trial and a muscular-dystrophy trial). Result entries E01..E18 keep
the same roles: E01 primary (week-52 lesion myelin water fraction, adjusted difference +0.9 percentage points, 95% CI 0.2 to 1.6, p = 0.011,
n = 121); E04 key secondary recorded in seconds and reported in ms with 1 decimal (lesion T1 from MP2RAGE, -18.2 ms, 95% CI -41.5 to 5.1, Holm
p = 0.12, CI includes zero); E05 secondary in mL (whole-brain volume, +4 mL, 95% CI 1 to 7, Holm p = 0.042); within-group absolute (pp) and
relative changes; post hoc subgroup by disease duration (below 10 years vs 10 years or more, interaction p = 0.21, one subgroup CI includes
zero); adherence, adverse events, baseline values. New refs.bib (8 keys: myelin water imaging, 3D GRASE, MP2RAGE, brain-change analysis,
absence of evidence, CONSORT, Holm, subgroup-reporting references). Rules R1-R10 restated for the new endpoints (lesion T1 replaces water T2
in R2/R4/R5/R6; MWF replaces fat fraction; whole-brain volume replaces contractile volume; reporting units unchanged: percent,
percentage_points, ms, mL, count). key.json null keyword 'lesion t1'. Grader logic unchanged (KEY-driven; schema label only). Prompt reworded.
Negative controls re-targeted to the new text (same 15 designs; the unit control is named water_t2_left_in_seconds for continuity with
rounds 1-3 and here leaves lesion T1 in seconds).

Validation (ROOT/work/radial-gre-venv/bin/python): reference passes 16/16 checks (abstract 176 words; also through
grade_honestresults_arm.py); negative controls 15/15 fail their targeted check; positive controls 2/2 pass. Outputs in private/validation/
(summary.json).
