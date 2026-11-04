#!/usr/bin/env python3
"""Build the offline Core board and descriptive Hard aggregates from a sanitized snapshot.

Import the approved handoff with --study-root PATH. Otherwise use the checked-in
snapshot; no private checkout, raw traces, network access or model runs are needed.
--check compares deterministic artifacts without writing any files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO / "leaderboard" / "offline-results-2026-11-03.json"
BOARD = REPO / "leaderboard" / "leaderboard.json"
DATE = "2026-11-03"
SOURCE_COMMIT = "8cede909b1808bc09dea00cc1dd3cd0789c74ac6"
SOURCE_REPOSITORY = "https://github.com/kewang_adobe/mri-agent-study"
SOURCE_FILES = {
    "summary": "docs/research/results/offline-summary.json",
    "pairs": "manuscript/work-v41/eval-v41/offline-pairs.json",
    "handoff": "docs/HANDOFF-2026-11-03.md",
}
# Exact files from SOURCE_COMMIT. Changing the approved handoff requires updating
# these pins and the provenance together, never merely relabelling arbitrary data.
SOURCE_SHA256 = {
    "summary": "dfadc34f3fa62642e59ec4c0f418e1af3b083c79b1aa38c3983e19ddae029437",
    "pairs": "86d2320eef791d4a3bd9fa310f886edba435f8f51bde69bafbed808a59b67760",
    "handoff": "5c07c27a0a1e97c5894ccf9d23cfdde78c1241a7e82c1a037718f6822b7c8fa9",
}
# Pins the canonical sanitized scientific payload too: source-file provenance
# alone cannot establish that a locally edited snapshot still has those results.
PAYLOAD_SHA256 = "3a727ebe9634c21906e77171ac1a3e8d6f2c17f831c2ff8185809038047ac3dc"
ADDON = {
    "name": "MRFoundry",
    "version": "0.14.0",
    "commit": "bd49b95",
    "url": "https://github.com/KeWang0622/MRFoundry",
}
MODELS = {
    "claude-haiku-5-5": "Claude Haiku 5.5",
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-sonnet-5-5": "Claude Sonnet 5.5",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gemini-4-argon": "Gemini 4 Argon",
    "gpt-5.3-codex": "GPT-5.3 Codex",
    "gpt-6.1-sol": "GPT-6.1 Sol",
    "gpt-6.1-terra": "GPT-6.1 Terra",
    "kimi-k3": "Kimi K3",
    "mai-code-1.1-flash": "MAI Code 1.1 Flash",
}
FRONTIER = {"claude-opus-5-5", "gemini-4-argon", "gpt-6.1-sol"}
HARD_MODELS = FRONTIER | {"claude-haiku-5-5", "gemini-3.8-flash", "gpt-5.3-codex", "mai-code-1.1-flash"}
PROVIDERS = {"claude": "Anthropic", "gpt": "OpenAI", "gemini": "Google", "kimi": "Moonshot AI", "mai": "Microsoft"}
COUNTS = ("n", "A", "S", "S_only", "A_only")
PAIR_FIELDS = ("task", "family", "domain", "model", "A", "S", "A_tok", "S_tok", "A_wall", "S_wall")
CAVEATS = [
    "The Hard-tier difference alone is not statistically significant (exact paired P = 0.0614).",
    "Hard results are descriptive aggregates: three frontier models have 30 pairs each; four further models "
    "have 11 each and no system-design tasks. These unequal cohorts do not form a common ranking.",
    "Grok 4.7 was excluded because its API rejected the host's file-editing tool; nine started pairs are not analysed.",
    "143 attempts (94 Core and 49 Hard) failed during setup before the first model turn due to a runner error "
    "and were restarted unchanged.",
    "An 8 GiB per-process memory limit took effect partway through the runs; "
    "both arms of each pair had the same limit.",
    "A known permissive image check accepts a zero-filled reconstruction on one hidden Hard instance.",
    "Core diffusion completion decreased from 17/20 without skills to 15/20 with MRFoundry.",
    "Timeout flags, reasoning-effort settings and repeated-run reliability are unavailable in the sanitized "
    "source and are not inferred from wall times or instance counts.",
]
METHODOLOGY = {
    "arms": {"A": "Without skills", "S": "With MRFoundry 0.14.0 (bd49b95)"},
    "paired_trials": "One baseline and one MRFoundry arm for each model–instance pair; offline evaluation.",
    "difference_ci": "95% two-way cluster bootstrap over task families and models; 4,000 resamples, seed 0.",
    "paired_test": "Two-sided exact sign/McNemar test on discordant pairs.",
    "entry_ci": "95% Wilson interval for a single Core model–arm completion proportion.",
    "hard_cohorts": {
        "strong": "Three frontier models; 15 families × two instances = 30 pairs per model.",
        "other": "Four further models; 11 multi-stage families × one instance = 11 pairs per model; no system tasks.",
    },
    "tokens": "Token ratios are total with/without tokens and tokens per verified success with/without.",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def serialized(value: dict) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def number(value, name: str, *, integer: bool = False):
    require(type(value) in ((int,) if integer else (int, float)), f"{name}: expected a number")
    require(math.isfinite(value), f"{name}: expected a finite number")
    return value


def exact_p(a_only: int, s_only: int) -> float:
    n = a_only + s_only
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(a_only, s_only) + 1)) / 2**n)


def clean_stats(raw: dict, *, overall: bool = False) -> dict:
    """Copy only scalar aggregate fields; never traverse unapproved source fields."""
    out = {k: number(raw[k], k, integer=True) for k in COUNTS}
    n, a, s = out["n"], out["A"], out["S"]
    require(n > 0 and all(0 <= out[k] <= n for k in COUNTS[1:]), "invalid aggregate counts")
    both = a - out["A_only"]
    require(both == s - out["S_only"] and both >= 0, "inconsistent paired counts")
    require(both + out["A_only"] + out["S_only"] <= n, "paired counts exceed sample size")
    out["p"] = number(raw["p"], "p")
    require(math.isclose(out["p"], exact_p(out["A_only"], out["S_only"]), abs_tol=1e-12), "invalid exact P value")
    if overall:
        out["diff"] = number(raw["diff"], "diff")
        require(math.isclose(out["diff"], (s - a) / n, abs_tol=1e-12), "difference disagrees with counts")
        require(isinstance(raw["ci"], list) and len(raw["ci"]) == 2, "expected two CI endpoints")
        out["ci"] = [number(x, "ci") for x in raw["ci"]]
        require(-1 <= out["ci"][0] <= out["ci"][1] <= 1, "invalid difference CI")
        for key in ("tok_ratio", "tok_per_success_ratio"):
            out[key] = number(raw[key], key)
            require(out[key] >= 0, f"invalid {key}")
        require(a > 0 and s > 0, "token-per-success ratio requires successes in both arms")
        require(
            math.isclose(out["tok_per_success_ratio"], out["tok_ratio"] * a / s, abs_tol=1e-12),
            "inconsistent token-per-success ratio",
        )
    return out


def validate_partition(parts: list[dict], total: dict, name: str) -> None:
    require(all(sum(p[k] for p in parts) == total[k] for k in COUNTS), f"{name} does not sum to overall counts")


def public_instances() -> dict[str, tuple[str, str]]:
    return {
        row["instance"]: (read_json(path.parent / "family.json")["id"], row["domain"])
        for path in sorted((REPO / "families").glob("*/instances.json"))
        for row in read_json(path)
    }


def clean_core_pairs(raw_pairs: list[dict]) -> list[dict]:
    known = public_instances()
    rows = []
    for raw in raw_pairs:
        # Hard rows are not inspected, copied, logged or retained.
        if raw.get("set") != "core":
            continue
        require(raw["task"] in known, "Core task must already be in the public family manifest")
        require((raw["family"], raw["domain"]) == known[raw["task"]], "Core family/domain disagrees with manifest")
        require(raw["model"] in MODELS, "unknown Core model")
        row = {k: raw[k] for k in PAIR_FIELDS[:4]}
        for arm in ("A", "S"):
            require(type(raw[arm]) is bool, "Core outcomes must be booleans")
            row[arm] = raw[arm]
            for suffix in ("tok", "wall"):
                key = f"{arm}_{suffix}"
                value = raw.get(key)
                if value is not None:
                    number(value, key, integer=suffix == "tok")
                    require(value >= 0, f"{key} must be nonnegative")
                row[key] = value
        rows.append(row)
    rows.sort(key=lambda row: (row["task"], row["model"]))
    require(len({(row["task"], row["model"]) for row in rows}) == len(rows), "duplicate Core model–instance pair")
    return rows


def paired_counts(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "A": sum(row["A"] for row in rows),
        "S": sum(row["S"] for row in rows),
        "S_only": sum(row["S"] and not row["A"] for row in rows),
        "A_only": sum(row["A"] and not row["S"] for row in rows),
    }


def clean_summary(raw: dict, rows: list[dict]) -> dict:
    out = {}
    domains = {row["domain"] for row in rows}
    for split, models, n_families in (("core", set(MODELS), 24), ("hard", HARD_MODELS, 15)):
        source = raw[split]
        require(source["n_families"] == n_families, f"unexpected {split} family count")
        require(source["n_models"] == len(models), f"unexpected {split} model count")
        require(set(source["by_model"]) == models, f"unexpected {split} model cohort")
        group = {
            "all": clean_stats(source["all"], overall=True),
            "n_families": n_families,
            "n_models": len(models),
        }
        if split == "core":
            require(set(source["by_domain"]) == domains, "Core domain summary disagrees with rows")
            group["by_domain"] = {key: clean_stats(source["by_domain"][key]) for key in sorted(domains)}
            validate_partition(list(group["by_domain"].values()), group["all"], "Core domains")
        group["by_model"] = {key: clean_stats(source["by_model"][key]) for key in sorted(models)}
        validate_partition(list(group["by_model"].values()), group["all"], f"{split} models")
        for model, counts in group["by_model"].items():
            expected = 24 if split == "core" else 30 if model in FRONTIER else 11
            require(counts["n"] == expected, "unexpected per-model cohort size")
        if split == "hard":
            for key in ("multistage", "system", "strong", "other"):
                group[key] = clean_stats(source[key])
            for keys in (("multistage", "system"), ("strong", "other")):
                validate_partition([group[k] for k in keys], group["all"], "Hard cohorts")
            for cohort, members in (("strong", FRONTIER), ("other", HARD_MODELS - FRONTIER)):
                validate_partition([group["by_model"][m] for m in members], group[cohort], f"Hard {cohort}")
            require(group["system"]["n"] == 24 and group["multistage"]["n"] == 110, "unexpected Hard task cohorts")
        out[split] = group
    out["combined"] = clean_stats(raw["combined"])
    validate_partition([out["core"]["all"], out["hard"]["all"]], out["combined"], "combined sets")
    core = out["core"]
    require(paired_counts(rows) == {k: core["all"][k] for k in COUNTS}, "Core rows disagree with overall statistics")
    require(len({row["family"] for row in rows}) == core["n_families"], "Core family count disagrees with rows")
    for field, summary_key in (("domain", "by_domain"), ("model", "by_model")):
        for key, counts in core[summary_key].items():
            actual = paired_counts([row for row in rows if row[field] == key])
            require(actual == {k: counts[k] for k in COUNTS}, f"Core {field} rows disagree with statistics")
    instances = {row["task"] for row in rows}
    require(len(instances) == 24, "expected one Core instance per family")
    for model in MODELS:
        require({row["task"] for row in rows if row["model"] == model} == instances, "incomplete Core model coverage")
    if all(row[f"{arm}_tok"] is not None for row in rows for arm in ("A", "S")):
        totals = {arm: sum(row[f"{arm}_tok"] for row in rows) for arm in ("A", "S")}
        require(totals["A"] > 0, "expected positive baseline token total")
        require(math.isclose(totals["S"] / totals["A"], core["all"]["tok_ratio"], abs_tol=1e-12), "Core token mismatch")
    return out


def clean_provenance(raw: dict) -> dict:
    require(raw["repository"] == SOURCE_REPOSITORY and raw["commit"] == SOURCE_COMMIT, "unexpected source revision")
    files = {}
    for name, path in SOURCE_FILES.items():
        source = raw["files"][name]
        require(source["path"] == path, "unexpected source path")
        require(source["sha256"] == SOURCE_SHA256[name], f"{name}: source hash does not match approved handoff")
        files[name] = {"path": path, "sha256": source["sha256"]}
    return {"repository": SOURCE_REPOSITORY, "commit": SOURCE_COMMIT, "files": files}


def sanitize_snapshot(raw: dict) -> dict:
    require(raw["schema_version"] == 1 and raw["evaluation_date"] == DATE, "unsupported offline snapshot")
    require(raw["addon"] == ADDON, "unexpected MRFoundry revision")
    rows = clean_core_pairs([dict(row, set="core") for row in raw["core_pairs"]])
    summary = clean_summary(raw["statistics"], rows)
    payload = serialized({"statistics": summary, "core_pairs": rows}).encode("utf-8")
    require(hashlib.sha256(payload).hexdigest() == PAYLOAD_SHA256, "frozen payload changed from approved handoff")
    return {
        "schema_version": 1,
        "evaluation_date": DATE,
        "addon": dict(ADDON),
        "provenance": clean_provenance(raw["provenance"]),
        "statistics": summary,
        "core_pairs": rows,
    }


def import_study(study_root: Path) -> dict:
    # Parse the same bytes whose hashes were checked, so a changing source file
    # cannot acquire provenance from a different read of its contents.
    contents = {name: (study_root / path).read_bytes() for name, path in SOURCE_FILES.items()}
    provenance = clean_provenance(
        {
            "repository": SOURCE_REPOSITORY,
            "commit": SOURCE_COMMIT,
            "files": {
                name: {"path": path, "sha256": hashlib.sha256(contents[name]).hexdigest()}
                for name, path in SOURCE_FILES.items()
            },
        }
    )
    rows = clean_core_pairs(json.loads(contents["pairs"]))
    snapshot = {
        "schema_version": 1,
        "evaluation_date": DATE,
        "addon": dict(ADDON),
        "provenance": provenance,
        "statistics": clean_summary(json.loads(contents["summary"]), rows),
        "core_pairs": rows,
    }
    return sanitize_snapshot(snapshot)


def wilson(k: int, n: int) -> list[float]:
    z = 1.959964
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def build(snapshot: dict) -> dict:
    snapshot = sanitize_snapshot(snapshot)
    rows = snapshot["core_pairs"]
    instances = sorted({row["task"] for row in rows})
    entries = []
    for model in sorted(MODELS):
        model_rows = [row for row in rows if row["model"] == model]
        for arm in ("A", "S"):
            n = len(model_rows)
            verified = sum(row[arm] for row in model_rows)
            by_domain = defaultdict(lambda: {"verified": 0, "runs": 0})
            for row in model_rows:
                by_domain[row["domain"]]["verified"] += row[arm]
                by_domain[row["domain"]]["runs"] += 1
            tokens = [row[f"{arm}_tok"] for row in model_rows if row[f"{arm}_tok"] is not None]
            walls = [row[f"{arm}_wall"] for row in model_rows if row[f"{arm}_wall"] is not None]
            entries.append(
                {
                    "id": model + ("+mrfoundry" if arm == "S" else ""),
                    "model": model,
                    "model_name": MODELS[model],
                    "provider": PROVIDERS[model.split("-")[0]],
                    "agent": "Codex CLI (app-server), offline evaluation",
                    "addon": dict(ADDON) if arm == "S" else None,
                    "runs": n,
                    "verified": verified,
                    "rate": round(verified / n, 4),
                    "ci95": wilson(verified, n),
                    "ci95_method": "Wilson 95% interval for a single-arm proportion",
                    "instances_covered": len(model_rows),
                    "complete": len(model_rows) == len(instances),
                    "median_tokens": int(statistics.median(tokens)) if tokens else None,
                    "median_wall_s": round(statistics.median(walls), 1) if walls else None,
                    "by_domain": dict(sorted(by_domain.items())),
                    "per_instance": {row["task"]: {"verified": int(row[arm]), "runs": 1} for row in model_rows},
                    "sources": ["offline-core"],
                }
            )
    entries.sort(key=lambda entry: (-entry["rate"], entry["model"], entry["id"]))
    return {
        "benchmark": "MRI Agent Bench",
        "board": "preview",
        "protocol": "offline",
        "version": "0.1.0.dev0",
        "generated": DATE + "T00:00:00+00:00",
        "split": {
            "name": "offline-core",
            "instances": instances,
            "description": "Core: 24 families × 10 models, one sealed instance per family "
            "and one paired trial per model.",
        },
        "domains": sorted({row["domain"] for row in rows}),
        "metric": "verified completion: share of runs in which every automated check passes",
        "excluded_not_started": {"core": 94, "hard": 49},
        "entries": entries,
        "sources": {"offline-core": "Completed offline Core evaluation; approved handoff dated 3 November 2026."},
        "notes": [
            "The ranked board uses only the 240 Core pairs (480 arms); all 20 model–arm entries cover 24 instances.",
            "All add-on results use MRFoundry 0.14.0 at commit bd49b95.",
            "Hard results are shown separately as descriptive aggregates for unequal cohorts, without task-level data.",
            "Entry confidence intervals are Wilson intervals; paired difference intervals "
            "use the source cluster bootstrap.",
            "The generated date records the frozen handoff date, not the time this file was rebuilt.",
        ],
        "offline_evaluation": {
            **snapshot["statistics"],
            "provenance": snapshot["provenance"],
            "methodology": METHODOLOGY,
            "caveats": CAVEATS,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study-root", type=Path, help="Import the approved handoff from a private study checkout")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--out", type=Path, default=BOARD)
    parser.add_argument("--check", action="store_true", help="Fail if either artifact differs; do not write")
    args = parser.parse_args(argv)
    try:
        snapshot = import_study(args.study_root) if args.study_root else sanitize_snapshot(read_json(args.snapshot))
        board = build(snapshot)
        outputs = ((args.snapshot, serialized(snapshot)), (args.out, serialized(board)))
        stale = []
        for path, content in outputs:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path)
                if not args.check:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
        if args.check and stale:
            for path in stale:
                print(f"out of date: {path}")
            return 1
        action = "checked" if args.check else "built"
        print(f"Offline board {action}: 240 Core pairs, 20 entries; 134 Hard pairs (aggregates).")
        return 0
    except (KeyError, TypeError, ValueError, OSError) as exc:
        # Validation errors never print raw source rows or values.
        parser.error(str(exc) if isinstance(exc, ValueError | OSError) else "invalid source structure")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
