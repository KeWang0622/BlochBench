"""Instance data: fetch packages, verify them against their frozen manifests, prepare agent workspaces."""

from __future__ import annotations

import os
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .common import MrabError, sha256_file

DEFAULT_DATA_URL = "https://github.com/KeWang0622/BlochBench/releases/download/core-v0.1.0"


def data_dir() -> Path:
    """Directory holding fetched instances (MRAB_DATA, default ~/mragentbench/data, outside any clone)."""
    return Path(os.environ.get("MRAB_DATA") or Path.home() / "mragentbench" / "data").resolve()


def fetch_instance(instance: dict, url: str | None = None, from_dir: str | None = None) -> tuple[Path, bool]:
    """Put an instance into the data directory; returns (path, already_present).

    From a local folder (from_dir/<source> or from_dir/<instance>) the instance is copied; otherwise the package
    <base>/<package> is downloaded from url or MRAB_DATA_URL, checked against package_sha256 and extracted.
    """
    data = data_dir()
    dest = data / instance["instance"]
    if dest.exists():
        return dest, True
    data.mkdir(parents=True, exist_ok=True)
    if from_dir:
        src = Path(from_dir) / instance["source"]
        if not src.exists():
            src = Path(from_dir) / instance["instance"]
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
        return dest, False
    base = url or os.environ.get("MRAB_DATA_URL") or DEFAULT_DATA_URL
    package = data / instance["package"]
    urllib.request.urlretrieve(base.rstrip("/") + "/" + instance["package"], package)
    if instance.get("package_sha256") and sha256_file(package) != instance["package_sha256"]:
        raise MrabError("package checksum mismatch")
    with tarfile.open(package) as archive:
        archive.extractall(data, filter="data")
    package.unlink()
    return dest, False


def read_manifest(path: Path) -> list[tuple[str, str]]:
    """Parse a FROZEN-SHA256.txt manifest into (sha256, relative path) pairs.

    Blank lines and comment lines (starting with #) are skipped; a leading * on the path (binary mode in sha256sum
    output) is removed.
    """
    entries = []
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        digest, rel = line.split(None, 1)
        entries.append((digest, rel.strip().lstrip("*")))
    return entries


@dataclass
class VerifyResult:
    """Outcome of checking an instance against its frozen manifest."""

    files: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mismatches


def verify_instance(instance: dict) -> VerifyResult:
    """Check every file of a fetched instance against FROZEN-SHA256.txt (and the manifest against the catalog)."""
    root = data_dir() / instance["instance"]
    manifest = root / "FROZEN-SHA256.txt"
    if not manifest.exists():
        raise MrabError("no manifest; fetch the instance first")
    if instance.get("manifest_sha256") and sha256_file(manifest) != instance["manifest_sha256"]:
        raise MrabError("manifest hash differs from the catalog")
    result = VerifyResult()
    for digest, rel in read_manifest(manifest):
        path = root / rel
        result.files += 1
        if not path.exists() or sha256_file(path) != digest:
            result.mismatches.append(rel)
    return result


def prepare_workspace(instance: dict, workdir: Path | str) -> Path:
    """Create an agent workspace holding only the public inputs and TASK.txt (the instance prompt).

    The workspace must not exist yet or be empty.
    """
    root = data_dir() / instance["instance"]
    if not root.exists():
        raise MrabError(f"instance {instance['instance']} not in {data_dir()}; run mrab fetch first")
    work = Path(workdir).resolve()
    if work.exists() and any(work.iterdir()):
        raise MrabError(f"{work} is not empty")
    work.mkdir(parents=True, exist_ok=True)
    public = root / "public"
    for path in sorted(public.rglob("*")):
        if path.is_file():
            target = work / path.relative_to(public)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    shutil.copyfile(root / "prompt.txt", work / "TASK.txt")
    return work
