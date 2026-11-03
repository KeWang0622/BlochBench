# v7-fmriglm

- Domain: Functional MRI
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (14): deliverables_present, report_schema, environment_record, readme_validation_limitations, public_psc_bias, public_psc_mae, public_null_calibration, entrypoint_runs_on_public_inputs, hidden_case1_psc_bias, hidden_case1_psc_mae, hidden_case1_null_calibration, hidden_case2_psc_bias, hidden_case2_psc_mae, hidden_case2_null_calibration

## Task (example instance)

~~~text
Analyse the rapid event-related functional MRI run described in task.json. You are given the stored BOLD time series of a 2D multislice acquisition, the event timings, the acquisition timing and the realignment parameters; the signal conventions, the definition of the response amplitude, the accuracy targets and the file interfaces are in task.json.

Write a standalone entrypoint, fmri_glm.py, that reads one input directory and writes two maps: the percent signal change of the response to a single event, and a z statistic for a positive response that is valid under the null hypothesis. Keep all custom code in that single file and read everything from the inputs, because it will be rerun on other runs with different repetition times, slice orders, numbers of dummy volumes, event timings and noise properties. Run it on the public inputs and return the result.

Use established tools or libraries where they help, and keep your own code minimal and readable. Decide from the acquisition description which effects your model must account for, and justify them.

Return the runnable code, the output files listed in task.json, a figure of the effect-size and z maps, an environment record with Python and package versions, and a README.md describing your validation evidence and the limitations of the result. No neuroscientific interpretation is requested. Expect to spend about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

