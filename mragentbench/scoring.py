"""Scoring: verified completion, pass^k and cost for single runs; paired add-on analysis.

Single-agent results (long-format CSV, as written by mrab collect):
    family, instance, domain, config, run, passed (0/1), tokens, wall_s
Paired add-on results (one row per pair, as written by mrab compare --csv):
    family, instance, run, domain, model, base_passed, addon_passed, base_tokens, addon_tokens

Repeated runs of one instance are not independent, so the primary paired analysis is at the instance level: each
instance contributes the difference between its add-on and base verified rates over its runs. The selected independent
unit (instance or family) is used for both the exact sign-flip and sign tests and the 95% cluster-bootstrap interval.
Family sign flips keep all variants together while preserving equal-instance weighting. The run-level exact McNemar
test, which treats every run as an independent pair, is kept as a
labelled secondary statistic and is the only one available for older CSV files without an instance column.
"""

from __future__ import annotations

import collections
import math
import random
from collections.abc import Iterable, Mapping
from fractions import Fraction
from functools import reduce

from .common import MrabError

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar P for b and c discordant pairs (binomial test with p = 1/2)."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n)


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% Wilson score interval of a proportion (the interval used on the leaderboard)."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def single_lines(rows: Iterable[Mapping[str, str]]) -> list[str]:
    """Per configuration: verified runs, pass^k over the k runs every cell has, tokens per verified result, domains."""
    by_config: dict[str, list[Mapping[str, str]]] = collections.defaultdict(list)
    for row in rows:
        by_config[row["config"]].append(row)
    lines = []
    for config, runs in by_config.items():
        n = len(runs)
        ok = sum(int(r["passed"]) for r in runs)
        tokens = sum(float(r.get("tokens") or 0) for r in runs)
        cells: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
        for r in runs:
            cells[(r["family"], r["instance"])].append(int(r["passed"]))
        k = min(len(v) for v in cells.values())
        pass_k = sum(all(v[:k]) for v in cells.values())
        lines.append(
            f"{config}: verified {ok}/{n} ({100 * ok / n:.1f}%), pass^{k} {pass_k}/{len(cells)} "
            f"({100 * pass_k / len(cells):.1f}%), tokens per verified result {tokens / max(ok, 1) / 1e6:.2f} M"
        )
        for domain in sorted({r["domain"] for r in runs}):
            in_domain = [r for r in runs if r["domain"] == domain]
            passed = sum(int(r["passed"]) for r in in_domain)
            lines.append(f"   {domain:8s} {passed}/{len(in_domain)}")
    return lines


def single(rows: Iterable[Mapping[str, str]]) -> None:
    """Print the single-agent summary."""
    for line in single_lines(rows):
        print(line)


def paired_stats(rows: list[Mapping[str, object]]) -> dict:
    """Counts for paired results: verified in each arm, discordant pairs, exact McNemar P, per-domain counts."""

    def passed(row: Mapping[str, object], key: str) -> int:
        return int(row[key])  # type: ignore[call-overload]

    n = len(rows)
    base = sum(passed(r, "base_passed") for r in rows)
    addon = sum(passed(r, "addon_passed") for r in rows)
    addon_only = sum(1 for r in rows if passed(r, "addon_passed") and not passed(r, "base_passed"))
    base_only = sum(1 for r in rows if passed(r, "base_passed") and not passed(r, "addon_passed"))
    domains = {}
    for domain in sorted({str(r["domain"]) for r in rows}):
        in_domain = [r for r in rows if r["domain"] == domain]
        domains[domain] = dict(
            pairs=len(in_domain),
            base_verified=sum(passed(r, "base_passed") for r in in_domain),
            addon_verified=sum(passed(r, "addon_passed") for r in in_domain),
        )
    return dict(
        pairs=n,
        base_verified=base,
        addon_verified=addon,
        addon_only=addon_only,
        base_only=base_only,
        mcnemar_p=mcnemar(addon_only, base_only),
        domains=domains,
    )


