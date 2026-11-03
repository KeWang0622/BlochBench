# MRS-01 · Single-voxel metabolite quantification

- Task ID: MRS-01
- Legacy ID: v7-mrsquant

- Domain: Spectroscopy
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (8): deliverables_present, report_schema, environment_record, readme_validation_limitations, public_concentrations, entrypoint_runs_on_public_inputs, hidden_case1_concentrations, hidden_case2_concentrations

## Task (example instance)

~~~text
Quantify brain metabolites from the single-voxel MR spectroscopy dataset described in task.json. You are given raw, uncombined and unaveraged multi-coil PRESS transients, an unsuppressed water reference from the same voxel, and the voxel's tissue composition with relaxation and water-content values in params.json. The data conventions, the definition of the concentrations, the accuracy targets and the file interfaces are in task.json.

Write a standalone entrypoint, mrs_quant.py, that reads one input directory and writes the NAA, total creatine and total choline concentrations in mM. Keep all custom code in that single file and read every parameter from params.json, because it will be rerun on other acquisitions with different echo and repetition times, tissue fractions, coil configurations, drift, eddy currents and linewidths. Run it on the public inputs and return the result.

Use established tools or libraries where they help, and keep your own code minimal and readable. Decide which preprocessing steps and quantification corrections the data require, and justify them.

Return the runnable code, the output files listed in task.json, a figure of the processed spectrum with your fit and residual, an environment record with Python and package versions, and a README.md describing your validation evidence and the limitations of the result. No clinical interpretation is requested. Expect to spend about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

