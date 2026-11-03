"""Compare two configurations run in pairs: verified completion, instance-level tests, cluster-bootstrap interval.

Runs are paired by (instance, run), keyed by their folders RUNS/<config>/<instance>/run<k>/ (exact names only). The
comparison is refused unless every pair is fair:

- both arms have the same agent, model, time cap, command line (template), effort, agent version, mrab version and
  instance manifest; the add-on arm used one add-on content, one AGENTS.md setting and one installed content; the
  base arm recorded no add-on (always enforced);
- every pair was started together by mrab pair (--allow-unpaired accepts runs made separately);
- both arms ran isolated, nothing outside the workspaces reached them (baseline_clean), the scans after the run found
  nothing, and the instance was unchanged (--allow-unisolated accepts such pairs and lists them);
- no started run lacks its run.json (--allow-incomplete counts such runs as failures).

Interrupted runs count as failures. Pairs with an ungraded run (--no-grade) are left out and listed.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .catalog import load_catalog
from .common import MrabError
from .runner import run_tokens
from .scoring import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, instance_stats, paired_lines, paired_stats, wilson

PAIR_CSV_FIELDS = [
    "family",
    "instance",
    "run",
    "domain",
    "model",
    "base_passed",
    "addon_passed",
    "base_tokens",
    "addon_tokens",
]
RUN_FOLDER = re.compile(r"run([1-9][0-9]*)")
# Settings that must be equal in both arms of a pair.
PAIRED_SETTINGS = (
    "agent",
    "model",
    "cap_s",
    "argv_template",
    "effort",
    "agent_version",
    "mrab_version",
    "manifest_sha256",
)
SHOWN = 10


@dataclass
class ConfigRuns:
    """The run folders of one configuration."""

    records: dict[tuple[str, int], dict] = field(default_factory=dict)
    incomplete: list[tuple[str, int]] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)


def load_config(runs_root: Path, config: str) -> ConfigRuns:
    """Read RUNS/<config>/<instance>/run<k>/run.json, keyed by folder; refuse records that contradict their folder."""
    folder = runs_root / config
    if not folder.is_dir():
        raise MrabError(f"no runs of configuration {config} in {runs_root}")
    out = ConfigRuns()
    for inst_dir in sorted(p for p in folder.iterdir() if p.is_dir()):
        for run_dir in sorted(p for p in inst_dir.iterdir() if p.is_dir()):
            rel = f"{config}/{inst_dir.name}/{run_dir.name}"
            match = RUN_FOLDER.fullmatch(run_dir.name)
            if not match:
                if (run_dir / "run.json").exists():
                    raise MrabError(f"{rel} holds a run.json but is not named run<k>; move it out of {runs_root}")
                out.ignored.append(rel)
                continue
            key = (inst_dir.name, int(match.group(1)))
            path = run_dir / "run.json"
            if not path.exists():
                out.incomplete.append(key)
                continue
            record = json.loads(path.read_text())
            if record.get("instance") != key[0] or record.get("run") != key[1]:
                raise MrabError(
                    f"{rel}/run.json records instance {record.get('instance')} run {record.get('run')}, "
                    "not those of its folder"
                )
            if record.get("config") != config:
                raise MrabError(f"{rel}/run.json records configuration {record.get('config')}, not {config}")
            out.records[key] = record
    if not out.records and not out.incomplete:
        raise MrabError(f"no runs of configuration {config} in {runs_root}")
    return out


def _label(key: tuple[str, int]) -> str:
    return f"{key[0]}/run{key[1]}"


def _failed_stand_in(key: tuple[str, int], other: dict | None) -> dict:
    """A failing record for a started run without run.json (counted with --allow-incomplete)."""
    entry = load_catalog().get(key[0], {})
    source = other or entry
    return dict(
        instance=key[0],
        run=key[1],
        family=source.get("family", "?"),
        domain=source.get("domain", "?"),
        model=(other or {}).get("model"),
        verified=False,
        usage={},
        incomplete=True,
    )


def _refuse(problem: str, items: list[str], hint: str) -> None:
    shown = "\n".join(f"  {item}" for item in items[:SHOWN]) + ("\n  ..." if len(items) > SHOWN else "")
    raise MrabError(f"{problem}:\n{shown}\n{hint}")


def _isolation_problems(key: tuple[str, int], b: dict, a: dict) -> list[str]:
    problems = []
    for arm, record in (("base", b), ("add-on", a)):
        if not (record.get("isolation") or {}).get("isolated"):
            problems.append(f"{_label(key)}: {arm} arm not isolated")
        if (record.get("instance_check") or {}).get("after", {}).get("ok") is False:
            problems.append(f"{_label(key)}: {arm} arm changed the instance files")
    if "baseline_clean" in b and not b["baseline_clean"]:
        contamination = b.get("contamination") or {}
        found = [k for k, v in contamination.items() if v and k != "clean"]
        detail = f" ({', '.join(found)})" if found else ""
        problems.append(f"{_label(key)}: baseline not clean{detail}")
    return problems


def compare_configs(
    runs_root: Path | str,
    base: str,
    addon: str,
    *,
    allow_incomplete: bool = False,
    allow_unpaired: bool = False,
    allow_unisolated: bool = False,
    cluster: str = "instance",
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Check that the pairs are fair, then compute the instance-level and run-level paired statistics."""
    runs_root = Path(runs_root)
    if base == addon:
        raise MrabError("--base and --addon name the same configuration")
    base_cfg, addon_cfg = load_config(runs_root, base), load_config(runs_root, addon)
    base_runs, addon_runs = dict(base_cfg.records), dict(addon_cfg.records)
    incomplete = sorted({*base_cfg.incomplete, *addon_cfg.incomplete})
    if incomplete and not allow_incomplete:
        _refuse(
            "started runs without run.json (interrupted, crashed or still running)",
            [
                f"{cfg}/{_label(k)}"
                for cfg, keys in ((base, base_cfg.incomplete), (addon, addon_cfg.incomplete))
                for k in keys
            ],
            "Every started run counts: wait for running pairs, or pass --allow-incomplete to count them as failures.",
        )
    for key in base_cfg.incomplete:
        base_runs[key] = _failed_stand_in(key, addon_runs.get(key))
    for key in addon_cfg.incomplete:
        addon_runs[key] = _failed_stand_in(key, base_runs.get(key))

    common = sorted(base_runs.keys() & addon_runs.keys())
    if not common:
        raise MrabError(f"no (instance, run) pairs in common between {base} and {addon}")
    complete = [k for k in common if not (base_runs[k].get("incomplete") or addon_runs[k].get("incomplete"))]

    mismatches, unverifiable = [], []
    for key in complete:
        b, a = base_runs[key], addon_runs[key]
        for name in PAIRED_SETTINGS:
            if name not in b or name not in a:
                unverifiable.append(f"{_label(key)}: {name} not recorded")
            elif b[name] != a[name]:
                mismatches.append(f"{_label(key)}: {name} {b[name]!r} vs {a[name]!r}")
    if mismatches:
        _refuse(
            f"{base} and {addon} were not run with the same settings, so they are not paired",
            mismatches,
            "Pairs need the same agent, model, time cap, command line, effort, agent and mrab versions and instance "
            "(mrab pair guarantees this).",
        )
    base_with_addon = [_label(k) for k in complete if base_runs[k].get("addon") or base_runs[k].get("addon_manifest")]
    if base_with_addon:
        _refuse(f"base runs of {base} record an add-on", base_with_addon, "Compare a baseline with an add-on run.")
    addon_records = [addon_runs[k] for k in complete]
    for name, values in (
        (
            "add-on contents (content_sha256)",
            {(r.get("addon_manifest") or {}).get("content_sha256") for r in addon_records},
        ),
        ("AGENTS.md settings (addon_pointer)", {r.get("addon_pointer") for r in addon_records}),
        ("installed contents (addon_installed_sha256)", {r.get("addon_installed_sha256") for r in addon_records}),
    ):
        if len(values) > 1:
            _refuse(
                f"the runs of {addon} used {len(values)} different {name}",
                sorted(map(str, values)),
                "Give every changed add-on, and every --no-agents-md run, its own configuration.",
            )
    not_together = [
        _label(k)
        for k in complete
        if not (base_runs[k].get("pair") and base_runs[k].get("pair") == addon_runs[k].get("pair"))
    ]
    if (not_together or unverifiable) and not allow_unpaired:
        _refuse(
            "pairs not started together by mrab pair, or with settings that cannot be checked",
            not_together + unverifiable,
            "Run pairs with mrab pair, or pass --allow-unpaired (they are then labelled unpaired).",
        )
    unisolated = [p for k in complete for p in _isolation_problems(k, base_runs[k], addon_runs[k])]
    if unisolated and not allow_unisolated:
        _refuse(
            "pairs without enforced isolation or with a baseline that is not clean",
            unisolated,
            "Reported add-on results need per-arm isolation (docs/EVALUATE-YOUR-SKILLS.md); pass --allow-unisolated "
            "to compare anyway (the pairs are then listed).",
        )

    ungraded = [
        _label(k) for k in common if base_runs[k].get("verified") is None or addon_runs[k].get("verified") is None
    ]
    keys = [k for k in common if _label(k) not in ungraded]
    if not keys:
        raise MrabError(f"no graded (instance, run) pairs in common between {base} and {addon}")
    rows = []
    for key in keys:
        b, a = base_runs[key], addon_runs[key]
        check = a.get("addon_check") or {}
        rows.append(
            dict(
                instance=key[0],
                run=key[1],
                family=b["family"],
                domain=b["domain"],
                model=b.get("model"),
                base_passed=int(bool(b.get("verified"))),
                addon_passed=int(bool(a.get("verified"))),
                base_tokens=run_tokens(b),
                addon_tokens=run_tokens(a),
                started_together=bool(b.get("pair")) and b.get("pair") == a.get("pair"),
                addon_intact=check.get("intact") if check else None,
            )
        )
    stats = paired_stats(rows)
    instance_level = instance_stats(rows, cluster=cluster, resamples=resamples, seed=seed)
    n = stats["pairs"]
    base_tokens = sum(r["base_tokens"] for r in rows)
    addon_tokens = sum(r["addon_tokens"] for r in rows)
    ratios = [r["addon_tokens"] / r["base_tokens"] for r in rows if r["base_tokens"]]
    manifests = {
        json.dumps(a["addon_manifest"], sort_keys=True) for a in addon_runs.values() if a.get("addon_manifest")
    }
    interrupted = sorted(
        {
            f"{cfg}/{_label(k)}"
            for cfg, runs in ((base, base_runs), (addon, addon_runs))
            for k in keys
            if runs[k].get("interrupted")
        }
    )
    return dict(
        format="mragentbench-compare/2",
        runs_dir=str(runs_root.resolve()),
        base_config=base,
        addon_config=addon,
        pairs=n,
        n_instances=instance_level["n_instances"],
        n_families=instance_level["n_families"],
        instance_level=instance_level,
        started_together=sum(r["started_together"] for r in rows),
        base=dict(
            verified=stats["base_verified"], rate=stats["base_verified"] / n, wilson95=wilson(stats["base_verified"], n)
        ),
        addon=dict(
            verified=stats["addon_verified"],
            rate=stats["addon_verified"] / n,
            wilson95=wilson(stats["addon_verified"], n),
        ),
        difference_pp=round(100 * (stats["addon_verified"] - stats["base_verified"]) / n, 2),
        run_level=dict(
            note="secondary: treats repeated runs of an instance as independent pairs",
            addon_only=stats["addon_only"],
            base_only=stats["base_only"],
            mcnemar_p=stats["mcnemar_p"],
        ),
        addon_only=stats["addon_only"],
        base_only=stats["base_only"],
        mcnemar_p=stats["mcnemar_p"],
        domains=stats["domains"],
        tokens=dict(
            base_total=base_tokens,
            addon_total=addon_tokens,
            ratio=addon_tokens / base_tokens if base_tokens else None,
            median_pair_ratio=statistics.median(ratios) if ratios else None,
        ),
        unmatched=dict(
            base_only=[_label(k) for k in sorted(base_runs.keys() - addon_runs.keys())],
            addon_only=[_label(k) for k in sorted(addon_runs.keys() - base_runs.keys())],
        ),
        addon_manifests=[json.loads(m) for m in sorted(manifests)],
        addon_modified=[f"{r['instance']}/run{r['run']}" for r in rows if r["addon_intact"] is False],
        allowed=dict(incomplete=allow_incomplete, unpaired=allow_unpaired, unisolated=allow_unisolated),
        incomplete=[
            f"{cfg}/{_label(k)}" for cfg, ks in ((base, base_cfg.incomplete), (addon, addon_cfg.incomplete)) for k in ks
        ],
        interrupted=interrupted,
        unpaired=not_together + unverifiable,
        unisolated=unisolated,
        ungraded=ungraded,
        ignored_folders=base_cfg.ignored + addon_cfg.ignored,
        rows=rows,
    )


