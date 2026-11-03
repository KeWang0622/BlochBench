"""Grading: run an instance's private grader on a workspace and read grade.json."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .common import MrabError
from .data import data_dir

# One thread per numerical library keeps grading deterministic and light; juliacall must handle signals itself.
GRADER_ENV = {
    "PYTHON_JULIACALL_HANDLE_SIGNALS": "yes",
    "JULIA_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
}


def grade_workspace(instance: dict, work: Path | str, out: Path | str, python: str | None = None) -> dict:
    """Run the private grader of an instance on a workspace; returns the parsed grade.json.

    The grader runs as <python> private/<grader> WORKDIR OUT from the instance's private folder, where OUT is a fresh
    folder created now, after the agent has stopped, so a grade.json planted in advance can never be read. Its files and
    the grader's output (grader-stdout.txt) are then moved to out, which must not exist or be empty. Without a
    grade.json the result counts as a failure with no checks.
    """
    from .runner import register, unregister  # the runner's signal handlers stop graders too

    root = data_dir() / instance["instance"]
    out = Path(out).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise MrabError(f"{out} exists and is not empty; remove it or choose another --out")
    env = dict(os.environ, **GRADER_ENV)
    grader = root / "private" / instance["grader"]
    fresh = Path(tempfile.mkdtemp(prefix="mrab-grade-")).resolve()
    try:
        argv = [python or sys.executable, str(grader), str(Path(work).resolve()), str(fresh)]
        proc = subprocess.Popen(
            argv,
            cwd=root / "private",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        register(proc)
        try:
            stdout, stderr = proc.communicate()
        finally:
            unregister(proc)
        (fresh / "grader-stdout.txt").write_text(stdout + stderr)
        grade_file = fresh / "grade.json"
        try:
            grade = json.loads(grade_file.read_text()) if grade_file.exists() else None
        except ValueError:
            grade = None
        if not isinstance(grade, dict):
            grade = None
        out.mkdir(parents=True, exist_ok=True)
        for item in fresh.iterdir():
            shutil.move(str(item), str(out / item.name))
    finally:
        shutil.rmtree(fresh, ignore_errors=True)
    return grade if grade is not None else {"all_automated_checks_pass": False, "checks": {}}


def is_verified(grade: dict) -> bool:
    """A run is verified when every automated check passed."""
    return bool(grade.get("all_automated_checks_pass"))


def failed_checks(grade: dict) -> list[str]:
    """Names of the checks that did not pass, in grader order."""
    return [name for name, check in grade.get("checks", {}).items() if not check.get("pass")]
