#!/usr/bin/env python3
"""Copy one configuration's result records and traces for review; never copy or execute workspaces."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import shutil
import sys
from pathlib import Path

from validate_submission import FIELDS, REPO, SLUG, catalog, read_json, require


def prepare(runs: Path, config: str, output: Path, entries: dict | None = None) -> dict:
    require(bool(SLUG.fullmatch(config)), "config must be a single directory name")
    source = runs / config
    require(source.is_dir(), "configuration directory does not exist")
    folders = sorted(p for p in source.glob("*/*") if p.is_dir() and p.name.startswith("run"))
    require(bool(folders), "no run folders found")
    require(not output.exists(), "output directory already exists; choose a new directory")
    entries = catalog() if entries is None else entries
    output.mkdir(parents=True)
    rows, records = [], []
    for folder in folders:
        require(re.fullmatch(r"run[1-9][0-9]*", folder.name) is not None, "invalid run folder name")
        instance, run = folder.parent.name, int(folder.name[3:])
        require(instance in entries, "configuration contains an unknown or nonpublic task")
        require((folder / "started.json").is_file(), f"{instance}/{folder.name}: missing started.json")
        dest = output / "records" / instance / folder.name
        dest.mkdir(parents=True)
        for name in ("started.json", "run.json"):
            if (folder / name).exists():
                require(not (folder / name).is_symlink(), "refuse symlinked evidence")
                shutil.copyfile(folder / name, dest / name)
        trace = folder / "trace.jsonl"
        if trace.is_file():
            require(not trace.is_symlink(), "refuse symlinked evidence")
            with trace.open("rb") as src, gzip.open(dest / "trace.jsonl.gz", "wb") as dst:
                shutil.copyfileobj(src, dst)
        row = dict(
            family=entries[instance]["family"],
            instance=instance,
            domain=entries[instance]["domain"],
            config=config,
            run=run,
            passed=0,
            tokens="",
            wall_s="",
        )
        if (folder / "run.json").exists():
            record = read_json(folder / "run.json")
            records.append(record)
            grade = folder / "grade" / "grade.json"
            if grade.exists():
                require(not grade.is_symlink(), "refuse symlinked evidence")
                shutil.copyfile(grade, dest / "grade.json")
            usage = record.get("usage") or {}
            row.update(passed=int(record.get("verified") is True), wall_s=record.get("wall_s", ""))
            if "input_tokens" in usage and "output_tokens" in usage:
                row["tokens"] = usage["input_tokens"] + usage["output_tokens"]
        else:
            (dest / "incomplete.json").write_text(
                json.dumps({"reason": "No final run.json; replace with the cause."}) + "\n"
            )
        rows.append(row)
    with (output / "runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    meta = read_json(REPO / "examples" / "submission" / "metadata.json")
    meta.update(config=config, instances=sorted({r["instance"] for r in rows}), repeats=max(r["run"] for r in rows))
    if records:
        record = records[0]
        for field in ("model", "agent", "agent_version", "mrab_version"):
            if field in record:
                meta[field] = record[field]
        if record.get("addon_manifest"):
            meta["addon"] = {k: record["addon_manifest"][k] for k in ("name", "version", "content_sha256")}
    (output / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    return dict(
        directory=str(output), attempts=len(rows), note="Review metadata, unfinished reasons and traces before sharing."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs_dir", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.runs_dir, args.config, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"cannot prepare submission: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
