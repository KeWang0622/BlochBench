# AGENTS.md

Instructions for coding agents, and for people, who work on this repository: the mrab tool, the task families, the
hosted grading service, the website and the docs.

> [!IMPORTANT]
> This file is for developing MRI Agent Bench, not for solving its tasks. An agent under evaluation must never work inside
> a clone of this repository, where it would read this file and could reach families/. mrab enforces that: run,
> prepare and pair refuse a data folder, runs folder, staging folder or workspace inside any Git repository, and the
> defaults (~/mragentbench/data, ~/mragentbench/runs, the system temporary folder) lie outside the clone. Other
> harnesses must do the same; see [the setup guide](docs/GETTING-STARTED.md#keep-the-evaluation-isolated).

## Hard rule: no Hard-tier or hidden material

Hard-tier and hidden material never enters this repository. That covers the task statements, prompts, generators,
graders, reference solutions, controls, data, seeds, instance packages, traces and results of Hard-tier families in
development, and of hidden instances and hidden families, in any file, commit message, issue, pull request or CI log.
That material is kept outside this repository. Broad scope and release plans may be described in
[docs/ROADMAP.md](docs/ROADMAP.md); task identities may not. If a change would disclose hidden task material, stop and
report it privately to the maintainer instead of committing it.

The maintainer's 3 November handoff permits aggregate Hard-tier results: overall totals, model totals and broad
coverage cohorts only. These appear in `leaderboard/offline-results-2026-11-03.json` and generated displays. They must
never contain Hard task or family identifiers, per-instance outcomes, check-level results or source paths to hidden
material. The importer uses an explicit field allowlist; do not copy the full study summary or pair table here.

## Setup

~~~bash
python3.12 -m venv .venv
make setup PYTHON=.venv/bin/python          # mrab (editable) and requirements-dev.txt: jsonschema, ruff
make setup-grader PYTHON=.venv/bin/python   # only to run graders: the pinned scientific stack and juliacall
~~~

Supported Python versions: mrab and its tests run on Python 3.10 to 3.13 (CI tests all four). The grader environment
needs Python 3.12 or later (its pins numpy 2.5.3 and scipy 1.18.1 require 3.12, dipy 1.12.1 requires 3.11), so
`make setup-grader` fails on 3.10 and 3.11; the supported grading image uses Python 3.12.14 (harness/Dockerfile.grader).
Graders of the sequence-design families also need Julia with KomaMRI: harness/grader-env/julia_env pins the environment.

## Tests and checks

| Command | What it does |
|---|---|
| `make test` | unit tests (`python -m unittest discover -s tests`); CI runs them on Python 3.10, 3.11, 3.12 and 3.13 |
| `make lint` | `ruff check` and `ruff format --check` on mragentbench, tools, tests and infra (settings in pyproject.toml) |
| `make families` | regenerate families/*/family.json; tests/test_families.py fails when one is out of date or breaks schemas/family.schema.json |
| `make build-site` | regenerate site/data and the README tables between the LEADERBOARD and DOMAINS markers |
| `make build-board` | regenerate the offline preview board from its frozen, disclosure-limited snapshot |
| `make check-results` | check the offline board and generated site against their saved sources without writing |

Tests must run without network access, AWS credentials, Julia or an agent CLI; tests/test_service.py builds a toy
instance for that reason. The mrab tool uses the Python standard library only ([CONTRIBUTING.md](CONTRIBUTING.md)).

## Rules for changes

- Task families are frozen. Do not edit or reformat files under families/ by hand (ruff excludes the folder); instance
  packages are checked against SHA-256 manifests. A change that can alter a score follows the versioning rule in
  [CHANGELOG.md](CHANGELOG.md) and needs the family's validation to be rerun.
- Generated files are regenerated, not edited: family.json (`make families`), site/data and the README tables
  (`make build-site`), croissant.json (tools/make_croissant.py). Package hashes in instances.json are written only by
  the maintainers when they rebuild the instance packages from the original sources; do not rebuild packages.
- `families/index.json` assigns permanent public task/variant IDs to frozen legacy identities. Never reuse or
  renumber an assigned ID; append new IDs. Folder moves do not authorize edits to frozen task bytes.
- Keep the canary string ([CANARY.txt](CANARY.txt)) with benchmark content.
- Statements about other work, tools, licences or dates need a primary source; external ones are listed in
  [docs/SOURCES.md](docs/SOURCES.md).
- Never commit tokens, keys, AWS credentials or account-specific secrets.

## Pull requests

- Branch from main, one topic per pull request, and open it against main. Never push to main.
- Fill in the template ([.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)), including whether the
  change can alter any score.
- Before opening: `make test` passes, `make lint` reports nothing in the files you changed, code changes come with
  tests, and user-visible changes have an entry under Unreleased in CHANGELOG.md.
- The maintainer ([.github/CODEOWNERS](.github/CODEOWNERS)) reviews and merges. Agents open pull requests; they do not
  merge them, tag or publish releases, change the repository's visibility, or change AWS resources.
- CI: the tests workflow runs on every pull request. The build-grader-image workflow builds the grader image on pull
  requests that touch harness/ or mragentbench/, without publishing it. Maintainer ECR publication is a separate, explicitly configured manual action.
