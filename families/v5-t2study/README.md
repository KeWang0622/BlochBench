# v5-t2study

- Domain: Study design and statistics
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (9): deliverables_present, per_scan_table_schema, per_scan_roi_accuracy, t2map_files_consistent, hidden_rerun_mapping, stats_reproduce_own_table, stats_vs_truth, hidden_rerun_stats, report_schema

## Task (example instance)

~~~text
Attached are the raw data of a small scan-rescan study comparing T2 in a target region between patients and controls. Please carry it from the undersampled multi-coil k-space through to the pre-registered statistical result.

Eighteen participants were each booked for two scans. The second session of one participant was lost to a receive-coil failure and is not included, so there are 35 scans. Each scan is a multi-echo spin-echo acquisition stored as undersampled multi-coil k-space with a noise prescan and a label map; no coil sensitivity maps are provided. task.json defines the data conventions, the signal model, the per-scan measurement, the statistical analysis plan (with the rule for subjects that have only one scan and the repeatability measures to report), the accuracy targets, the deliverables and the file schemas.

Reconstruct every echo with a suitable parallel-imaging method, fit one T2 map per scan, extract the ROI value and carry out the analysis plan at the right unit of analysis. Rely on established open-source tools where they help and write the connecting code yourself.

map_t2.py must be a standalone program that maps one scan from its file alone, because I will run it on more scans with other anatomy, coil arrays and T2 values. study_stats.py must be a standalone program that applies the analysis plan to a per-scan table, because I will also run it on other study tables.

Please send back the per-scan maps, the per-scan table, the study statistics, a summary figure, the code, a record of the software environment and a README that describes how you validated each stage and what the limitations are. Expect about an hour of work.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

