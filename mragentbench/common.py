"""Small helpers shared by the mrab modules (standard library only)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


class MrabError(Exception):
    """A user-facing error. The command line prints the message and exits with status 1."""


class RunInterrupted(Exception):
    """mrab was asked to stop (SIGTERM, SIGHUP or SIGINT) while agents ran; their runs were recorded as interrupted."""

    def __init__(self, signum: int, message: str) -> None:
        super().__init__(message)
        self.signum = signum


def sha256_file(path: Path | str) -> str:
    """Return the hex SHA-256 of a file, read in 1 MiB blocks."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    """Current time as an ISO 8601 UTC timestamp with milliseconds."""
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    """Write JSON with one-space indentation and a trailing newline (the layout of run.json)."""
    path.write_text(json.dumps(data, indent=1) + "\n")
