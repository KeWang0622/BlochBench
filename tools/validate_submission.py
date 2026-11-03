#!/usr/bin/env python3
"""Check public result records without executing agent output, graders or network requests."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIELDS = ["family", "instance", "domain", "config", "run", "passed", "tokens", "wall_s"]
SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+@-]*")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name}: expected a JSON object")
    return value


def catalog(root: Path = REPO / "families") -> dict:
    result = {}
    for path in sorted(root.glob("*/instances.json")):
        checks = read_json(path.parent / "family.json")["checks"]
        for entry in json.loads(path.read_text()):
            result[entry["instance"]] = dict(entry, family=path.parent.name, checks=checks)
    return result


def number(value: object) -> float:
    require(not isinstance(value, bool), "expected a nonnegative number")
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected a nonnegative number") from exc
    require(math.isfinite(n) and n >= 0, "expected a finite nonnegative number")
    return n


def validate_metadata(meta: dict, entries: dict) -> set[tuple[str, int]]:
    fields = {
        "format",
        "track",
        "benchmark_commit",
        "config",
        "model",
        "agent",
        "agent_version",
        "mrab_version",
        "instances",
        "repeats",
        "network",
        "hardware",
        "addon",
        "deviations",
        "redactions",
        "all_started_runs_included",
    }
    require(
        set(meta) == fields,
        f"metadata fields: missing {sorted(fields - set(meta))}; unexpected {sorted(set(meta) - fields)}",
    )
    require(meta["format"] == "blochbench-results/1", "unsupported metadata format")
    require(meta["track"] in ("exploratory", "full-core"), "track must be exploratory or full-core")
    require(
        isinstance(meta["benchmark_commit"], str)
        and re.fullmatch(r"[0-9a-f]{40}", meta["benchmark_commit"]) is not None,
        "benchmark_commit must be the full 40-character evaluation commit",
    )
    for key in ("config", "model", "agent", "mrab_version", "hardware"):
        require(isinstance(meta[key], str) and bool(meta[key].strip()), f"{key}: required nonempty string")
    require(bool(SLUG.fullmatch(meta["config"])), "config must be a single directory name")
    require(meta["agent_version"] is None or isinstance(meta["agent_version"], str), "invalid agent_version")
    require(meta["network"] in ("offline", "web", "custom"), "network must be offline, web or custom")
    for key in ("deviations", "redactions"):
        require(
            isinstance(meta[key], list) and all(isinstance(x, str) and x.strip() for x in meta[key]),
            f"{key}: expected a list of descriptions",
        )
    if meta["agent_version"] is None:
        require(bool(meta["deviations"]), "explain the unavailable agent version in deviations")
    require(meta["all_started_runs_included"] is True, "confirm that every started attempt is included")
    require(type(meta["repeats"]) is int and 1 <= meta["repeats"] <= 100, "repeats must be 1–100")
    instances = meta["instances"]
    require(
        isinstance(instances, list) and bool(instances) and all(isinstance(x, str) for x in instances),
        "instances must explicitly list the evaluated public IDs",
    )
    require(len(set(instances)) == len(instances), "duplicate metadata instance")
    require(set(instances) <= set(entries), "unknown or nonpublic instance")
    if meta["track"] == "full-core":
        require(
            set(instances) == set(entries) and meta["repeats"] == 3,
            "full-core requires all catalog instances, three attempts each",
        )
    addon = meta["addon"]
    if addon is not None:
        require(
            isinstance(addon, dict) and set(addon) == {"name", "version", "content_sha256"},
            "addon must be null or name/version/content_sha256",
        )
        require(all(isinstance(v, str) and v for v in addon.values()), "invalid addon values")
        require(re.fullmatch(r"[0-9a-f]{64}", addon["content_sha256"]) is not None, "invalid addon hash")
    return {(instance, run) for instance in instances for run in range(1, meta["repeats"] + 1)}


def validate(root: Path, entries: dict | None = None) -> dict:
    root = root.resolve()
    require(root.is_dir(), "submission directory does not exist")
    require(not any(p.is_symlink() for p in root.rglob("*")), "submission must not contain symbolic links")
    entries = catalog() if entries is None else entries
    meta = read_json(root / "metadata.json")
    expected = validate_metadata(meta, entries)
    with (root / "runs.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == FIELDS, "runs.csv must use the mrab collect column order")
        rows = list(reader)
    observed = set()
    successes = unfinished = missing_usage = 0
    for row in rows:
        require(set(row) == set(FIELDS) and all(v is not None for v in row.values()), "malformed CSV row")
        require(row["run"].isdigit() and str(int(row["run"])) == row["run"], "run must be a positive integer")
        key = (row["instance"], int(row["run"]))
        require(key in expected, "CSV contains an undeclared instance or repeat")
        require(key not in observed, "duplicate CSV attempt")
        observed.add(key)
        entry = entries[key[0]]
        label = f"{key[0]}/run{key[1]}"
        require(row["family"] == entry["family"] and row["domain"] == entry["domain"], f"{label}: wrong family/domain")
        require(row["config"] == meta["config"], f"{label}: wrong configuration")
        require(row["passed"] in ("0", "1"), f"{label}: passed must be 0 or 1")
        folder = root / "records" / key[0] / f"run{key[1]}"
        started = read_json(folder / "started.json")
        for field, value in (("instance", key[0]), ("run", key[1]), ("config", meta["config"])):
            require(started.get(field) == value, f"{label}: started.json {field} disagrees")
        require(
            isinstance(started.get("started_at"), str) and bool(started["started_at"]), f"{label}: missing start time"
        )
        if not (folder / "run.json").exists():
            failure = read_json(folder / "incomplete.json")
            require(
                set(failure) == {"reason"} and isinstance(failure["reason"], str) and bool(failure["reason"].strip()),
                f"{label}: incomplete.json must explain the unfinished attempt",
            )
            require(
                "replace with the cause" not in failure["reason"],
                f"{label}: replace the unfinished-attempt placeholder",
            )
            require(
                row["passed"] == "0" and row["tokens"] == "" and row["wall_s"] == "",
                f"{label}: unfinished attempts are failures with unknown resource use",
            )
            require(
                not (folder / "grade.json").exists(), f"{label}: unfinished attempt has a grade; reconcile it first"
            )
            unfinished += 1
            missing_usage += 1
            continue
        require(not (folder / "incomplete.json").exists(), f"{label}: final and incomplete records both present")
        record = read_json(folder / "run.json")
        for field in ("instance", "family", "domain", "config"):
            require(record.get(field) == row[field], f"{label}: run.json {field} disagrees")
        require(record.get("run") == key[1], f"{label}: run index disagrees")
        for field in ("model", "agent", "agent_version", "mrab_version"):
            require(record.get(field) == meta[field], f"{label}: run.json {field} disagrees with metadata")
        require(record.get("manifest_sha256") == entry.get("manifest_sha256"), f"{label}: task manifest differs")
        if number(record.get("cap_s")) != entry["cap_s"]:
            require(bool(meta["deviations"]), f"{label}: document the changed time cap")
        if meta["addon"] is None:
            require(not record.get("addon") and not record.get("addon_manifest"), f"{label}: undeclared addon")
        else:
            manifest = record.get("addon_manifest") or {}
            require(all(manifest.get(k) == v for k, v in meta["addon"].items()), f"{label}: addon differs")
        verified = record.get("verified") is True
        require(int(row["passed"]) == int(verified), f"{label}: CSV pass differs from run.json")
        grade_path = folder / "grade.json"
        if grade_path.exists():
            grade = read_json(grade_path)
            checks = grade.get("checks")
            require(isinstance(checks, dict), f"{label}: grade has no check map")
            passed_checks = bool(checks) and all(isinstance(v, dict) and v.get("pass") is True for v in checks.values())
            require(
                (grade.get("all_automated_checks_pass") is True) == passed_checks, f"{label}: inconsistent grade checks"
            )
            require(verified == passed_checks, f"{label}: run and grade disagree")
            if verified:
                require(set(checks) == set(entry["checks"]), f"{label}: verified grade omits required checks")
        else:
            require(not verified and not record.get("graded"), f"{label}: missing grade.json")
        require((folder / "trace.jsonl.gz").is_file() or (folder / "trace.jsonl").is_file(), f"{label}: missing trace")
        usage = record.get("usage") or {}
        require(isinstance(usage, dict), f"{label}: invalid token usage")
        if "input_tokens" in usage and "output_tokens" in usage:
            tokens = number(usage["input_tokens"]) + number(usage["output_tokens"])
            require(number(row["tokens"]) == tokens, f"{label}: token total disagrees")
        else:
            require(row["tokens"] == "", f"{label}: unavailable token usage must be blank")
            missing_usage += 1
        require(number(row["wall_s"]) == number(record.get("wall_s")), f"{label}: wall time disagrees")
        successes += int(verified)
    require(observed == expected, f"missing {len(expected - observed)} declared attempts")
    actual = set()
    for path in (root / "records").glob("*/*"):
        require(path.is_dir() and re.fullmatch(r"run[1-9][0-9]*", path.name) is not None, "invalid record folder")
        actual.add((path.parent.name, int(path.name[3:])))
    require(actual == expected, "record folders and declared attempts differ; include every started attempt")
    return dict(
        format="blochbench-validation/1",
        status="consistent-self-report",
        track=meta["track"],
        instances=len(meta["instances"]),
        attempts=len(rows),
        passed=successes,
        completion=successes / len(rows),
        unfinished=unfinished,
        attempts_without_token_usage=missing_usage,
        benchmark_commit=meta["benchmark_commit"],
        note="Record consistency only; no task execution, independent grading or hidden-set verification.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.submission)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"invalid submission: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
