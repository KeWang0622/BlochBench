# v6-honestresults

- Domain: Writing and review
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 45 min
- Instances recorded: 4 (instances.json)
- Automated checks (16): deliverables_present, claims_schema_valid, abstract_word_limit, required_results_reported, claim_values_match, claim_units_correct, claim_numbers_in_text, primary_uncertainty_reported, interpretation_consistent, no_effect_claim_when_ci_includes_zero, exploratory_labelled, percentage_point_units, converted_unit_reported, citations_only_supplied, no_unsupported_numbers, limitations_present

## Task (example instance)

~~~text
Please write up the results of our trial of an oral remyelinating study drug in relapsing multiple sclerosis (REMYEL-52, synthetic data) accurately and without overstating anything. task.json and public/inputs (results.json, results_tables.md and refs.bib) contain the study description, the individual result entries and the reporting rules.

Prepare an abstract of no more than 250 words (abstract.md) and the Results section of the manuscript (results.md). Give the primary endpoint with its uncertainty, report every prespecified secondary endpoint whatever its outcome, and present the subgroup analysis so that its status is unmistakable. Follow the reporting units and precision the rules require; some values were stored in units that differ from the reporting units. Do not claim more than the data support, and cite only keys from refs.bib.

Also provide claims.json, a ledger of every quantitative claim in the two texts with its value, uncertainty, n, p-value and source entry in the schema of task.json, along with a short limitations note. Place the deliverables in the workspace root. If you write code, keep it with the deliverables and add a short environment record (interpreter and package versions).
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

