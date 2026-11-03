# Validation of the grader

Expected: reference and positive controls pass every check; each negative control fails, ideally on the check it targets.

| Control | Kind | Targeted checks | Checks failed |
|---|---|---|---|
| ref | reference | - | none (all pass) |
| ref_arm | reference | - | none (all pass) |
| fft_shift | negative | per_scan_roi_accuracy | per_scan_roi_accuracy, t2map_files_consistent, hidden_rerun_mapping, stats_reproduce_own_table, stats_vs_truth |
| te_seconds | negative | per_scan_roi_accuracy | per_scan_roi_accuracy, t2map_files_consistent, hidden_rerun_mapping, stats_vs_truth |
| ses1_label | negative | per_scan_roi_accuracy | per_scan_roi_accuracy, t2map_files_consistent, stats_vs_truth |
| zero_filled | negative | hidden_rerun_mapping | per_scan_roi_accuracy, hidden_rerun_mapping |
| scans_as_units | negative | stats_vs_truth | stats_reproduce_own_table, stats_vs_truth, hidden_rerun_stats |
| student_t | negative | hidden_rerun_stats | stats_reproduce_own_table, hidden_rerun_stats |
| cohen_d | negative | hidden_rerun_stats | stats_reproduce_own_table, hidden_rerun_stats |
| wsd_no_sqrt2 | negative | hidden_rerun_stats | stats_reproduce_own_table, hidden_rerun_stats |
| drop_incomplete | negative | hidden_rerun_stats | stats_reproduce_own_table, stats_vs_truth, hidden_rerun_stats |
| sign_flip | negative | stats_vs_truth | stats_reproduce_own_table, stats_vs_truth, hidden_rerun_stats |
| lowres_sens | positive | - | none (all pass) |
| grappa_rss | positive | - | none (all pass) |
