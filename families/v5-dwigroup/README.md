# v5-dwigroup

- Domain: Diffusion
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (13): deliverables_present, subject_results_schema, public_fa_accuracy, public_md_accuracy, public_v1_accuracy, group_difference_accuracy, group_welch_consistency, hidden_rerun_runs, hidden_fa_accuracy, hidden_md_accuracy, hidden_v1_accuracy, hidden_maps, readme_validation_limitations

## Task (example instance)

~~~text
Please build a processing pipeline for a small two-group diffusion MRI study that goes from the scanner export to regional tensor metrics and a group comparison. The study has 14 subjects, controls and patients. For each subject you get the magnitude diffusion series, a label map on the same voxel grid and an acquisition sidecar that lists, for every volume, the nominal b-value, the gradient direction as exported by the scanner and the acquisition time. task.json documents the coordinate conventions of the images and of the gradient directions, how the effective b-value follows from the stored direction vectors, the scanner signal drift in the data, the exact regional and group endpoints, the file schemas and the expected accuracy.

Use established open-source tools where they fit and write the connecting code yourself: read the gradient table correctly, correct the drift, fit the diffusion tensor, extract regional FA, MD and principal directions, and run the two-group comparison for tract A. process_subject.py must be a standalone entrypoint that processes one subject from its three files, because I will run it again on further subjects acquired with another protocol variant and positioned differently in the scanner.

Please return runnable code, the per-subject and group result files, a QC figure, a record of the environment and a README that explains how you checked the gradient directions and the drift correction and what the limitations are. Plan for about an hour of work.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

