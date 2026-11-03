# Run a Core task

## 1. Install

Use Python 3.12 for the grader. The `mrab` CLI supports Python 3.10–3.13 and has no runtime dependencies.

```bash
git clone https://github.com/KeWang0622/BlochBench.git
cd BlochBench
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r harness/grader-env/requirements.txt
mrab list
```

The scientific stack is substantial. Sequence-design graders also need Julia/KomaMRI; the supported complete
environment targets Linux x86-64 and is defined by [`harness/Dockerfile.grader`](../harness/Dockerfile.grader), with Julia pins in
[`harness/grader-env/julia_env/`](../harness/grader-env/julia_env/). Start with the blood-flow example below if you do
not need sequence simulation. Build the full environment with:

```bash
docker build --platform linux/amd64 -f harness/Dockerfile.grader -t blochbench-grader:0.1.0 .
```

## 2. Fetch and inspect one task

```bash
mrab fetch heldout-v7-pcasl-r4
mrab verify heldout-v7-pcasl-r4
mrab prepare heldout-v7-pcasl-r4 ~/mragentbench/work/first-task
cat ~/mragentbench/work/first-task/TASK.txt
```

Downloads use the [Core data release](https://github.com/KeWang0622/BlochBench/releases/tag/core-v0.1.0).
The manifest and every packaged file are checked by `mrab verify`. See [DATA.md](DATA.md) for overrides and formats.
`prepare` creates a workspace for inspection or a custom runner; `run` creates its own fresh workspace.

## 3. Run an agent

Install and authenticate your agent CLI first, then substitute its model ID:

```bash
mrab run heldout-v7-pcasl-r4 --agent codex --model YOUR_MODEL_ID --run 1
```

Use `--agent claude` for Claude Code. Other agent CLIs use an argv template:

```bash
mrab run heldout-v7-pcasl-r4 --agent cmd --model YOUR_MODEL_ID \
  --cmd '["my-agent", "--prompt-file", "{prompt}", "--cwd", "{workdir}"]'
```

`run` grades after the agent exits or reaches the task's time cap. It saves `run.json`, `trace.jsonl` and
`grade/grade.json` under `~/mragentbench/runs/<config>/<instance>/run1/`.
A pass requires **all** automated checks. To grade a workspace produced separately:

```bash
mrab grade heldout-v7-pcasl-r4 ~/mragentbench/work/first-task
```

### Keep the evaluation isolated

The downloaded Core package includes answers and graders for reproducibility. They must be hidden from the agent.
Keep agent workspaces outside the repository. On Linux, `mrab run` uses its namespace sandbox when available and
records isolation in `run.json`. For reportable results elsewhere, run the agent in a container or VM exposing only
its workspace; keep the grader outside it. A prepared directory alone does not enforce filesystem isolation.
See [the isolation guide](EVALUATE-YOUR-SKILLS.md#isolation).

## 4. Inspect and submit results

```bash
mrab collect > runs.csv
mrab score runs.csv
```

These commands summarize finalized runs. For publication, use the [submission exporter and validator](SUBMITTING.md)
so interrupted attempts are included as failures. Small subsets are accepted as exploratory results; all 88 Core
instances × three attempts form a full-Core submission. Public results are self-reported.

## Compare a skill library

```bash
mrab addon validate path/to/addon
export MRAB_RUNS=~/mragentbench/paired-runs
mrab pair heldout-v7-pcasl-r4 --agent codex --model YOUR_MODEL_ID --addon path/to/addon --run 1
mrab compare --base BASE_CONFIG --addon ADDON_CONFIG --json compare.json
```

Use a fresh paired-runs directory and the actual configuration names it creates. Both arms need independent isolation.
[Full add-on workflow](EVALUATE-YOUR-SKILLS.md) · [`addon.json` example](../examples/addons/minimal/)

## Paths and help

| Setting | Default / purpose |
|---|---|
| `MRAB_DATA` | `~/mragentbench/data` — downloaded packages |
| `MRAB_RUNS` | `~/mragentbench/runs` — attempts and grades |
| `MRAB_WORK` | System temporary directory — agent staging workspaces |
| `MRAB_DATA_URL` | Public Core release; override with a compatible package mirror |

`mrab <command> --help` lists all flags. Hosted grading commands (`bundle`, `submit`, `status`) require a separately
configured maintainer service; the public submission route is a results issue with a validated bundle.
