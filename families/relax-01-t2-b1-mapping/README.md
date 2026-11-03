# RELAX-01 · T2 and transmit-field mapping from imperfect echoes

- Task ID: RELAX-01
- Legacy ID: v4-t2epg

- Domain: Relaxometry and QSM
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 45 min
- Instances recorded: 3 (instances.json)
- Automated checks (18): deliverables_present, environment_record, public_t2_grid, public_t2_voxel_accuracy, public_t2_label_bias, public_t2_low_b1_bias, public_b1_accuracy, public_roi_t2_endpoint, report_consistent, rerun_public_runs, rerun_public_reproduces_submitted, hidden_runs, hidden_t2_grid, hidden_t2_voxel_accuracy, hidden_t2_label_bias, hidden_t2_low_b1_bias, hidden_b1_accuracy, hidden_roi_t2_endpoint

## Task (example instance)

~~~text
Please produce T2 maps from a CPMG multi-echo spin-echo scan whose refocusing pulses are imperfect, and treat the problem the way a quantitative-MRI researcher would.

The inputs (a 4D magnitude NIfTI holding the echo train, a label image and an acquisition description) and all the conventions you need are set out in task.json: pulse and echo timing, the refocusing phase, the possible range of the unknown transmit-field (B1+) scale, the relaxation ranges, output units and file interfaces. Treat task.json as authoritative.

The refocusing flip angle departs from its nominal value across the object, so stimulated-echo pathways enter the echo trains. Estimate each voxel's true T2 together with its B1+ scale, write T2 and B1+ maps on the input grid, and report the mean T2 of every labelled region. Use established open-source tools where they help and write the glue code yourself.

fit_t2.py has to be a standalone entrypoint that needs nothing but an input directory, because it will be rerun on other scans with a different echo spacing, number of echoes, nominal refocusing angle, grid and transmit field. Return the maps, the region values, a figure of the maps, runnable code, a record of the software environment and its versions, and a short note on how you validated the fit and where it is limited. The data are simulated; no clinical interpretation is needed.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

