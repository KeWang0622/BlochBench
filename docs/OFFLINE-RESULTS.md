# Offline evaluation snapshot — 3 November 2026

We report the completed Core and Hard comparisons with and without **MRFoundry 0.14.0** (skill commit `bd49b95`).
All runs used the offline track. This is a maintainer-run preview on one agent host; expert review and the planned
repeated-run verified board remain outstanding. No model experiments were rerun to prepare this repository update.

## Verified completion

Verified completion means every automated check passed. It does not imply independent human review or clinical
validity. Rates use the same number of paired trials in both arms.

| Set | Paired trials | Without skills | With MRFoundry | Paired difference, percentage points (95% CI) | Exact McNemar P |
|---|---:|---:|---:|---:|---:|
| Core | 240 | 162 (67.5%) | 188 (78.3%) | +10.8 (+0.8 to +21.2) | 0.000410 |
| Hard | 134 | 49 (36.6%) | 60 (44.8%) | +8.2 (−3.9 to +19.7) | 0.0614 |

The confidence interval resamples task families and models independently with replacement, using 4,000 resamples
and seed 0. Exact McNemar tests summarize the discordant pairs: 39 versus 13 for Core and 20 versus 9 for Hard
(MRFoundry-only versus baseline-only successes). These trial-level tests are read alongside the clustered intervals.
The Hard interval crosses zero and its exact P value exceeds 0.05.

Core covers 24 families × 10 models, one sealed instance per family. Seven models improve, three tie and none
decrease in overall completion. This does not hold in every domain: **diffusion falls from 17/20 to 15/20**.
The task guide and results retain all ten domains and all ten models.

Hard covers 15 families: 11 multi-stage and four system-design families. Its two model cohorts have different
coverage and are displayed separately:

- Three frontier models: 15 families × two instances, 30 paired trials per model (90 total).
- Four further models: 11 multi-stage families × one instance, 11 paired trials per model (44 total).

There is no single cross-cohort Hard ranking. The four further models have no system-design trials. System-design
completion is 1→3 of 24 paired trials; multi-stage completion is 48→57 of 110. No Hard task identities, prompts,
per-instance outcomes, grader details or traces are distributed with these aggregates.

## Resources

| Measure (with MRFoundry / without skills) | Core | Hard |
|---|---:|---:|
| Total reported tokens | 1.048 | 1.062 |
| All reported tokens / verified successes | 0.903 | 0.868 |

The second measure includes tokens spent on unsuccessful attempts. It is not the average tokens used by successful
runs alone. Token accounting differs across providers, so these ratios are not monetary-cost comparisons. The Core
leaderboard additionally reports median tokens and median wall time per arm from the saved pair records.

## Limitations and recorded incidents

1. The authors also maintain MRFoundry. The tasks are largely synthetic, expert review is pending, and only one
   host is evaluated. Automated completion supports this bounded comparison, not a universal model ranking.
2. Core has one trial per model and family; Hard has unequal model coverage. We do not estimate pass^3, pass^5 or
   reliability across repeated executions of the same instance from this snapshot.
3. The handoff records nine started Grok 4.7 pairs excluded because the API rejected the host's file-editing tool.
   Grok is absent from the analysed model panel.
4. The handoff records 143 pair-setup failures before the first model turn (94 Core, 49 Hard), caused by a runner
   error and restarted unchanged. They are not additional analysed trials or successful model executions.
5. An 8 GiB per-process memory limit took effect partway through the runs. Both arms of each pair had the same
   setting, but the limit was not uniform across the entire experiment.
6. One Hard instance has a documented image-check weakness: a zero-filled reconstruction passes those image
   subchecks. This is a grader limitation, not evidence of verified completion of the whole task. Its task identity
   and grader material remain private. The frozen outcomes are unchanged.

## Provenance and regeneration

The source is the private `mri-agent-study` handoff at commit
`8cede909b1808bc09dea00cc1dd3cd0789c74ac6`, dated 3 November 2026. Source records are
`docs/research/results/offline-summary.json` and `manuscript/work-v41/eval-v41/offline-pairs.json`.
The full source also contains private Hard material and must not be copied wholesale into this repository.

The frozen [disclosure-limited snapshot](../leaderboard/offline-results-2026-11-03.json) retains Core rows and
explicitly allowed Hard aggregates. The importer records source hashes, checks consistency, and builds
[leaderboard.json](../leaderboard/leaderboard.json) deterministically. The saved rows reproduce the supplied totals,
model/domain breakdowns, exact tests, token ratios and clustered intervals; this does not independently audit raw
pod traces or prove the reported runner configuration.

From this repository, without the original pod or any model calls:

~~~bash
python tools/build_offline_leaderboard.py
python tools/build_site.py
make check-results
~~~

To import the same source checkout explicitly:

~~~bash
python tools/build_offline_leaderboard.py --study-root /path/to/mri-agent-study
~~~

The importer excludes older evaluation rounds from the display and rejects inconsistent data. It does not launch
agents, regrade artifacts, rebuild instance packages or change frozen task families. The public research preview distributes Core material and these approved Hard aggregates; full Hard material stays private.
