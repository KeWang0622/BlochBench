# Evaluate your skills with MRI Agent Bench

MRI Agent Bench can measure what a skill library adds to a coding agent. The same model runs the same instance twice,
started at the same moment: once in a workspace that holds your skills, once in a workspace that does not, each arm
sealed off from the other. Repeated over instances and runs, the paired outcomes show whether the skills help, with an
exact paired test over independent instances or task families.

This page is for authors of skill libraries (here called add-ons) who run that measurement themselves. It covers the
rules, the package format, the commands and what to report.

## Rules

1. **Comparisons are paired.** Both arms use the same model, agent host and version, command line, reasoning effort,
   instance, tools, inputs and time cap. The add-on is installed in one arm only. `mrab pair` builds both arms this way
   and starts them together; `mrab compare` refuses pairs whose settings differ, and pairs not started together unless
   you pass `--allow-unpaired`.
2. **Reported results need per-arm isolation.** The two agents run at the same time on one machine; unless each is
   confined to its own workspace, the base agent can find the add-on arm's skills. Use the Linux sandbox of
   `mrab pair` (the default, see [Isolation](#isolation)) or a container per arm. Pairs run with `--isolation none`
   are recorded with `isolated: false`, and `mrab compare` refuses them unless you pass `--allow-unisolated`; such
   results must not be reported as add-on results.
3. **Every started run counts.** A timeout, a crash or a run you stopped is a failure, not a reason to rerun. Fix the
   instances and the number of runs per instance before you start, and do not discard, repeat or replace a pair after
   seeing its result. Stopping `mrab pair` (Ctrl-C, SIGTERM, a terminal hangup) kills both agents and records both runs
   as interrupted failures; `mrab compare` refuses a runs folder with started runs that have no run record unless you
   pass `--allow-incomplete`, which counts them as failures.
4. **Declare exposure.** addon.json states whether the add-on's authors saw MRI Agent Bench tasks while building it (see
   [Exposure](#exposure)). The statement is required, travels with every run record and is printed by `mrab compare`.
5. **Results on the public split are self-reported.** Public instances, their generators, graders and reference
   solutions are distributed with the benchmark, so nothing prevents an add-on from being fitted to them. Report such
   results as self-reported, however carefully they were run.
6. **Clean comparisons need sealed or hidden instances.** A comparison is clean only on instances that the add-on's
   authors could not have seen before the add-on version was frozen: hidden instances run by the maintainers
   ([ROADMAP.md](ROADMAP.md)), or sealed instances whose content was fixed and withheld until after
   the add-on's content hash was recorded.
7. **Report with `mrab compare` statistics.** Repeated runs of one instance are not independent, so the primary
   result is at the instance level: the number of instances, the mean per-instance difference with its 95%
   cluster-bootstrap interval, and the exact sign-flip permutation P. Declare the independent unit before evaluation;
   use `--cluster family` when evaluating related variants from the same task family. Report per-arm rates and Wilson
   intervals as descriptive summaries with their independence assumption, label the run-level McNemar P as secondary,
   and publish the JSON that `mrab compare --json` writes.

## The add-on package

~~~
my-addon/
  addon.json                 manifest (schemas/addon.schema.json)
  AGENTS.md                  optional pointer, placed at the root of the add-on arm's workspace
  skills/
    <skill>/SKILL.md         one folder per skill, in the Agent Skills format (https://agentskills.io/specification)
    <skill>/scripts/ ...     optional scripts/, references/, assets/
  README.md, LICENSE, tests/ allowed, but not installed and not hashed
~~~

[examples/addons/minimal](../examples/addons/minimal) is a complete package with one skill.

addon.json (all fields except `metadata` and `$schema` are required; unknown fields are errors):

| Field | Content |
|---|---|
| `name` | 1 to 64 characters: letters, digits, `.`, `_`, `-`; starts with a letter or digit |
| `version` | 1 to 40 characters of the same kind; identifies the frozen content that was evaluated |
| `description` | 1 to 1024 characters |
| `homepage` | http or https URL |
| `license` | SPDX identifier or licence name |
| `authors` | list of 1 to 50 names |
| `hosts` | agent hosts the add-on supports: `codex`, `claude`, or both |
| `exposure` | `{"public_instances_seen": true \| false \| "partial", "details": "..."}` |
| `metadata` | optional map of up to 50 string values, for example a commit hash |

Each SKILL.md starts with YAML front matter. `name` must equal the folder name (lowercase letters, digits and single
hyphens, at most 64 characters) and `description` must be non-empty and at most 1024 characters; `license`,
`compatibility`, `metadata` and `allowed-tools` are optional. Other fields and bodies longer than 500 lines give
warnings. Symbolic links are refused in the installed part (addon.json, AGENTS.md, skills/), and the installed content
is limited to 25 MB and 2,000 files.

### Exposure

`public_instances_seen` is `false` only if no author, and no agent an author used while building the add-on, opened any
MRI Agent Bench instance (prompt, public inputs, private files), any family folder in this repository (README.md,
task.example.json, code/), or any trace or result of a run on them. Use `"partial"` when some were seen and `true` when
the add-on was developed on the benchmark; in both cases `details` must name the families or instances seen.

### Validate and hash

~~~bash
mrab addon validate my-addon          # every error and warning; exit status 1 if invalid
mrab addon hash my-addon              # content sha256 of a valid add-on
mrab addon schema                     # the JSON Schema of addon.json
~~~

For the minimal example, `mrab addon validate examples/addons/minimal` prints the add-on's name, version, skills,
hosts, whether it has an AGENTS.md, its exposure statement, the files it ignores (README.md), then
`content sha256 <hex>` and `valid`.

The content hash covers exactly what is installed: addon.json, AGENTS.md and every file under skills/, with each
file's executable bit (caches such as `__pycache__`, `*.pyc` and `.DS_Store` are skipped). Any change to an installed
byte or executable bit changes it. Run configurations are named `<agent>-<model>+<name>@<version>`, with
`,no-agents-md` appended when the add-on's AGENTS.md is not installed, so give every changed content a new version;
`mrab compare` refuses a configuration whose runs used different contents or AGENTS.md settings.

## Isolation

Each agent works in a fresh staging folder with a random name under `MRAB_WORK` (default: the system temporary
folder), outside the runs folder, so its working path names neither the arm nor the add-on. `MRAB_WORK` must be
outside any Git repository and must not be inside the runs or data folder. The agent gets mrab's environment without
the `MRAB_*` variables. After both agents stop, the results are moved into the run folders and graded there, each
grader writing into a fresh folder created at that moment.

With `--isolation sandbox` (the default of `mrab pair`), each agent runs in new Linux user, mount and process-id
namespaces, set up without privileges:

- its own workspace is the only staging folder it can see; the runs folder, the instance data (graders and hidden
  data), every other staging folder, the add-on source folder, `/tmp`, `/var/tmp`, `/dev/shm` and `$TMPDIR` are
  replaced by empty folders;
- the home folder is a private copy-on-write view: the agent can read its configuration and credentials, and what it
  writes there (sessions, caches, notes) is invisible to the other arm and discarded after the run;
- when it stops or is stopped, every process it started is killed with it.

`mrab pair` checks that the sandbox works before it starts and refuses otherwise. The sandbox needs Linux with
unprivileged user namespaces (on Ubuntu 24.04 and later: `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`;
container runtimes may need their seccomp and AppArmor profiles relaxed) and overlayfs for the staging folder. An agent
command that names a file inside a hidden folder (for example a script in `/tmp`) is refused, because it could not
start. Other writable folders on the machine are not hidden: keep copies of the add-on and notes about it off the
machine, or use a container per arm. On other systems, or when the sandbox is not available, use one container per
arm, started with `--agent cmd` and a command that mounts only `{workdir}`, and pass `--isolation none`: mrab then
records `isolated: false`, which `mrab compare` refuses without `--allow-unisolated`.

After each pair, `mrab pair` verifies the instance against its frozen manifest again, scans the base workspace for
skill folders, instruction files (AGENTS.md, CLAUDE.md and their variants) and files identical to the add-on's, and
searches both arms' output for the other arm's paths, the add-on source folder and the add-on's name (choose a
distinctive one). Anything found is recorded under `contamination` and makes `baseline_clean` false.

## Prepare a clean host

An agent host loads skills and instructions from more places than the workspace. Anything it loads outside the
workspaces reaches both arms, so the baseline would no longer be "the model without skills". Before it creates any
folder, `mrab pair` looks for:

- skill folders: `~/.agents/skills`, `~/.codex/skills` (except `.system`), `~/.claude/skills`, `~/.claude/commands`,
  `~/.claude/agents`, the same under `CODEX_HOME` and `CLAUDE_CONFIG_DIR`, `/etc/codex/skills`,
  `/etc/claude-code/.claude/skills`, and `.agents/skills` or `.claude/skills`, `.claude/commands` and `.claude/agents`
  in `MRAB_WORK` or any folder above it;
- installed Claude Code plugins (`plugins/installed_plugins.json` in the Claude configuration folder);
- non-empty instruction files: `AGENTS.md` and `AGENTS.override.md` in the Codex home, `CLAUDE.md` and `rules/` in the
  Claude configuration folder, `/etc/claude-code/CLAUDE.md`, and `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`,
  `CLAUDE.local.md`, `.claude/CLAUDE.md`, `.claude/AGENTS.md` or `.claude/rules/` in `MRAB_WORK` or above it.

If it finds any of these it refuses, lists them and runs only with `--allow-host-context`; such pairs are recorded with
`baseline_clean: false`. A `MRAB_WORK` inside a Git repository is always refused (Codex reads AGENTS.md files and
`.agents/skills` from the repository root down to the working directory, and Claude Code keeps one auto memory per
repository). Parent instruction files matter even though both arms see them: by default Claude Code
skips AGENTS.md files when the working directory or a folder above it has a CLAUDE.md, and the add-on's pointer is
installed as CLAUDE.md, so the two arms would read different instructions.

The simplest clean host is a Linux machine or container whose home holds no agent configuration except credentials:

~~~bash
export MRAB_DATA=/data/mrab                         # fetched instances
export MRAB_RUNS=/scratch/mrab-runs/my-addon-0.1.0  # one runs folder per add-on version
export MRAB_WORK=/scratch/mrab-work                 # staging folders (default: the temporary folder)
~~~

mrab does not inspect host configuration such as MCP servers, hooks or network access; both arms get the same (one
container image for the whole evaluation keeps it that way). The built-in Codex adapter passes `--ignore-user-config`.
Inside the sandbox the home folder is a copy-on-write view, so token refreshes made during a run are discarded; prefer
API-key authentication for long evaluations.

## Run pairs

~~~bash
mrab list                                         # families and instances
mrab fetch PERF-01-04                    # MRAB_DATA_URL or --from-dir, see docs/DATA.md
mrab verify PERF-01-04
for k in 1 2 3; do
  mrab pair PERF-01-04 --agent codex --model <model> --addon my-addon --run "$k"
done
~~~

`--agent` is `codex`, `claude` or `cmd`; the add-on must list the host in `hosts` (not checked for `cmd`). Any other
agent runs with `--agent cmd --cmd '["my-agent", "--cwd", "{workdir}"]'` (placeholders `{workdir}`, `{model}`,
`{prompt}`, the path of TASK.txt, and `{effort}`; the task is also given on standard input). Other options:
`--effort LEVEL` (the built-in Codex adapter passes `-c model_reasoning_effort=LEVEL`; a `--cmd` template must contain
`{effort}`), `--cap SECONDS` (default: the family's time cap), `--python` (interpreter for the grader), `--no-grade`,
`--no-agents-md`, `--isolation sandbox|none`.

Each pair creates two run folders:

| Arm | Folder | Workspace |
|---|---|---|
| base | `$MRAB_RUNS/<agent>-<model>/<instance>/run<k>/` | public inputs and TASK.txt |
| add-on | `$MRAB_RUNS/<agent>-<model>+<name>@<version>[,no-agents-md]/<instance>/run<k>/` | the same, plus the skills in `.agents/skills/` (Codex and cmd agents) or `.claude/skills/` (Claude Code), and AGENTS.md installed as `AGENTS.md` (Codex, cmd) or `CLAUDE.md` (Claude Code) |

The run folders are created with `started.json` when the agents start, so a pair that never finishes is still visible.
Afterwards both hold work/ (the workspace), trace.jsonl (agent output), agent-stderr.txt, grade/ (grader output),
run.json and pair.json. run.json records the settings that `mrab compare` checks (`argv_template`, `effort`,
`agent_version`, `mrab_version`, `manifest_sha256`), `isolation`, `interrupted` and, for the add-on arm,
`addon_pointer` and `addon_installed_sha256`. pair.json records the pair id, both arms' start and finish times and
their start skew, the add-on manifest with its content hash, where it was installed, the check after the run
(`addon_check`: installed files unchanged, AGENTS.md pointer unchanged, source folder unchanged), `isolation`,
`contamination`, `instance_check` and the host context (`host_skills`, `host_instructions`, `baseline_clean`).
`mrab pair` prints one summary line per arm and one for the pair, and warns if the agent changed the installed add-on
or the baseline is not clean.

Both agents run at the same time on the same machine, so it needs room for two agents; the graders run one after the
other once both have stopped. `mrab pair` never overwrites a run folder: pick a new `--run` or a new runs folder.

## Compare

~~~bash
mrab compare "$MRAB_RUNS" --base codex-<model> --addon codex-<model>+my-addon@0.1.0 \
  --json compare.json --csv pairs.csv
~~~

Runs are paired by (instance, run), from folders named exactly `run<k>`; a folder such as `run1.bak` that holds a
run.json, or a run.json whose instance, run or configuration disagrees with its folder, is refused. Before computing
anything, `mrab compare` refuses:

- pairs whose agent, model, time cap, command line, effort, agent version, mrab version or instance manifest differ,
  an add-on configuration whose runs used different contents, AGENTS.md settings or installed contents, and base runs
  that record an add-on;
- pairs not started together by `mrab pair`, or whose settings were not recorded (allow with `--allow-unpaired`);
- pairs that were not isolated, whose baseline was not clean, or whose instance files changed (allow with
  `--allow-unisolated`; they are then listed);
- started runs without run.json (allow with `--allow-incomplete`, which counts them as failures).

Interrupted runs count as failures. Pairs with an ungraded run (`--no-grade`) are left out and listed. The report gives,
in this order:

- each arm's verified runs with the 95% Wilson interval (assumes independent runs; descriptive only when runs share
  instances or families, not a cluster-adjusted uncertainty estimate);
- the instance level (primary): instances and families, instances where the add-on arm did better, worse or the same,
  the mean per-instance difference in verified rate with its 95% cluster-bootstrap interval (10,000 resamples of
  instances, seed 0), the exact sign-flip permutation P and the exact sign test P. `--cluster family` uses families
  for both the bootstrap and tests, keeping all variants together; its report also gives family direction counts;
- the run level (secondary, it treats repeated runs as independent): pairs, pairs only one arm passed, exact McNemar P,
  then the counts per domain;
- tokens (input plus output): add-on over base overall, and the median ratio over pairs;
- how many pairs were started together by `mrab pair`;
- the add-on's name, version, content hash and exposure;
- warnings for what was allowed or left out.

`compare.json` holds all of this plus one row per pair. `pairs.csv` (family, instance, run, domain, model,
base_passed, addon_passed, base_tokens, addon_tokens) is the input format of `mrab score --paired`, which reports the
instance level when the instance column is present. Use `mrab score --paired pairs.csv --cluster family` to reproduce
family-level inference; CSV files do not store the cluster choice. Family mode requires both instance and family IDs.

The point estimate always weights instances equally after averaging repeats within each instance. In family mode,
the sign-flip statistic uses each family's **sum** of instance differences, preserving that weighting; larger
families contribute more to the estimate. The bootstrap samples whole families and recomputes the instance-weighted
mean. Declare this weighting and the cluster choice before seeing results. Exact sign-flip inference assumes
independent clusters and sign symmetry under the null. The sign test instead tests positive versus negative cluster
directions, omitting ties; it is not a separate test of mean effect. With few independent families, inference is weak
even if there are many variants or repeats.

Analyze one model at a time with these commands. Mixed-model inputs are refused rather than treating models as repeats;
an across-model study needs its own analysis accounting for model dependence. The frozen offline study uses its
separately documented two-way bootstrap and is not recomputed by these commands.

## Report

| Item | Where it comes from |
|---|---|
| Add-on name, version, content sha256 | `mrab addon hash`; the add-on line of `mrab compare` |
| Exposure statement | addon.json `exposure` |
| Instances and split | public (self-reported), sealed or hidden; list the instances |
| Model, agent host and version, effort, settings | `agent_version`, `effort`, `argv_template` in run.json |
| Isolation | `isolation` and `baseline_clean` in pair.json (sandbox, or one container per arm) |
| Runs per instance and time cap | `--run` values; `cap_s` in run.json |
| Instances, declared cluster unit and weighting, mean difference with cluster-bootstrap CI, sign-flip P | `mrab compare` (primary) |
| Verified per arm with independence-based Wilson CI; run-level McNemar P, labelled secondary | `mrab compare` |
| Token ratio | `mrab compare` |
| Interrupted, incomplete, excluded and allowed runs | `mrab compare` warnings |

Publish compare.json together with every run.json, pair.json, grade/grade.json and trace.jsonl. To put the result on
the public board, follow [SUBMITTING.md](SUBMITTING.md) for each of the two configurations.

## Hosted grading (optional)

The hosted service regrades workspaces in the maintainers' grader image ([API.md](API.md)). Submit each arm as its
own submission:

~~~bash
mrab submit "$MRAB_RUNS" --config codex-<model> --model <model> --agent "Codex CLI <version>" \
  --wait --results base-results.json
mrab submit "$MRAB_RUNS" --config codex-<model>+my-addon@0.1.0 --model <model> --agent "Codex CLI <version>" \
  --addon-manifest my-addon/addon.json --wait --results addon-results.json
~~~

`--addon-manifest` validates the package and sends the manifest with its content hash. `mrab submit` refuses add-on
runs (package or plain skills folder) without it, and with it refuses runs without a run.json, runs recorded without an
add-on package, and runs whose run.json records a different content hash.
Hosted grading checks the grades, not how the agents were run, so the results stay self-reported; `mrab compare`
reads local run records, not hosted results files.
