#!/usr/bin/env python3
"""Repair public package transport without changing frozen benchmark files.

Usage: python tools/repair_release_packages.py SOURCE_CACHE RELEASE_DIRECTORY

Only unmanifested symlinks and private/refenv environment artifacts may be removed.
Every package is safely extracted and its frozen files verified before catalogue
package hashes/sizes are updated. The frozen manifests remain byte-identical.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import posixpath
import shutil
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
REPORT = "data-packaging.json"


class PackagingError(ValueError):
    """A package does not meet the narrowly scoped transport repair contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frozen_entries(raw: bytes) -> dict[str, str]:
    entries = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        digest, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise PackagingError("Unsafe path in frozen manifest.")
        name = posixpath.normpath(name)
        if name in entries or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise PackagingError("Duplicate path or invalid digest in frozen manifest.")
        entries[name] = digest
    if not entries:
        raise PackagingError("Frozen manifest is empty.")
    return entries


def archive_plan(path: Path, record: dict) -> dict:
    """Verify frozen bytes and identify only explicitly allowed, unmanifested removals."""
    root = record["instance"]
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        by_relative = {}
        for member in members:
            member_path = PurePosixPath(member.name)
            if (
                member_path.is_absolute()
                or ".." in member_path.parts
                or "\\" in member.name
                or not member_path.parts
                or member_path.parts[0] != root
            ):
                raise PackagingError(f"{path.name}: unsafe or unexpected archive root.")
            relative = str(member_path.relative_to(root))
            if relative in by_relative:
                raise PackagingError(f"{path.name}: duplicate archive member.")
            by_relative[relative] = member

        manifest_member = by_relative.get("FROZEN-SHA256.txt")
        if manifest_member is None or not manifest_member.isfile():
            raise PackagingError(f"{path.name}: missing regular frozen manifest.")
        manifest = archive.extractfile(manifest_member).read()
        if hashlib.sha256(manifest).hexdigest() != record["manifest_sha256"]:
            raise PackagingError(f"{path.name}: frozen manifest hash differs from catalogue.")
        frozen = frozen_entries(manifest)
        retained, removed = [], []
        removed_counts = Counter()
        for relative, member in by_relative.items():
            drop = member.issym() or relative == "private/refenv" or relative.startswith("private/refenv/")
            if drop:
                if relative in frozen or any(name.startswith(relative + "/") for name in frozen):
                    raise PackagingError(f"{path.name}: removal would affect a frozen manifest entry.")
                removed.append(member.name)
                kind = "symlinks" if member.issym() else "files" if member.isfile() else "directories"
                removed_counts[kind] += 1
                removed_counts["file_bytes"] += member.size
            else:
                if not (member.isfile() or member.isdir()):
                    raise PackagingError(f"{path.name}: unsupported member outside removal allowlist.")
                try:
                    tarfile.data_filter(member, str(Path(tempfile.gettempdir()) / "mrab-package-filter"))
                except tarfile.FilterError as exc:
                    raise PackagingError(f"{path.name}: retained member fails safe extraction filter.") from exc
                retained.append(member.name)

        for name, expected in frozen.items():
            member = by_relative.get(name)
            if member is None or not member.isfile():
                raise PackagingError(f"{path.name}: frozen file missing from archive.")
            digest = hashlib.sha256()
            with archive.extractfile(member) as handle:
                for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise PackagingError(f"{path.name}: frozen file content differs from manifest.")
    return {
        "retained": retained,
        "removed": removed,
        "removed_counts": dict(removed_counts),
        "frozen_files": len(frozen),
    }


def write_repaired_archive(source: Path, destination: Path, plan: dict) -> None:
    """Preserve retained members, contents, order, and tar metadata deterministically."""
    keep = set(plan["retained"])
    with tarfile.open(source) as original:
        with tarfile.open(destination, "w", format=tarfile.PAX_FORMAT, pax_headers=original.pax_headers) as repaired:
            for member in original:
                if member.name not in keep:
                    continue
                data = original.extractfile(member) if member.isfile() else None
                try:
                    repaired.addfile(copy.copy(member), data)
                finally:
                    if data is not None:
                        data.close()


