# MRI Agent Bench expert review protocol

This protocol specifies review to be completed. It does not establish that the released Core families have received
independent expert validation; current status is recorded in [DATASHEET.md](../DATASHEET.md).

## Assignment

- 24 Core families in ten domains ([catalogue](../families/index.json)). Each family is reviewed by at least one MRI researcher from its
  domain; the seven sequence-design families and any family with a "major issue" verdict get a second reviewer.
- Suggested domain assignment for three reviewers (record actual time; do not assume an audit fits a fixed time cap):
  - Acquisition: sequence design (MP-RAGE, SE-DWI, UTE, spiral, TSE, navigator EPI, IR-T1 pipeline), hardware and safety
    (spiral B0, safe CPMG).
  - Reconstruction and quantitative imaging: learned reconstruction, Dixon from raw data, QSM, T2 EPG fitting, pCASL,
    CEST, MRS.
  - Analysis and research practice: diffusion (DTI with EPI correction, DWI group study), fMRI GLM, T2 study, pilot
    design, gap proposal, honest results, method review.
- Disclose each reviewer's involvement in task, grader or evaluated-system development. At least one reviewer per
  family must be independent of those contributions. Agent-assisted checks do not count as independent human review.
- Reviewers see the task specification and required artifacts. They assess submissions before seeing grader verdicts
  or model/add-on identities; record accidental unblinding. After recording a judgment, inspect grader code and logs.
- Independently reproduce reference and alternative-solution grading on a declared subset spanning every domain.
  Record the environment, selected families, outputs and any families not reproduced.

## Grader calibration

1. Freeze the audit sample and selection procedure before inspecting reviewer judgments. Sample both passes and
   failures across families, model/add-on conditions and observed error types. Include alternative correct solutions
   and deliberately flawed controls; report controls separately from sampled agent submissions.
2. For each blinded submission, record scientific validity, reproducibility, evidence adequacy and uncertainty.
   Scientific errors cannot be offset by polished writing. Use the [review form](REVIEW-FORM.md).
3. Compare expert judgments with automated decisions. Obtain a second domain review for disagreements and all
   suspected false accepts/rejects; retain original judgments and record adjudication. Unresolved cases remain explicit.
4. Report the confusion table and denominators: false-accept rate = automated passes among expert-invalid submissions;
   false-reject rate = automated failures among expert-valid submissions. Report uncertain cases separately. Give
   uncertainty intervals with a declared sampling/dependence model; small audits may support only descriptive counts.
   Stratified or targeted samples describe their audit strata unless population weighting is justified. Control
   coverage and reviewer agreement alone are not error-rate estimates.

## What to judge

For each family, answer the form (REVIEW-FORM.md). The four questions that decide the verdict:

1. Correctness: is the science in the task, the specification and the reference solution right (physics, conventions,
   models, statistics)?
2. Specification: could a competent MRI researcher complete the task from the prompt and task.json alone, without
   guessing at an unstated convention?
3. Grading: does each check test what it claims? Are tolerances justified? Is there a way to pass without doing the
   science, or a correct solution that would fail?
4. Realism: is this a step that occurs in real MRI research, at a realistic scale?

## Verdicts and what happens next

| Verdict | Meaning | Action |
|---|---|---|
| Accept | Correct, clear, fairly graded | Record the reviewed commit, scope and supporting evidence |
| Accept with changes | Fixable issues (wording, tolerance, a missing convention) | Correct in a separately versioned release; rerun affected validation and obtain reviewer confirmation |
| Reject | Wrong science, ungradeable, or unrealistic | Exclude or redesign for a future release; retain the historical record |

Publish Core review records under `docs/reviews/`, keyed by public task ID and reviewed commit; do not edit frozen
family files to record reviews. Keep hidden-task review material outside this repository. Public summaries must not
identify hidden tasks. Corrections follow [the versioning policy](../CHANGELOG.md) and apply consistently to every
affected condition. Preserve original grades and distinguish corrected analyses from the frozen study.

## Difficulty notes

After blinded review, reviewers may suggest realistic extensions for future releases. Model success alone is not a
reason to remove a useful capability or redesign a task. Select tasks using declared scientific coverage criteria,
not which model or add-on benefits; do not change the current study's membership or scores retrospectively.
