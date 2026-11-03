# Contributing a task family

A family is accepted when it meets all of the following.

1. Task: a realistic MRI research request with a public specification (task.json) that states inputs, constraints,
   deliverables and output schemas. The agent chooses its own tools.
2. Generator: produces new instances (parameters, data and wording) from a seed; hidden data for reruns are generated
   alongside.
3. Grader: scores deliverables without reading the agent's report; reruns submitted code on hidden inputs where code is a
   deliverable; uses physics-based checks (for sequences, replay with the pinned simulator); writes grade.json with one
   entry per check.
4. Validation: the reference solution passes; at least six negative controls, each a realistic mistake, fail the check
   they target; at least two alternative correct solutions pass; an empty submission fails.
5. Review: at least one MRI researcher outside the author's group accepts it with the review form
   (docs/REVIEW-FORM.md); findings and fixes are recorded in REVIEW.md.
6. Calibration: dev instances are run with the strongest available models; families that every current model passes
   are kept only as easy anchors.

Open an issue with a short proposal first. Families intended for the hidden set are coordinated privately with the
maintainers and are not posted publicly.
