# Changelog

All notable changes to MRI Agent Bench. Task changes follow this versioning rule: a change that cannot
alter any score is a patch, a change that needs stored artifacts to be regraded is a minor version, and a change that
needs agents to be rerun is a major version.

## Unreleased

- Use the approved MRFoundry MRI mascot in the site navigation, favicons, social preview and README banner.
  Keep benchmark content, task packages and frozen results unchanged.

- Redesign the project website around concrete public tasks, artifact verification and a dated paired study.
  Add responsive editorial layouts, a personal-homepage link and direct access to the full domain breakdown.
  Preserve all frozen benchmark data, result calculations and submission workflows.

- Rename the public project to **MRI Agent Bench** and the canonical repository to `KeWang0622/MRIAgentBench`.
  Update documentation, citations, website branding and download links. Preserve task IDs, packages, results,
  `mragentbench` / `mrab`, submission format identifiers and historical provenance.

- Give every Core task a stable domain code (for example `PERF-01`) and an explicit variant ID (`PERF-01-04`).
  Rename family folders to descriptive paths; show the codes in the task guide, website and CLI.
- Accept public variant IDs in fetch, verify, prepare, run, grade and pair. Keep legacy IDs working and preserve
  downloaded package names, frozen task content, run records and scientific results. `mrab list --legacy` shows
  the original identifiers; `docs/TASK-IDS.md` lists the complete mapping.

## 0.1.0 — 2026-11-03 (research preview)

- Publish a clean Core snapshot and default download source. Repair 18 archives by removing unmanifested environment
  artifacts; preserve every frozen file/manifest and 70 byte-identical archives (docs/DATA-PACKAGING.md).
- Add a task-first guide, concrete running/submission workflows and validated community result bundles.
- Replace promotional ranking panels with alphabetical paired results; retain every measured outcome.
- Explain Core/Hard, task types/data variants/trials, and the limits of the offline study.
- Keep internal planning history and Hard task material outside the public release.

## Earlier private development

- Replace the legacy preview with the completed offline evaluation: 240 paired Core trials and aggregate results
  for 134 paired Hard trials, using MRFoundry 0.14.0. Core improves from 162 to 188 verified trials; Hard from 49 to
  60. Preserve paired uncertainty, the diffusion decline, unequal Hard coverage, token accounting and runner caveats.
- Add a deterministic offline leaderboard importer, a frozen snapshot restricted to Core rows and Hard aggregates,
  and checks that exclude hidden Hard material. Rebuilding the board and site needs no model calls or pod filesystem.
  Frozen families, graders, instance packages and original trial scores are unchanged.
- Distinguish this single-host maintainer preview from the planned repeated-run, independently reviewed board.
  The public project name is BlochBench; legacy package and CLI names remain for compatibility.

- Add-on track for evaluating skill libraries (docs/EVALUATE-YOUR-SKILLS.md). An add-on is a package with an
  addon.json manifest (schemas/addon.schema.json, including a required exposure statement) and Agent Skills folders;
  examples/addons/minimal is a complete one. New commands: mrab addon validate, hash and schema; mrab pair (both arms of
  one instance started together, the add-on installed in one arm only, the installed files hashed before and after the
  run); mrab compare (paired statistics and fairness checks, below).
  mrab run --addon also accepts a package; mrab submit --addon-manifest sends the validated manifest with its content
  hash, and the API stores it with the submission (docs/API.md).
- mrab pair refuses to run when anything outside the workspaces could reach both arms: user, system and project skill
  folders, installed Claude Code plugins, instruction files (AGENTS.md, CLAUDE.md and their variants) in the agent
  homes or above the staging folder. --allow-host-context runs anyway and records baseline_clean false. A staging
  folder (MRAB_WORK) inside a Git repository is always refused.
- Fair comparisons (independent review): each run works in a neutral staging folder with a random name under
  MRAB_WORK, outside the runs folder, and on Linux mrab pair runs each arm in a sandbox (user, mount and process-id
  namespaces) that hides the other arm, the runs and data folders, the add-on source and the temporary folders, and
  gives the home folder a private copy-on-write view; --isolation none is recorded as isolated: false. The instance is
  verified before and after each pair; the base workspace and both traces are scanned for the add-on; graders write
  into a fresh folder created after the agent stops; MRAB_* variables are removed from the agent's environment.
  baseline_clean is true only for isolated pairs with nothing found.
