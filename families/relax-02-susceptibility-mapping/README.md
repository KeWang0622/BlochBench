# RELAX-02 · Quantitative susceptibility mapping

- Task ID: RELAX-02
- Legacy ID: v4-qsm

- Domain: Relaxometry and QSM
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 45 min
- Instances recorded: 3 (instances.json)
- Automated checks (11): deliverables_present, public_schema, public_local_field, public_roi_susceptibility, public_chi_map, hidden_rerun_runs, hidden_schema, hidden_local_field, hidden_roi_susceptibility, hidden_chi_map, report_schema

## Task (example instance)

~~~text
We have a 3D multi-echo gradient-echo head scan and need quantitative susceptibility maps, with the susceptibility of the deep grey-matter nuclei expressed relative to ventricular CSF. Please produce the local field map and the susceptibility map and report the regional values.

task.json describes the data files, the phase scaling and sign convention of the scanner export, the acquisition geometry (including the B0 direction and the voxel size), the field model, the reference region, the output files and the entrypoint interface; it is the authority. Use established open-source tools where they help and write the glue code yourself.

Estimate the field from the multi-echo phase, remove the background field from sources outside the brain, invert the dipole model and summarise the regions of interest. qsm.py must be a standalone entrypoint that runs from an input directory alone, because it will be run again on another subject with different echo times, resolution, matrix and head orientation. Please return the maps, the ROI results, a figure, runnable code, a record of the environment and versions, report.json, and a short note on how you validated each step and what its limitations are. The data are simulated, so no clinical interpretation is needed.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