def compare_lines(result: dict[str, Any]) -> list[str]:
    """Text report of compare_configs: arm rates, the instance-level primary test, the run-level secondary test."""
    n = result["pairs"]
    width = max(len(result["base_config"]), len(result["addon_config"]))
    lines = []
    for label, arm, cfg in (("base  ", "base", result["base_config"]), ("add-on", "addon", result["addon_config"])):
        lo, hi = result[arm]["wilson95"]
        lines.append(
            f"{label} {cfg:{width}s}  verified {result[arm]['verified']}/{n} "
            f"({100 * result[arm]['rate']:.1f}%, 95% CI {100 * lo:.1f}-{100 * hi:.1f})"
        )
    stats = dict(
        pairs=n,
        base_verified=result["base"]["verified"],
        addon_verified=result["addon"]["verified"],
        addon_only=result["addon_only"],
        base_only=result["base_only"],
        mcnemar_p=result["mcnemar_p"],
        domains=result["domains"],
    )
    lines += paired_lines(stats, result["instance_level"])
    tokens = result["tokens"]
    if tokens["ratio"] is not None:
        lines.append(
            f"tokens (input + output): add-on / base {tokens['ratio']:.2f} overall "
            f"({tokens['addon_total'] / 1e6:.2f} M / {tokens['base_total'] / 1e6:.2f} M), "
            f"median per pair {tokens['median_pair_ratio']:.2f}"
        )
    else:
        lines.append("tokens: no usage recorded for the base arm")
    lines.append(f"pairs started together (mrab pair): {result['started_together']} of {n}")
    unmatched = result["unmatched"]
    if unmatched["base_only"] or unmatched["addon_only"]:
        lines.append(
            f"unmatched runs left out: {len(unmatched['base_only'])} base only, "
            f"{len(unmatched['addon_only'])} add-on only"
        )
    for manifest in result["addon_manifests"]:
        seen = manifest.get("exposure", {}).get("public_instances_seen")
        label = {True: "yes", False: "no", "partial": "partly"}.get(seen, "not declared")
        lines.append(
            f"add-on {manifest.get('name')} {manifest.get('version')} "
            f"(content sha256 {str(manifest.get('content_sha256'))[:12]}), public instances seen: {label}"
        )
    warnings = [
        ("addon_modified", "the installed add-on changed during {n} run(s)"),
        ("incomplete", "{n} started run(s) without run.json counted as failures (--allow-incomplete)"),
        ("interrupted", "{n} interrupted run(s) counted as failures"),
        ("unpaired", "{n} pair(s) not started together or not fully checked (--allow-unpaired)"),
        ("unisolated", "{n} problem(s) with isolation or baseline cleanliness (--allow-unisolated)"),
        ("ungraded", "{n} pair(s) left out because a run was not graded"),
        ("ignored_folders", "{n} folder(s) not named run<k> ignored"),
    ]
    for key, text in warnings:
        if result[key]:
            items = result[key]
            shown = ", ".join(items[:SHOWN]) + (", ..." if len(items) > SHOWN else "")
            lines.append(f"warning: {text.format(n=len(items))}: {shown}")
    return lines


def write_pairs_csv(result: dict[str, Any], path: Path) -> None:
    """Write the pairs in the CSV format of mrab score --paired."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PAIR_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["rows"])