- mrab compare: the primary test is at the instance level (exact sign-flip permutation test and exact sign test on
  per-instance differences, 95% cluster-bootstrap interval by instance or family); run-level McNemar is kept as a
  labelled secondary statistic. It refuses pairs whose command line, effort, agent version, mrab version or instance
  manifest differ, mixed add-on contents or AGENTS.md settings, pairs not started together (--allow-unpaired),
  unisolated or unclean pairs (--allow-unisolated) and started runs without run.json (--allow-incomplete counts them
  as failures); run folders are matched exactly (run<k>). pairs.csv gains instance and run columns.
- SIGTERM, SIGHUP and SIGINT stop both agents of mrab pair (and the agent of mrab run) with everything they started,
  and record the runs as interrupted failures; agents also die with mrab (parent-death signal, Linux). Run folders get
  started.json when the agents start.
- --no-agents-md runs get their own configuration name (,no-agents-md) and record addon_pointer and
  addon_installed_sha256; --effort is recorded and passed to Codex; the agent's --version and the instance manifest
  hash are recorded.
- The add-on content hash and the after-run check include each file's executable bit; the host-context check covers
  ~/.claude/commands and ~/.claude/agents. mrab submit refuses plain-folder add-on runs and runs without run.json when
  an add-on is declared. The API answers 400 for non-string hosts or instance names.
- Fixes found in review of the add-on code: installed skill files keep their mode, so executable scripts stay
  executable; mrab run --addon checks the add-on's declared hosts and that the folder exists before creating anything;
  mrab submit refuses add-on runs without --addon-manifest and baseline runs with it; the API answers 400, not an
  internal error, for runs that are not JSON objects, and requires exposure details unless public_instances_seen is
  false; mrab score without a file prints a usage error.
- The mrab tool is split into documented, typed modules (catalog, data, runner, grading, scoring, cli; standard
  library only). Commands, flags, environment variables, the runs/ layout and every output are unchanged. Two fixes:
  mrab run --agent cmd without --cmd no longer leaves an empty run folder that blocks the retry, and a timed-out agent
  is stopped together with every process it started.
- Ruff lint and format settings in pyproject.toml, pre-commit hooks (.pre-commit-config.yaml), and a lint step in CI.
- Repository standards: a Makefile (setup, setup-grader, test, lint, families, build-site, packages), AGENTS.md (setup,
  supported Python versions, checks, pull-request rules, and the rule that Hard-tier and hidden material never enters
  this repository), CODEOWNERS, Dependabot for GitHub Actions and the test and lint tools pinned in
  requirements-dev.txt (not pyproject.toml, whose changes rebuild the grader image), a separate lint job, and unit
  tests in CI on Python 3.10 to 3.13.
- The data and runs folders default to ~/mragentbench/data and ~/mragentbench/runs instead of ./data and ./runs inside
  the clone, and mrab run, prepare and pair refuse a data folder, runs folder or workspace inside any Git repository,
  so an agent under evaluation never reads the repository's AGENTS.md. mrab compare reads MRAB_RUNS when no folder is
  given.
- Per-family metadata families/<id>/family.json, generated by tools/make_family_metadata.py from each family's
  README.md, instances.json and task.example.json, with a JSON Schema (schemas/family.schema.json) and a test that
  checks both the schema and the agreement with the sources.
- DATASHEET.md: the dataset documented with the Datasheets for Datasets questions, from facts in the repository;
  open questions are marked TODO for the maintainer.
- Hosted grading service on AWS: mrab bundle, submit and status; HTTP API with token authentication and quotas;
  AWS Batch grading jobs on Fargate without AWS credentials in the container (docs/INFRASTRUCTURE.md, docs/API.md).
- Grader image on Debian trixie (OpenSSL 3.5, needed by the pinned OpenSSL_jll), with mrab installed and Julia packages
  in a shared read-only depot so graders can run as an unprivileged user. Built and pushed to Amazon ECR by CI.
- Preview leaderboard from maintainer-run evaluations on the 24 public -r4 instances (leaderboard/leaderboard.json).
- Survey of how other agent benchmarks are built and run, from primary sources (docs/LANDSCAPE.md).
- Unit tests for bundling and grading; CI runs them on every pull request.
- 24 Core families, 88 public instances, 311 automated checks; mrab list, fetch, verify, prepare, run, grade, collect,
  score; expert review packets; hidden-set plan.
