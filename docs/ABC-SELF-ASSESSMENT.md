# Agentic Benchmark Checklist: BlochBench self-assessment (v1.0 Core, pre-release)

> Historical development note (1 November 2026). For current release status and evidence, use
> [the datasheet](../DATASHEET.md), [offline results](OFFLINE-RESULTS.md) and [roadmap](ROADMAP.md).

Checklist: Zhu et al., *Establishing Best Practices for Building Rigorous Agentic Benchmarks* (arXiv:2507.02825;
ABC.md in uiuc-kang-lab/agentic-benchmarks). Status: **met**, **partly met**, **not yet** (with the action planned before
v1.0), or **n/a**. Evidence files are in this repository or in the benchmark folder of the MRFoundry study.

## Outcome validity

BlochBench graders combine end-to-end testing (rerun submitted code on hidden inputs, replay exported sequences in a
Bloch simulator), state matching (required deliverables and schemas) and numeric answer matching against ground truth
within stated tolerances. Writing families compare structured outputs with an answer key; no LLM judge is used.

| Item | Status | Evidence or action |
|---|---|---|
| I.a/I.b string matching | n/a | No free-text matching; written outputs are scored through structured fields (JSON) against keys |
| I.c LLM-as-a-judge | n/a | Not used |
| I.d.1 test cases verified for correctness | partly met | Every family: reference passes; 196 negative controls, 191 of 195 with a declared target fail that target; 2+ positive controls pass. Human verification: expert review in progress (docs/REVIEW-PROTOCOL.md) |
| I.d.2 objective test-quality metric | partly met | Negative-control coverage: 181 of 230 scientific checks are failed by at least one targeted negative control (negative-control-coverage.json). Gaps are concentrated in the six sequence-design families (hardware limits, raster and dead times, Bloch replay, sequence readback): add targeted negatives before v1.0 |
| I.f.2 end-to-end tests exercise relevant parts | met | Hidden reruns on unseen data; sequence replay with an independent simulator; maps compared voxelwise and by region |
| I.f.3 no flaky results | not yet | Regrade each reference and a sample of recorded submissions twice and confirm identical grades; pin simulator versions (KomaMRI 0.14) in the image |
| I.g state matching | met | Required deliverables, file names and schemas are specified in task.json and checked |
| I.h.1 answer formats specified | met | Output schemas are part of every task.json |
| I.h.2 guessing minimized | met | Numeric answers against hidden truth with tight tolerances; reruns on hidden data; writing keys combine several structured fields |
| I.I.1 metrics resist exploitation | partly met | Graders ignore self-reported results and recompute them; hidden reruns block hard-coding. Action: red-team each family with exploit attempts (copying example outputs, hard-coding public answers, editing provided files) |

## Challenge validity

| Item | Status | Evidence or action |
|---|---|---|
| II.1 tool versions specified | partly met | Graders run in a pinned image built by CI and stored in Amazon ECR (harness/Dockerfile.grader); tasks leave tool choice to the agent. Action: publish the image and state its versions in every prompt |
| II.2 required APIs accessible | met | Package registries and the model endpoint are the only external services; study logs show no task blocked by them after reruns |
| II.3 errors handled | met | A run with an infrastructure error before the first task turn is rerun once; started runs are scored as assigned |
| II.4 state cleared between runs | met | Fresh workspace, empty Python environment and separate Julia depot per run |
| II.5 agent isolated from ground truth | met | Hidden data and graders are outside the workspace; the study sandbox denied reads of other runs and grading files; traces audited |
| II.6 ground truth verified | partly met | Truth is generated from known parameters and recovered by the reference within tolerance; expert review pending |
| II.7 every task solvable | met | Reference solution passes every check on every instance |
| II.8 oracle solver | met | Reference solutions (code/ in each family) |
| II.9 no exploitable vulnerabilities | partly met | Empty submission fails all 311 checks in all 24 families (trivial-agent-grades.json); red-team pass pending |

## Benchmark reporting

| Item | Status | Evidence or action |
|---|---|---|
| III.1 open source | not yet | Public release with v1.0 |
| III.2 open evaluation harness | partly met | mrab run/grade, the grader image and a hosted grading service exist (docs/INFRASTRUCTURE.md); public with v1.0 |
| III.3 contamination measures | met (design) | Hidden families and seeds, semi-private and private sets, hash commitments, canary (docs/ROADMAP.md) |
| III.4 updates over time | met (design) | Six-monthly and yearly rotation; Hard tier calibrated against frontier models |
| III.5 capability-construct relation | met | docs/ROADMAP.md states what is measured: verified end-to-end MRI research outcomes |
| III.6 evaluation subject | met | An agent system: model, agent host and declared add-ons; add-on mode compares the same model with and without an add-on |
| III.7 flaw prevention and correction | met | Controls, expert review, audit of a random 5% of graded verified runs each round, correction log |
| III.8 qualitative discussion of flaws | not yet | Paper section on residual flaws (simulated data, topic selection by the authors, AI-authored tasks) |
| III.9 quantitative flaw impact | partly met | Run-to-run variation measured (outcome changed in 26 of 115 repeated combinations without add-ons); grader false-failure rate to be estimated from the expert audit |
| III.10 statistical significance | met | Exact McNemar tests and two-way cluster bootstrap over families and models |
| III.11 interpretation guidance | not yet | Add to README and paper |
| III.12 non-AI baselines | not yet | Planned: MRI researchers on six families under the same caps |
| III.13 trivial agents | met | Empty submission: 0 of 24 families, 0 of 311 checks passed |
