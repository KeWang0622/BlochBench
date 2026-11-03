# BlochBench: Executable MRI Research Tasks for AI Agents

Research preview summary · 3 November 2026. This repository does not yet contain a finalized standalone benchmark paper.
The completed comparison and its limitations are available in [the results guide](../docs/RESULTS.md).

## Benchmark

BlochBench asks agents to turn MRI research requests and supplied data into executable deliverables. Its public Core
suite contains 24 task types and 88 instances across ten domains: sequence design, spectroscopy, functional MRI,
relaxometry and susceptibility mapping, perfusion and CEST, diffusion, reconstruction, hardware and safety, study
statistics, and scientific writing. Each type specifies inputs, required outputs, automated checks, a generator,
a reference solution and validation controls. Graders use simulation, numerical ground truth, code reruns and
structured claim checks; no LLM judge is used.

A separate nonpublic Hard suite contains 11 multi-stage and four system-design task types. This release distributes
only approved overall/model/cohort aggregates for Hard. It does not disclose the task identities or scoring material.

## Completed evaluation

The frozen offline study compares each model without skills against the same model with MRFoundry 0.14.0. Core
includes 240 paired trials: 24 task types × ten models × one instance. Completion rises from 162/240 (67.5%) to
188/240 (78.3%), a difference of +10.8 percentage points (two-way family/model bootstrap 95% CI +0.8 to +21.2).
Hard includes 134 paired trials across unequal model cohorts and rises from 49/134 (36.6%) to 60/134 (44.8%);
its +8.2-point difference has a 95% CI of −3.9 to +19.7. Full tables, exact tests and token accounting are generated
from the checked-in snapshot. No agents were rerun for the public release.

## Limits and remaining work

The benchmark and MRFoundry share an author. Task generation used AI author agents; external MRI expert review is
pending. Synthetic tasks and automated checks are imperfect proxies for research competence. Core diffusion declines
in the paired study, Hard cohorts are not directly rankable, and the Hard aggregate interval includes zero.
The study does not establish repeated-run reliability, performance across alternative agent hosts or clinical validity.
[The evaluation note](../docs/OFFLINE-RESULTS.md) records setup failures, model exclusions, the memory-cap change and
a permissive Hard subcheck. Independent review, stronger adversarial controls and repeated-run studies are next steps.

## Reproduction

[Task guide](../docs/TASKS.md) · [Running](../docs/GETTING-STARTED.md) · [Submitting](../docs/SUBMITTING.md) ·
[Dataset details](../DATASHEET.md) · [Frozen result regeneration](../docs/OFFLINE-RESULTS.md#provenance-and-regeneration)