def verify_extraction(path: Path, record: dict, scratch: Path) -> int:
    """Actually extract with the harness's data filter and verify every frozen file."""
    with tempfile.TemporaryDirectory(prefix="mrab-package-verify-", dir=scratch) as temporary:
        destination = Path(temporary)
        with tarfile.open(path) as archive:
            archive.extractall(destination, filter="data")
        root = destination / record["instance"]
        raw = (root / "FROZEN-SHA256.txt").read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["manifest_sha256"]:
            raise PackagingError(f"{path.name}: extracted manifest changed.")
        frozen = frozen_entries(raw)
        for name, expected in frozen.items():
            file = root / name
            if not file.is_file() or file.is_symlink() or sha256_file(file) != expected:
                raise PackagingError(f"{path.name}: extracted frozen file failed verification.")
    return len(frozen)


def render_report(report: dict) -> str:
    totals = report["totals"]
    removed = report["removed"]
    lines = [
        "<!-- Generated by tools/repair_release_packages.py. -->",
        "# Public package transport repair",
        "",
        "The original public package cache included local environment links that Python's safe tar extraction "
        "rejects. One archive also included an installed reference environment. This repair removes those "
        "unmanifested artifacts so the packages work with the benchmark's existing fetch command.",
        "",
        "| Item | Count |",
        "|---|---:|",
        f"| Public instance packages | {totals['packages']} |",
        f"| Repacked archives | {totals['repacked']} |",
        f"| Archives copied byte-for-byte | {totals['unchanged']} |",
        f"| Removed environment symlinks | {removed.get('symlinks', 0)} |",
        f"| Removed environment files | {removed.get('files', 0)} |",
        f"| Removed environment directories | {removed.get('directories', 0)} |",
        f"| Frozen file hashes verified after safe extraction | {totals['verified_frozen_files']} |",
        f"| Original archive bytes | {totals['original_bytes']:,} |",
        f"| Release archive bytes | {totals['release_bytes']:,} |",
        "",
        "Only unmanifested symlinks and the `private/refenv` environment tree are eligible for removal. "
        "The repair stops if an eligible entry or any of its descendants appears in a frozen manifest. "
        "All retained file bytes, the frozen manifests, task inputs, graders, references, and controls are preserved. "
        "Unmanifested validation outputs and obsolete Core working files are retained to keep the repair narrow.",
        "",
        "Only `package_sha256` and `package_bytes` change in the instance catalogue. "
        "Every `manifest_sha256` remains unchanged. This changes distribution archives, not task definitions "
        "or recorded scores.",
        "",
        "## Repaired archive hashes",
        "",
        "Prefixes below are for reading; [the machine-readable record](data-packaging.json) contains full "
        "SHA-256 values, byte counts, unchanged manifest hashes, and removal counts for each repaired archive.",
        "",
        "| Archive | Original SHA-256 prefix | Release SHA-256 prefix |",
        "|---|---|---|",
    ]
    for package in report["packages"]:
        lines.append(
            f"| `{package['package']}` | `{package['original_sha256'][:16]}` | `{package['release_sha256'][:16]}` |"
        )
    lines.extend(
        [
            "",
            "## Reproduce and verify",
            "",
            "```bash",
            "python tools/repair_release_packages.py ORIGINAL_CACHE RELEASE_DIRECTORY",
            "```",
            "",
            "The script checks each source archive against its registered hash or the original hash recorded above, "
            "builds deterministic replacement archives, extracts all packages with `tarfile`'s `data` filter, "
            "and verifies every frozen file before updating package hashes and sizes. Existing cached originals "
            "can be reused after the catalogue update because their original hashes remain in the repair record.",
            "",
        ]
    )
    return "\n".join(lines)


