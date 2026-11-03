# RECON-01 · Fat fraction and R2* from multi-coil k-space

- Task ID: RECON-01
- Legacy ID: v7-dixonraw

- Domain: Reconstruction
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (11): deliverables_present, report_schema, environment_record, readme_validation_limitations, public_pdff_vials, public_r2s_vials, entrypoint_runs_on_public_inputs, hidden_case1_pdff_vials, hidden_case1_r2s_vials, hidden_case2_pdff_vials, hidden_case2_r2s_vials

## Task (example instance)

~~~text
Reconstruct quantitative fat-fraction and R2* maps from the raw multi-echo gradient-echo dataset described in task.json. You are given uncombined multi-coil k-space for every echo, a noise-only acquisition, a relative transmit-field (B1) map and the acquisition parameters, including the fat spectrum, in params.json. The k-space and signal conventions, the endpoint definitions, the accuracy targets and the file interfaces are in task.json.

Write a standalone entrypoint, dixon_pdff.py, that reads one input directory and writes proton-density fat fraction (PDFF) and R2* maps on the requested image grid. Keep all custom code in that single file and read every parameter from the inputs, because it will be rerun on other acquisitions with different echo times, flip angles, repetition times, field maps, coil arrangements and field strengths. Run it on the public inputs and return the result.

Use established tools or libraries where they help, and keep your own code minimal and readable. Decide which reconstruction steps and physical corrections are needed to turn this raw data into proton-density fat fraction, and justify them.

Return the runnable code, the output files listed in task.json, a figure with the PDFF, R2* and field maps, an environment record with Python and package versions, and a README.md describing your validation evidence and the limitations of the result. No clinical interpretation is requested. Expect to spend about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

