# v6-pilotdesign

- Domain: Study design and statistics
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 45 min
- Instances recorded: 4 (instances.json)
- Automated checks (14): deliverables_present, schema_valid, qc_exclusions_applied, unit_of_analysis_participant, within_subject_sd_correct, repeatability_coefficient_correct, icc_correct, pilot_group_estimates_correct, acute_design_correct, acute_sample_size_correct, group_design_correct, group_sample_size_correct, plan_md_consistent, assumptions_and_limitations_present

## Task (example instance)

~~~text
We plan two studies with knee cartilage T2 as the outcome and have collected pilot data on our own scanner (the pilot data are synthetic; task.json and the CSV files in public/inputs describe them).

Start with measurement repeatability from the test-retest pilot: report the within-subject SD and its confidence interval, the repeatability coefficient, and the ICC in the form task.json defines, with its confidence interval. Next, summarise the pilot comparing patients with early osteoarthritis and controls. Apply the QC rule and the endpoint definition exactly as task.json gives them.

Then design both studies described in task.json: an acute loading challenge (a treadmill run) in healthy volunteers and a comparison of patients with early knee osteoarthritis against controls. For each study pick the design and the statistical unit that answer the question most efficiently and validly, use the variability estimate that matches that design, and work out how many participants to enrol for the stated effect, power and alpha once the stated non-evaluable fraction is allowed for.

Deliver design.json, following the schema in task.json, and plan.md, a short study plan that sets out the assumptions and finishes with a brief limitations note. Save both files in the workspace root. If you write code, keep it beside the deliverables together with a short record of the environment (interpreter and package versions).
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

