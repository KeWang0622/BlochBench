# Study results

Frozen maintainer-run offline evaluation handed off on 3 November 2026. Baseline uses no skills; the paired arm uses
MRFoundry 0.14.0 (`bd49b95`). Both arms use the same model, task inputs, harness and time cap, with web search disabled.
These tables are descriptive paired comparisons, not a ranking of general MRI ability.

<!-- RESULTS:START -->
| Evaluation | Paired trials | Baseline | With MRFoundry | Difference (95% CI) |
|---|---:|---:|---:|---:|
| Core | 240 | 162/240 (67.5%) | 188/240 (78.3%) | +10.8 pp (+0.8 to +21.2 pp) |
| Hard | 134 | 49/134 (36.6%) | 60/134 (44.8%) | +8.2 pp (-3.9 to +19.7 pp) |

## Core: paired model results

One instance per task type, 24 trials per arm. Models are listed alphabetically. A pass means every automated check passed; it does not establish general MRI proficiency.

| Model | Baseline passes | With MRFoundry | Difference | Median tokens, baseline → MRFoundry |
|---|---:|---:|---:|---:|
| Claude Haiku 5.5 | 15/24 | 19/24 | +16.7 pp | 5.81 M → 6.33 M |
| Claude Opus 5.5 | 22/24 | 22/24 | +0.0 pp | 1.59 M → 2.01 M |
| Claude Sonnet 5.5 | 17/24 | 23/24 | +25.0 pp | 0.69 M → 0.90 M |
| GPT-5.3 Codex | 9/24 | 13/24 | +16.7 pp | 0.48 M → 1.08 M |
| GPT-6.1 Sol | 19/24 | 22/24 | +12.5 pp | 1.02 M → 1.86 M |
| GPT-6.1 Terra | 22/24 | 22/24 | +0.0 pp | 1.03 M → 1.90 M |
| Gemini 3.8 Flash | 19/24 | 22/24 | +12.5 pp | 5.59 M → 6.90 M |
| Gemini 4 Argon | 21/24 | 24/24 | +12.5 pp | 4.94 M → 4.78 M |
| Kimi K3 | 13/24 | 16/24 | +12.5 pp | 1.47 M → 1.39 M |
| MAI Code 1.1 Flash | 5/24 | 5/24 | +0.0 pp | 1.72 M → 1.62 M |

## Hard: 30-trial cohort

15 task types × 2 instances. Compare models within this cohort only.

| Model | Baseline passes | With MRFoundry | Difference |
|---|---:|---:|---:|
| Claude Opus 5.5 | 16/30 | 20/30 | +13.3 pp |
| GPT-6.1 Sol | 15/30 | 18/30 | +10.0 pp |
| Gemini 4 Argon | 13/30 | 14/30 | +3.3 pp |

## Hard: 11-trial cohort

11 multi-stage task types × 1 instance. Compare models within this cohort only.

| Model | Baseline passes | With MRFoundry | Difference |
|---|---:|---:|---:|
| Claude Haiku 5.5 | 2/11 | 3/11 | +9.1 pp |
| GPT-5.3 Codex | 1/11 | 1/11 | +0.0 pp |
| Gemini 3.8 Flash | 2/11 | 4/11 | +18.2 pp |
| MAI Code 1.1 Flash | 0/11 | 0/11 | +0.0 pp |
<!-- RESULTS:END -->

## Interpretation and limitations

- Core uses 24 task types × 10 models × one instance: 240 paired trials. The public suite contains 88 variants.
- Core aggregate improvement has a two-way family/model bootstrap 95% interval of +0.8 to +21.2 percentage points;
  exact McNemar p = 0.0004095. Diffusion declines from 17/20 to 15/20 passes.
- Hard uses unequal cohorts. Its aggregate interval is −3.9 to +19.7 points; exact McNemar p = 0.0614.
  This does not establish an improvement at the 0.05 level or a ranking across cohorts.
- MRFoundry/baseline total-token ratios are 1.05× (Core) and 1.06× (Hard). Total tokens across **all attempts**, divided
  by successful attempts, give ratios of 0.90× and 0.87×. These are not billing costs or ratios of run medians.
- Task families await independent expert review. The benchmark and MRFoundry share an author.
- Setup restarts, excluded tool-incompatible trials, the memory-cap change and a permissive Hard subcheck are
  documented in [OFFLINE-RESULTS.md](OFFLINE-RESULTS.md). The permissive check was not silently changed or regraded.

[Full protocol and provenance](OFFLINE-RESULTS.md) · [Machine-readable results](../leaderboard/leaderboard.json) ·
[Interactive tables](https://KeWang0622.github.io/BlochBench/leaderboard.html)

Community results follow [SUBMITTING.md](SUBMITTING.md) and do not overwrite this frozen snapshot.
