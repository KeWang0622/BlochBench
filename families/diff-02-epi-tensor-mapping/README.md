# DIFF-02 · Diffusion tensor mapping from raw EPI

- Task ID: DIFF-02
- Legacy ID: v7-epidti

- Domain: Diffusion
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 60 min
- Instances recorded: 4 (instances.json)
- Automated checks (20): deliverables_present, report_schema, environment_record, readme_validation_limitations, public_geometry, public_nyquist_ghost, public_fa_md_rois, public_fa_voxelwise, public_v1_direction, entrypoint_runs_on_public_inputs, hidden_case1_geometry, hidden_case1_nyquist_ghost, hidden_case1_fa_md_rois, hidden_case1_fa_voxelwise, hidden_case1_v1_direction, hidden_case2_geometry, hidden_case2_nyquist_ghost, hidden_case2_fa_md_rois, hidden_case2_fa_voxelwise, hidden_case2_v1_direction

## Task (example instance)

~~~text
Produce diffusion tensor maps from the raw echo-planar diffusion dataset described in task.json. You are given unprocessed single-shot EPI readouts for every diffusion volume and slice, including navigator readouts, together with a B0 field map, a per-voxel gradient-nonlinearity field and the nominal diffusion gradient table. The raw-data and diffusion conventions, the endpoint definitions, the accuracy targets and the file interfaces are in task.json.

Write a standalone entrypoint, epi_dti.py, that reads one input directory, reconstructs the images and writes fractional anisotropy, mean diffusivity, the principal diffusion direction and a corrected mean b=0 image, all on the undistorted image grid. Keep all custom code in that single file and read every parameter from the inputs, because it will be rerun on other acquisitions with different timing errors, field maps, phase-encoding polarity, echo spacing, gradient fields and diffusion schemes. Run it on the public inputs and return the result.

Use established tools or libraries where they help, and keep your own code minimal and readable. Decide which reconstruction steps and corrections are needed between the raw readouts and the tensor fit, and justify them.

Return the runnable code, the output files listed in task.json, a figure comparing uncorrected and corrected b=0 images together with FA, MD and colour-coded direction maps, an environment record with Python and package versions, and a README.md describing your validation evidence and the limitations of the result. No claims about in vivo data are requested. Expect to spend about an hour.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

