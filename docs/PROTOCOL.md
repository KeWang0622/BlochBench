# Evaluation protocol

An entry describes an **agent system**: model, host/scaffold, settings, tools and optional add-on. A model name alone
is not a reproducible configuration. Record the benchmark commit and exact instance list for every report.

## Completed study

The frozen offline comparison handed off on 3 November 2026 contains 240 paired Core trials and 134 paired Hard trials.
Both arms used the same model, instance, host and task time cap; the skill arm used MRFoundry 0.14.0. Web search was
disabled for every included model. These are historical study settings, not defaults guaranteed by the public CLI.
[OFFLINE-RESULTS.md](OFFLINE-RESULTS.md) is the authoritative record of totals, provenance, limitations and incidents.

Core uses one instance per task type for ten models. Hard uses two unequal cohorts: three models on 15 types × two
instances, and four models on 11 multi-stage types × one instance. Results show paired counts and separate Hard cohorts.
No cross-cohort ranking is reported. The intervals for aggregate paired differences use a two-way cluster bootstrap
over families and models (4,000 resamples, seed 0); exact McNemar tests summarize discordant trial pairs.

The snapshot does not estimate pass^3 or pass^5. It includes recorded setup restarts, a model/tool exclusion and a memory
cap introduced partway through evaluation. It must not be retrospectively described as following a later protocol.

## Public Core submissions

Submit either an explicitly declared exploratory subset or all 88 Core instances with three attempts each.
[SUBMITTING.md](SUBMITTING.md) defines the bundle and local validation. Public reports remain self-reported after
consistency review. They do not overwrite the study snapshot or establish independent expert validation.

- Fix the model, host version, effort/settings, tools, time caps and add-on before running the declared set.
- Use a fresh workspace per attempt. Keep graders, answers, other attempts and undeclared host instructions inaccessible.
- Include every started attempt, including timeouts, crashes and interruptions. Use new run numbers for new attempts.
- Declare task exposure, any task-specific tuning, network policy, hardware and deviations. Public tasks can be memorized.
- Keep subsets, repeat schedules and environments separate when comparing systems. Do not rank different coverage as one set.

### What the runner enforces

`mrab` prepares public-input-only workspaces and refuses data/run/work folders inside Git checkouts. On supported Linux
hosts its namespace sandbox isolates filesystems; run records state whether isolation was available. The grader runs
after the agent stops and records each named check. The submission tools reconcile recorded attempts, grades and coverage.

### What the operator must enforce

The generic CLI does **not** supply a package-only network proxy, universally disable each host's web tools, normalize
vendor effort settings, remove every inherited credential, or create a new scientific Python/Julia environment per run.
Configure the agent host and container/network policy yourself and report them. Workspace preparation alone is not
isolation. See [the isolation guide](EVALUATE-YOUR-SKILLS.md#isolation). No public automated leakage audit is claimed.

## Metrics and paired add-ons

**Completion** is the fraction of attempted runs passing every check. Missing final records count as failures.
**pass^k** is the fraction of instances for which all k attempts pass; report it only with a complete fixed repeat schedule.
Report tokens and elapsed time with missing resource observations disclosed; provider token counts are not billing costs.

For add-ons, pair the same model, settings, task instance, run number, tools and time cap, with the add-on in one arm only.
Each arm needs independent isolation. Freeze the add-on contents and report its hash and exposure declaration.
`mrab compare` checks recorded pairing and configuration consistency; its primary test is an instance-level sign-flip
comparison with a cluster-bootstrap interval. Its run-level McNemar statistic is secondary. These community comparison
statistics differ from the two-way study bootstrap above. See [EVALUATE-YOUR-SKILLS.md](EVALUATE-YOUR-SKILLS.md).

## Future hidden evaluation

Independent task review, repeated-run studies and a publicly accessible hidden-task submission service remain planned.
A future protocol must fix the hidden set, coverage, repetition schedule, error handling, resource limits and hash
commitments before evaluation. Its results will be labeled separately. See [ROADMAP.md](ROADMAP.md).
