# WRITE-01 · Evidence audit and research proposal

- Task ID: WRITE-01
- Legacy ID: v6-gapproposal

- Domain: Writing and review
- Tier: Core (v1.0 candidate); review status: pending
- Time cap: 45 min
- Instances recorded: 4 (instances.json)
- Automated checks (17): deliverables_present, schema_valid, citations_within_corpus, replicated_finding_correct, contradiction_correct, underpowered_claims_correct, gap_identified, gap_support_valid, hypothesis_and_endpoint_measurable, design_correct, sample_size_inputs_valid, recruitment_inputs_valid, sample_size_arithmetic, controls_required_present, controls_support_valid, risks_and_limitations_present, markdown_consistent

## Task (example instance)

~~~text
Our cardiac MRI group needs to choose its next study. I would like a well-founded research gap and a study proposal built strictly on the supplied corpus of 35 study records on myocardial inflammation (synthetic; see task.json and public/inputs). Please read the records carefully.

Begin with an audit of the evidence: which findings are replicated, which results conflict and which protocol difference accounts for the conflict, and which claims rest on underpowered studies, along with the later records that depend on them. Then identify the gap that meets the gap rules in task.json and propose a study to close it, with the hypothesis, primary endpoint, design, controls, risks and a sample-size calculation that follows the stated rules and draws its numbers from the corpus.

Deliver proposal.json in the schema of task.json and proposal.md, a readable proposal of at most 1500 words that cites records as [Mxx]. Cite nothing from outside the corpus. Place the deliverables in the workspace root. If you write code for the calculations, keep it with the deliverables and add a short environment record (interpreter and package versions). Include a brief limitations note in both files.
~~~

The full specification is in task.example.json. code/ holds the generator, grader, reference solution and control scripts of the example instance; VALIDATION.md lists how the reference and the controls scored.

