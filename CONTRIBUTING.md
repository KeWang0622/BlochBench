# Contributing

Thank you for helping improve BlochBench.

- **Report a task problem** (unclear instructions, a grader that rejects a correct answer or accepts a wrong one): open
  an issue with the Task problem template. Include the instance name and, if possible, the workspace that was graded
  wrongly.
- **Propose a new task family**: read docs/CONTRIBUTING-FAMILY.md. Every family needs a generator, a private grader, a
  reference solution, at least six negative controls and two positive controls, a validation run and expert review.
- **Submit results**: see docs/SUBMITTING.md and docs/API.md.
- **Code changes**: open a pull request. Keep the mrab tool standard-library only, add or update tests in tests/, and
  run them with make test (python -m unittest discover -s tests). Changes to graders or task data must say whether
  they can change any score (CHANGELOG.md explains the versioning rule). AGENTS.md lists the setup, the checks and the
  pull-request rules, for people and coding agents alike.

Benchmark content must keep the canary string (CANARY.txt). Do not post hidden-set material anywhere.