def repair_release(source: Path, output: Path, repo: Path = REPO) -> dict:
    if source.resolve() == output.resolve():
        raise PackagingError("Keep the original cache and release directory separate.")
    catalogues = {}
    records = []
    for path in sorted((repo / "families").glob("*/instances.json")):
        entries = json.loads(path.read_text(encoding="utf-8"))
        catalogues[path] = entries
        records.extend(entries)
    if not records or len({record["package"] for record in records}) != len(records):
        raise PackagingError("Missing catalogue or duplicate package names.")
    report_path = repo / "docs" / REPORT
    prior = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {"packages": []}
    history = {entry["package"]: entry for entry in prior["packages"]}
    output.mkdir(parents=True, exist_ok=True)
    verified = 0
    for index, record in enumerate(records, 1):
        name = record["package"]
        if Path(name).name != name:
            raise PackagingError("Package filename must not contain directories.")
        original = source / name
        original_hash = sha256_file(original)
        original_bytes = original.stat().st_size
        registered = (record["package_sha256"], record["package_bytes"])
        historical = history.get(name)
        allowed = {registered}
        if historical and registered == (historical["release_sha256"], historical["release_bytes"]):
            if historical["manifest_sha256"] != record["manifest_sha256"]:
                raise PackagingError(f"{name}: repair record has a different frozen manifest.")
            allowed.add((historical["original_sha256"], historical["original_bytes"]))
        if (original_hash, original_bytes) not in allowed:
            raise PackagingError(f"{name}: source archive hash or size is not registered.")
        plan = archive_plan(original, record)
        handle, temporary_name = tempfile.mkstemp(prefix=".package-", suffix=".tar", dir=output)
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            if plan["removed"]:
                write_repaired_archive(original, temporary, plan)
            else:
                temporary.unlink()
                try:
                    os.link(original, temporary)
                except OSError:
                    shutil.copyfile(original, temporary)
            release_hash = sha256_file(temporary)
            release_bytes = temporary.stat().st_size
            if historical and (release_hash, release_bytes) != (
                historical["release_sha256"],
                historical["release_bytes"],
            ):
                raise PackagingError(f"{name}: repaired archive is not reproducible from its recorded source.")
            verified += verify_extraction(temporary, record, output.parent)
            temporary.replace(output / name)
        finally:
            temporary.unlink(missing_ok=True)
        if plan["removed"]:
            history[name] = {
                "package": name,
                "instance": record["instance"],
                "original_sha256": original_hash,
                "release_sha256": release_hash,
                "original_bytes": original_bytes,
                "release_bytes": release_bytes,
                "manifest_sha256": record["manifest_sha256"],
                "removed": plan["removed_counts"],
            }
        record["package_sha256"] = release_hash
        record["package_bytes"] = release_bytes
        print(f"Verified package {index}/{len(records)}: {name}", flush=True)

    removed = Counter()
    for entry in history.values():
        removed.update(entry["removed"])
    report = {
        "schema_version": 1,
        "repair": "remove-unmanifested-symlinks-and-reference-environment-v1",
        "totals": {
            "packages": len(records),
            "repacked": len(history),
            "unchanged": len(records) - len(history),
            "original_bytes": sum(
                history.get(r["package"], {}).get("original_bytes", r["package_bytes"]) for r in records
            ),
            "release_bytes": sum(r["package_bytes"] for r in records),
            "verified_frozen_files": verified,
        },
        "removed": dict(sorted(removed.items())),
        "packages": [history[name] for name in sorted(history)],
    }
    # Catalogue changes happen only after every output archive passes actual extraction and frozen-file checks.
    for path, entries in catalogues.items():
        before = json.loads(path.read_text(encoding="utf-8"))
        if before != entries:
            path.write_text(json.dumps(entries, indent=1) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (repo / "docs" / "DATA-PACKAGING.md").write_text(render_report(report), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        report = repair_release(args.source, args.output)
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f"Package repair failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report["totals"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
