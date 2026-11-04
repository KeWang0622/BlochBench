<p align="center">
  <img src="assets/banner.svg" width="100%" alt="MRI Agent Bench: executable MRI research tasks for AI agents">
</p>

<p align="center">
  <a href="https://github.com/KeWang0622/MRIAgentBench/actions/workflows/tests.yml"><img alt="tests" src="https://github.com/KeWang0622/MRIAgentBench/actions/workflows/tests.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Code: Apache-2.0" src="https://img.shields.io/badge/code-Apache--2.0-0e7490"></a>
  <a href="LICENSE-DATA.md"><img alt="Data: CC BY 4.0" src="https://img.shields.io/badge/data-CC%20BY%204.0-0e7490"></a>
</p>

**MRI Agent Bench tests whether an AI agent can turn an MRI research request and input data into working, verifiable results.**
Tasks ask agents to design pulse sequences, reconstruct images, estimate tissue properties, analyze studies, or write
conclusions supported by data. Graders check the submitted files by simulation, rerunning code, and recomputing results.

[Task guide](docs/TASKS.md) · [Run a task](docs/GETTING-STARTED.md) · [Submit results](docs/SUBMITTING.md) ·
[Results](docs/RESULTS.md) · [Website](https://kewang0622.github.io/MRIAgentBench/)

## What are the tasks?

| Set | What it measures | Coverage | Availability |
|---|---|---|---|
| **Core** | Focused, executable MRI research workflows | 24 task types, 88 data variants, 10 domains | Task specifications, generators, graders, reference solutions and data packages |
| **Hard** | Longer workflows and system-level decisions | 15 task types: 11 multi-stage and 4 system-design | Aggregate evaluation results; task material remains private |

A **task type** is a family of problems with a shared generator and grader. An **instance** is one frozen data variant.
A **trial** is one agent attempt. Core means the public base suite; it does not mean every task is easy.
The current study evaluated one Core instance per type, not all 88 variants.

| Example task | Given | Deliver | Checked by |
|---|---|---|---|
| [PERF-01 · Cerebral blood flow mapping](families/perf-01-pcasl/) | Label/control MRI, calibration data and acquisition settings | Blood-flow map and reproducible processing code | Numerical ground truth and unseen input data |
| [DIFF-02 · Diffusion tensor imaging](families/diff-02-epi-tensor-mapping/) | Raw EPI diffusion readouts and acquisition metadata | Corrected images, tensor maps and analysis code | Reconstruction and tensor estimates |
| [WRITE-02 · Report trial results](families/write-02-trial-reporting/) | Precomputed trial results and reporting rules | Structured results, uncertainty and supported conclusions | Source-value, unit and claim consistency |

See the [full task guide](docs/TASKS.md) for all 24 types, expected files and grading criteria.

<details>
<summary>All ten domains</summary>

<!-- DOMAINS:START -->
| Domain | Task types | Data variants | Examples |
|---|---:|---:|---|
| Sequence design and Bloch simulation | 7 | 22 | Inversion-recovery T1 mapping with radial readouts; Gradient-echo EPI with delay-robust reconstruction |
| Spectroscopy | 1 | 4 | Single-voxel metabolite quantification |
| Functional MRI | 1 | 4 | Event-related fMRI effect estimation |
| Relaxometry and QSM | 2 | 6 | T2 and transmit-field mapping from imperfect echoes; Quantitative susceptibility mapping |
| Perfusion and CEST | 2 | 8 | Cerebral blood flow from pCASL; APT-weighted CEST mapping |
| Diffusion | 2 | 8 | Diffusion processing and a two-group comparison; Diffusion tensor mapping from raw EPI |
| Reconstruction | 2 | 8 | Fat fraction and R2* from multi-coil k-space; Learned versus classical quantitative reconstruction |
| Hardware, field and safety | 2 | 8 | CPMG design under RF and gradient limits; Spiral imaging with off-resonance correction |
| Study design and statistics | 2 | 8 | Scan-rescan T2 study from k-space to statistics; Study design from pilot cartilage T2 measurements |
| Writing and review | 3 | 12 | Evidence audit and research proposal; Trial reporting with traceable quantitative claims |
<!-- DOMAINS:END -->

</details>

## Run a task

Use Python 3.12 for the supported grader environment. An agent CLI and its credentials are needed for agent runs.

```bash
git clone https://github.com/KeWang0622/MRIAgentBench.git
cd MRIAgentBench
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
mrab list
mrab fetch PERF-01-04
mrab verify PERF-01-04
```

Next: [install the grader and run an agent](docs/GETTING-STARTED.md). Data and run directories default to
`~/mragentbench/`, outside the clone. The evaluated agent must see only its workspace, not graders or reference answers.
Task codes use **domain–task–variant**: `PERF-01-04` is pCASL task 01, data variant 04.
[Task numbering](docs/TASK-IDS.md) explains the codes and maps the legacy IDs retained in frozen files.

## Submit results

Community submissions use a results issue with declared task coverage, run records, grades and model/agent settings.
Small exploratory submissions are welcome; full-Core submissions cover all 88 instances with three attempts each.
Every started attempt counts. Public submissions are labeled **self-reported** and are separate from the frozen study.

Follow the [submission guide](docs/SUBMITTING.md) to export, validate and submit a result bundle.
For paired skill-library comparisons, see [Evaluate your skills](docs/EVALUATE-YOUR-SKILLS.md).

## Current study results

Frozen offline evaluation, 3 November 2026. The same model and harness were compared with and without
[MRFoundry](https://github.com/KeWang0622/MRFoundry) 0.14.0; web search was disabled in both arms.

<!-- LEADERBOARD:START -->
| Evaluation | Paired trials | Baseline | With MRFoundry | Difference (95% CI) |
|---|---:|---:|---:|---:|
| Core | 240 | 162/240 (67.5%) | 188/240 (78.3%) | +10.8 pp (+0.8 to +21.2 pp) |
| Hard | 134 | 49/134 (36.6%) | 60/134 (44.8%) | +8.2 pp (-3.9 to +19.7 pp) |
<!-- LEADERBOARD:END -->

Core improved overall; diffusion declined. The Hard interval crosses zero, and its models cover different task sets.
[Paired model tables](docs/RESULTS.md) and the [evaluation note](docs/OFFLINE-RESULTS.md) give the denominators,
uncertainty, exclusions and limitations. These are maintainer-run results; the benchmark and MRFoundry share an author.
No independent expert review of the task families has been completed. Passing these synthetic tasks does not establish
clinical readiness or the quality of a publishable study.

## Repository

| Path | Contents |
|---|---|
| [`families/`](families/) | Frozen Core task specifications, code, validation and package hashes |
| [`mragentbench/`](mragentbench/) | The `mrab` command-line runner, grading and paired comparison tools |
| [`harness/`](harness/) | Pinned scientific dependencies and grading container |
| [`leaderboard/`](leaderboard/) | Frozen study snapshot and community submission format |
| [`docs/`](docs/README.md) | Task guide, running, submissions, protocol and dataset details |
| [`site/`](site/) | Static task browser and results website |

Previously published as **BlochBench**. The Python package `mragentbench`, CLI `mrab`, task IDs and data packages
are unchanged. Historical release names, the canary and `blochbench-results/1` submission format remain valid.

## Contribute and cite

[Report a task problem](https://github.com/KeWang0622/MRIAgentBench/issues/new/choose),
[contribute a task](docs/CONTRIBUTING-FAMILY.md), or read [CONTRIBUTING.md](CONTRIBUTING.md).
Code is Apache-2.0; task data and documentation are CC BY 4.0. See the [datasheet](DATASHEET.md) and [data license](LICENSE-DATA.md).

```bibtex
@software{wang2026mriagentbench,
  author = {Wang, Ke},
  title = {MRI Agent Bench: Executable MRI Research Tasks for AI Agents},
  year = {2026},
  url = {https://github.com/KeWang0622/MRIAgentBench},
  version = {0.1.0}
}
```

Machine-readable citation: [CITATION.cff](CITATION.cff). This is a research preview release.