def sign_flip_p(differences: list[tuple[int, int, int]]) -> float:
    """Exact two-sided sign-flip P for rational contributions given as (positive, negative, denominator).

    Contributions are per-instance rate differences or their sums within families. Assuming independent units and
    sign symmetry under the null, each contribution is as likely to have either sign. The exact distribution over
    all 2^m flips of the m non-zero contributions is computed by convolution on a common integer scale.
    """
    scale = reduce(math.lcm, (n for _, _, n in differences), 1)
    values = [(a - b) * (scale // n) for a, b, n in differences]
    observed = abs(sum(values))
    nonzero = [abs(v) for v in values if v]
    counts: dict[int, int] = {0: 1}
    for v in nonzero:
        nxt: dict[int, int] = collections.defaultdict(int)
        for total, count in counts.items():
            nxt[total + v] += count
            nxt[total - v] += count
        counts = nxt
    extreme = sum(count for total, count in counts.items() if abs(total) >= observed)
    return min(1.0, extreme / 2 ** len(nonzero))


def cluster_bootstrap(
    clusters: Mapping[str, list[float]], resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float]:
    """95% percentile interval of the mean per-instance difference, resampling clusters with replacement."""
    keys = sorted(clusters)
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        values = [d for key in rng.choices(keys, k=len(keys)) for d in clusters[key]]
        means.append(sum(values) / len(values))
    means.sort()
    return means[int(0.025 * resamples)], means[math.ceil(0.975 * resamples) - 1]


def instance_stats(
    rows: list[Mapping[str, object]],
    cluster: str = "instance",
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Equal-instance paired estimate; bootstrap and exact tests use the selected independent unit."""
    if cluster not in {"instance", "family"}:
        raise MrabError("cluster must be instance or family")
    models = {str(r["model"]) for r in rows if r.get("model")}
    if len(models) > 1:
        raise MrabError("paired inference requires one model; analyze each model separately")
    by_instance: dict[str, dict] = {}
    for r in rows:
        inst = by_instance.setdefault(str(r["instance"]), dict(family=str(r["family"]), base=0, addon=0, runs=0))
        if inst["family"] != str(r["family"]):
            raise MrabError(f"instance {r['instance']} has conflicting family assignments")
        inst["base"] += int(r["base_passed"])  # type: ignore[call-overload]
        inst["addon"] += int(r["addon_passed"])  # type: ignore[call-overload]
        inst["runs"] += 1
    diffs = {name: (i["addon"] - i["base"]) / i["runs"] for name, i in by_instance.items()}
    better = sum(d > 0 for d in diffs.values())
    worse = sum(d < 0 for d in diffs.values())
    groups: dict[str, list[float]] = collections.defaultdict(list)
    contributions: dict[str, Fraction] = collections.defaultdict(Fraction)
    for name, d in diffs.items():
        key = name if cluster == "instance" else by_instance[name]["family"]
        groups[key].append(d)
        i = by_instance[name]
        contributions[key] += Fraction(i["addon"] - i["base"], i["runs"])
    cluster_better = sum(d > 0 for d in contributions.values())
    cluster_worse = sum(d < 0 for d in contributions.values())
    lo, hi = cluster_bootstrap(groups, resamples, seed)
    return dict(
        n_instances=len(by_instance),
        n_families=len({i["family"] for i in by_instance.values()}),
        runs_per_instance=sorted({i["runs"] for i in by_instance.values()}),
        better=better,
        worse=worse,
        tied=len(diffs) - better - worse,
        mean_difference=sum(diffs.values()) / len(diffs),
        ci95=(lo, hi),
        cluster=cluster,
        n_clusters=len(groups),
        cluster_better=cluster_better,
        cluster_worse=cluster_worse,
        cluster_tied=len(groups) - cluster_better - cluster_worse,
        resamples=resamples,
        seed=seed,
        permutation_p=sign_flip_p([(d.numerator, 0, d.denominator) for d in contributions.values()]),
        sign_test_p=mcnemar(cluster_better, cluster_worse),
    )


def instance_lines(stats: Mapping) -> list[str]:
    """Equal-instance estimate and tests labelled with their independent unit."""
    lo, hi = stats["ci95"]
    directions = ""
    if stats["cluster"] == "family":
        directions = (
            f"; families better {stats['cluster_better']}, worse {stats['cluster_worse']}, tied {stats['cluster_tied']}"
        )
    return [
        f"instances {stats['n_instances']} (families {stats['n_families']}): add-on better on {stats['better']}, "
        f"worse on {stats['worse']}, tied on {stats['tied']}; "
        f"mean difference {100 * stats['mean_difference']:+.1f} pp, "
        f"95% CI {100 * lo:+.1f} to {100 * hi:+.1f} pp (cluster bootstrap over {stats['cluster']} clusters, "
        f"{stats['resamples']} resamples, seed {stats['seed']})",
        f"primary test, {stats['cluster']} level: exact sign-flip permutation P {stats['permutation_p']:.3g}; "
        f"exact sign test P {stats['sign_test_p']:.3g}{directions}",
    ]


def paired_lines(stats: Mapping, instance_level: Mapping | None = None) -> list[str]:
    """The text report of paired_stats (the output of mrab score --paired), instance level first when available."""
    n, base, addon = stats["pairs"], stats["base_verified"], stats["addon_verified"]
    run_level = (
        f"pairs {n}: base {base} ({100 * base / n:.1f}%), with add-on {addon} ({100 * addon / n:.1f}%), "
        f"add-on only {stats['addon_only']}, base only {stats['base_only']}, "
        f"exact McNemar P {stats['mcnemar_p']:.2g}"
    )
    if instance_level:
        lines = instance_lines(instance_level)
        lines.append("secondary, run level (treats repeated runs of an instance as independent): " + run_level)
    else:
        lines = [run_level]
    for domain, d in stats["domains"].items():
        lines.append(f"   {domain:8s} {d['base_verified']} -> {d['addon_verified']} of {d['pairs']}")
    return lines


def paired(rows: list[Mapping[str, object]], cluster: str = "instance") -> None:
    """Print the paired add-on summary (instance level when the rows have an instance column)."""
    import sys

    models = {str(r["model"]) for r in rows if r.get("model")}
    if len(models) > 1:
        raise MrabError("paired inference requires one model; analyze each model separately")
    has_instance = bool(rows) and all(r.get("instance") for r in rows)
    if cluster == "family" and (not has_instance or not all(r.get("family") for r in rows)):
        raise MrabError("--cluster family requires instance and family columns on every paired row")
    if not has_instance:
        print(
            "note: no instance column; only the run-level McNemar test, which treats runs as independent",
            file=sys.stderr,
        )
    for line in paired_lines(paired_stats(rows), instance_stats(rows, cluster=cluster) if has_instance else None):
        print(line)
