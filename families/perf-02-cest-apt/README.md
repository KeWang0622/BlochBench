# PERF-02 · APT-weighted CEST mapping

- Task ID: PERF-02
- Legacy ID: v7-cestapt

- Domain: Perfusion and CEST
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (14): deliverables_present, report_schema, environment_record, readme_validation_limitations, public_mtrasym_rois, public_mtrasym_voxelwise, public_b0_map, entrypoint_runs_on_public_inputs, hidden_case1_mtrasym_rois, hidden_case1_mtrasym_voxelwise, hidden_case1_b0_map, hidden_case2_mtrasym_rois, hidden_case2_mtrasym_voxelwise, hidden_case2_b0_map

## Task (example instance)

~~~text
Produce an amide proton transfer (APT) weighted CEST map from the single-slice dataset described in task.json. You are given a CEST Z-spectrum series with an unsaturated reference image and a separately acquired WASSR series from the same slice; the frequency conventions, units, endpoint definition, accuracy targets and file interfaces are all in task.json, and the per-dataset parameters are in params.json.

Write a standalone entrypoint, cest_apt.py, that reads one input directory and writes the MTRasym(3.5 ppm) map in percent together with the B0 map you used. Keep all custom code in that single file and read everything from the inputs, because it will be rerun on other datasets with different B0 fields, saturation settings, offset lists, acquisition orders and field strengths. Run it on the public inputs and return the result.

Use established tools or libraries where they help, and keep your own code minimal and readable. Decide from the acquisition description which corrections the asymmetry analysis needs, and justify them.

Return the runnable code, the output files listed in task.json, a figure showing the MTRasym and B0 maps, an environment record with Python and package versions, and a README.md describing your validation evidence and the limitations of the result. No clinical interpretation is requested. Expect to spend about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

