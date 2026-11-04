# MRI Agent Bench expert review protocol (v1.0 Core families)

## Assignment

- 24 Core families in ten domains (families-v1.json). Each family is reviewed by at least one MRI researcher from its
  domain; the seven sequence-design families and any family with a "major issue" verdict get a second reviewer.
- Suggested split for three reviewers (about eight families each, 4-6 hours in total):
  - Acquisition: sequence design (MP-RAGE, SE-DWI, UTE, spiral, TSE, navigator EPI, IR-T1 pipeline), hardware and safety
    (spiral B0, safe CPMG).
  - Reconstruction and quantitative imaging: learned reconstruction, Dixon from raw data, QSM, T2 EPG fitting, pCASL,
    CEST, MRS.
  - Analysis and research practice: diffusion (DTI with EPI correction, DWI group study), fMRI GLM, T2 study, pilot
    design, gap proposal, honest results, method review.
- Reviewers see the public task and the grader details. They do not need to run code; the packet contains the
  validation results. Reviewers who want to run the reference solution receive the family folder.

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
| Accept | Correct, clear, fairly graded | Family enters v1.0 as reviewed |
| Accept with changes | Fixable issues (wording, tolerance, a missing convention) | Maintainer fixes, regenerates instances, re-runs validation; reviewer confirms |
| Reject | Wrong science, ungradeable, or unrealistic | Family is removed or redesigned |

All reviews, fixes and confirmations are recorded in families/<id>/REVIEW.md in the repository. Disagreements between two
reviewers are resolved by discussion; unresolved items are listed in the paper.

## Difficulty notes

The packet marks families that the strongest current models pass at 90% or more without help (saturated). For those,
reviewers are asked for one realistic way to make the task harder (question 7 of the form).
