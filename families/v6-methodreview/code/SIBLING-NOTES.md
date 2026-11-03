# Sealed sibling heldout-v6-methodreview-r4 (same family, deliverables, schema, checks and thresholds as heldout-v6-methodreview)

New instance: a new synthetic manuscript (29 paragraphs/tables) on deep-learning reconstruction of threefold undersampled FLAIR* for central
vein sign (CVS) assessment in suspected multiple sclerosis (rounds 1-3: prostate DWI reconstruction, nigral QSM, cardiac T1/ECV). Eight planted
problems at new locations, K1-K8: K1 network checkpoint and denoising weight tuned on the study cohort's reference reads (P06;
test_set_leakage_or_tuning), K2 lesion-level chi-square with lesions as independent observations (P11, P19), K3 Pearson correlation used as
agreement/interchangeability (P09, P17; inappropriate_statistical_test), K4 participant counts text vs Table 1 (P14, T1), K5 total lesion volume
in mm3 while Table 3 gives mL (P21; unit_error or text_table_inconsistency), K6 post hoc removal of participants with borderline CVS proportions
(P16), K7 vein-visibility comparison restricted to lesions with a vein marked on DL-FLAIR* (P08, P18; circular_analysis), K8 claim that the method
makes lumbar puncture and follow-up MRI unnecessary and should replace the McDonald criteria (P24). Seventeen sound paragraphs/tables, several
written as decoys (external training cohort, blinded randomized reads with washout, prespecified 40% CVS rule, Holm-corrected correlations,
protocol-fixed image-quality exclusion, lesion-level kappa table). Prompt reworded. Grader (grade_methodreview.py, grade_methodreview_arm.py)
unchanged; key thresholds unchanged (recall >= 7 of 8, at most 2 false accusations, quotes >= 10 characters, at most 25 issues, review.md <= 2000
words, recommendation major_revision or reject). Controls re-targeted to the new paragraphs (same control designs as round 3).

Validation (ROOT/work/radial-gre-venv/bin/python): reference passes 8/8 checks with recall 8/8 (also through grade_methodreview_arm.py);
negative controls 9/9 fail their targeted check; positive controls 2/2 pass (alternative locations/categories with two false accusations;
seven of eight found). Outputs in private/validation/ (summary.json).
