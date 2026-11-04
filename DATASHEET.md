# MRI Agent Bench datasheet

Version 0.1.0 · research preview · 3 November 2026

## Purpose and authorship

MRI Agent Bench evaluates executable MRI research work: an agent receives a task and input files, then produces artifacts
checked by numerical tests, simulation, code reruns and structured claim checks. It also supports paired evaluations
of agent add-ons. Maintainer: [Ke Wang](https://github.com/KeWang0622).

Task construction used AI author agents, with maintainer integration and automated reference/control validation.
Independent MRI expert review is **pending for all 24 Core families**. MRI Agent Bench and MRFoundry share an author;
current results are maintainer-run. Funding and institutional sponsorship are not specified in this release.

## Contents

| Component | Coverage |
|---|---|
| Core | 24 task types, 88 instances, 10 MRI domains |
| Checks | 311 named automated checks across the 24 task types |
| Validation | Reference solutions, positive controls and 196 recorded negative controls |
| Hard | 15 nonpublic task types; only approved aggregate results are distributed |

The [task guide](docs/TASKS.md) lists inputs, deliverables and grading for every public type.
Instances are generated from simulations, digital phantoms and synthetic study data with fixed seeds.
The public Core split contains no human-participant records. Inputs include k-space, images, spectra, acquisition
metadata, study tables and short research corpora. Generators and graders are included under `families/`.

Each package holds a prompt, public inputs, evaluator-only answers/graders, and a SHA-256 manifest.
All Core package contents are public for reproducibility; evaluator-only files must be hidden from the agent during
an attempt. Related instances share a generator/grader and vary parameters, seeds, data or wording.
See [data formats and downloads](docs/DATA.md) and [Croissant metadata](croissant.json).

## Validation and known limits

References and alternative correct solutions are recorded in each family's `VALIDATION.md`; incorrect controls target
specific checks. An empty submission passes no recorded checks across all 24 task types. Recorded targeted negative controls cover 181 of 230
scientific checks; this is not a measured grader error rate. Expert validity, false failures and resistance to
adversarial submissions still need further evaluation.

Synthetic data omit many scanner and patient artifacts. Task selection, conventions and tolerances reflect their
authors. All tasks are in English. Public answers can contaminate future training or evaluation. A pass demonstrates
compliance with these checks; it is not evidence of clinical validity, publication quality or broad MRI expertise.

The current [offline study](docs/OFFLINE-RESULTS.md) uses 240 paired Core trials on one instance per type and
134 paired Hard trials on unequal model cohorts. It does not measure repeated-run reliability on all 88 Core
instances. That note records setup failures, model exclusions, the memory-cap change and a permissive Hard subcheck.
No outcomes were changed for this release.

## Distribution and use

Code and Core task specifications are in the public GitHub repository. Frozen packages are in the
[Core data release](https://github.com/KeWang0622/MRIAgentBench/releases/tag/core-v0.1.0), with SHA-256 hashes in the catalog.
The original private development history and Hard material are not part of the public snapshot.
A DOI and long-term institutional archive have not been assigned.

Code: [Apache-2.0](LICENSE). Task data, descriptions and documentation: [CC BY 4.0](LICENSE-DATA.md).
The current Core release uses synthetic data; future third-party data must declare their own source licenses.
Please preserve [CANARY.txt](CANARY.txt) and exclude benchmark content from training corpora to protect evaluation
integrity. Intended use is research evaluation, not clinical decision-making.

## Maintenance

Report task errors through [GitHub issues](https://github.com/KeWang0622/MRIAgentBench/issues/new/choose).
Report exploitable grader or software vulnerabilities through [private vulnerability reporting](SECURITY.md).
Changes follow [CHANGELOG.md](CHANGELOG.md): presentation fixes preserve scores; scoring changes declare whether
stored artifacts need regrading or agents need rerunning. Frozen release assets and hashes identify older versions.
Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md); hidden material must never appear in public issues or PRs.
