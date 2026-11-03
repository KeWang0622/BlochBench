"""Isolation of agent runs: neutral staging folders, the per-arm sandbox and the checks around it.

Every run (mrab run, and each arm of mrab pair) works in a fresh staging folder with a random name under MRAB_WORK
(default: the system temporary folder), never inside the runs folder: the path an agent sees names neither the
configuration nor the add-on. Results are moved into RUNS/<config>/<instance>/run<k>/ after the agent stops.

On Linux, when the kernel allows unprivileged user namespaces, the agent runs in the sandbox of mragentbench/sandbox.py:
it sees only its own workspace, with the runs folder, the instance data, every staging folder, the add-on source and
the temporary folders replaced by empty ones, and a private copy-on-write view of the home folder. Elsewhere, or with
--isolation none, agents run unconfined and the run is recorded with isolated: false.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import MrabError

SANDBOX_SCRIPT = Path(__file__).with_name("sandbox.py")
SETUP_FAILED = 125
SETUP_FAILED_MARK = "mrab-sandbox: setup failed"
# Shared scratch folders that would let one arm's agent leave files for the other.
SHARED_SCRATCH = ("/tmp", "/var/tmp", "/dev/shm")
MODES = ("sandbox", "none")


def work_root() -> Path:
    """Folder that holds the staging folders (MRAB_WORK, default the system temporary folder)."""
    return Path(os.environ.get("MRAB_WORK") or tempfile.gettempdir()).resolve()


def is_within(path: Path, folder: Path) -> bool:
    """True when path is folder or lies below it (both resolved)."""
    path, folder = path.resolve(), folder.resolve()
    return path == folder or folder in path.parents


def find_repository(path: Path) -> Path | None:
    """The nearest folder at or above path that holds .git (a Git repository or worktree), or None."""
    path = path.resolve()
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return folder
    return None


def check_work_root(root: Path, runs: Path, data: Path) -> None:
    """Refuse staging locations from which an agent could reach results, data or repository instructions."""
    if not root.is_dir():
        raise MrabError(f"MRAB_WORK {root} is not a folder")
    for name, folder in (("runs folder", runs), ("data folder", data)):
        if is_within(root, folder):
            raise MrabError(f"MRAB_WORK {root} must not be inside the {name} {folder}")
    repo = find_repository(root)
    if repo:
        raise MrabError(
            f"MRAB_WORK {root} is inside the Git repository {repo}; agents there would read its AGENTS.md and project "
            "settings. Set MRAB_WORK to a folder outside any repository."
        )


def check_outside_repositories(**folders: Path) -> None:
    """Refuse folders that lie inside a Git repository (for mrab run, prepare and pair).

    An agent working inside a clone of this repository would read its AGENTS.md (contributor instructions that point
    to the graders) and could reach families/; results and data inside a clone are one step away from that.
    """
    names = {"runs": "the runs folder (MRAB_RUNS)", "data": "the data folder (MRAB_DATA)", "workdir": "the workspace"}
    for key, folder in folders.items():
        repo = find_repository(folder)
        if repo:
            raise MrabError(
                f"{names.get(key, key)} {folder.resolve()} is inside the Git repository {repo}; agents there would "
                "read its AGENTS.md and project settings. Use a folder outside any repository (the defaults are "
                "~/mragentbench/data and ~/mragentbench/runs)."
            )


def new_stage(root: Path) -> Path:
    """A fresh staging folder with a random name: STAGE/work is the workspace, STAGE/home holds the home overlay."""
    stage = Path(tempfile.mkdtemp(prefix="mrab-", dir=root)).resolve()
    (stage / "home" / "upper").mkdir(parents=True)
    (stage / "home" / "work").mkdir()
    return stage


def remove_stage(stage: Path) -> None:
    """Remove a staging folder after its results were moved out (overlay work folders may be read-only)."""
    for dirpath, dirnames, _ in os.walk(stage):
        for name in dirnames:
            try:
                os.chmod(Path(dirpath) / name, 0o700)
            except OSError:
                pass
    shutil.rmtree(stage, ignore_errors=True)


def hidden_paths(runs: Path, data: Path, root: Path, extra: list[Path] | None = None) -> list[str]:
    """Folders replaced by empty ones inside the sandbox (existing folders only, never / or the home folder)."""
    home = Path.home().resolve()
    candidates = [root, runs, data, *(extra or []), *map(Path, SHARED_SCRATCH)]
    if os.environ.get("TMPDIR"):
        candidates.append(Path(os.environ["TMPDIR"]))
    hidden: list[str] = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not resolved.is_dir() or str(resolved) in hidden:
            continue
        if resolved == Path("/") or resolved == home:
            raise MrabError(f"{resolved} cannot be hidden from the agents (it is / or the home folder)")
        hidden.append(str(resolved))
    return hidden


@dataclass
class Isolation:
    """How a run's agent is confined."""

    mode: str
    hidden: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def isolated(self) -> bool:
        return self.mode == "sandbox"

    def spec(self, stage: Path) -> dict[str, Any]:
        """The launcher specification for one run in its staging folder."""
        if not self.isolated:
            return {"sandbox": False}
        return {
            "sandbox": True,
            "work": str(stage / "work"),
            "hide": self.hidden,
            "home": str(Path.home().resolve()),
            "home_upper": str(stage / "home"),
        }

    def record(self) -> dict[str, Any]:
        return dict(
            mode=self.mode,
            isolated=self.isolated,
            hidden=self.hidden,
            home="private copy-on-write view" if self.isolated else "shared",
            reason=self.reason,
        )


def check_command_visible(template: list[str], hidden: list[str]) -> None:
    """Refuse an agent command that names a file (a program or script) in a folder the sandbox hides.

    Such an agent could not start inside the sandbox, and both arms would fail. Folders named in the command are not
    checked: an agent may be given paths it cannot reach.
    """
    program = shutil.which(template[0]) if template and os.sep not in template[0] else None
    for part in ([program] if program else []) + template:
        if "{" in part or not part.startswith("/"):
            continue
        path = Path(part)
        for folder in hidden:
            if path.is_file() and is_within(path, Path(folder)):
                raise MrabError(
                    f"the agent command uses {part}, which is inside {folder}; the sandbox hides that folder from the "
                    "agent. Put the agent's files elsewhere (or use --isolation none)."
                )


def launcher_argv(spec: dict[str, Any], argv: list[str]) -> list[str]:
    """argv that starts ARGV through the launcher (parent-death signal, and the sandbox when spec asks for it)."""
    return [sys.executable, "-I", str(SANDBOX_SCRIPT), json.dumps(spec), "--", *argv]


_PROBES: dict[tuple[str, str, tuple[str, ...]], str] = {}


def probe_sandbox(root: Path, hidden: list[str]) -> str:
    """Check that the sandbox works here and enforces what it promises; returns "" or the reason it does not."""
    if not sys.platform.startswith("linux"):
        return "the sandbox needs Linux"
    if os.environ.get("MRAB_SANDBOX") == "0":
        return "the sandbox is turned off (MRAB_SANDBOX=0)"
    home = Path.home().resolve()
    key = (str(root), str(home), tuple(hidden))
    if key in _PROBES:
        return _PROBES[key]
    stage = new_stage(root)
    other = new_stage(root)
    try:
        (stage / "work").mkdir()
        (stage / "work" / "mine").write_text("x")
        (other / "secret").write_text("x")
        marker = f".mrab-probe-{stage.name}"
        check = (
            f'test -f mine && test ! -e "{other}/secret" && touch "{home}/{marker}" && test -f "{home}/{marker}" '
            f'&& touch written && test "$(pwd)" = "{stage / "work"}"'
        )
        isolation = Isolation("sandbox", hidden=sorted(set(hidden) | {str(root)}))
        argv = launcher_argv(isolation.spec(stage), ["/bin/sh", "-c", check])
        try:
            proc = subprocess.run(argv, cwd=stage / "work", capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            reason = f"the sandbox could not start: {e}"
        else:
            if proc.returncode != 0:
                detail = (proc.stderr.strip().splitlines() or [f"exit status {proc.returncode}"])[-1]
                reason = f"the sandbox is not available here ({detail})"
            elif (home / marker).exists():
                (home / marker).unlink()
                reason = "the sandbox did not keep the home folder private"
            elif not (stage / "work" / "written").exists():
                reason = "the sandbox did not give write access to the workspace"
            else:
                reason = ""
    finally:
        remove_stage(stage)
        remove_stage(other)
    _PROBES[key] = reason
    return reason


def resolve_isolation(requested: str, root: Path, hidden: list[str]) -> Isolation:
    """sandbox (refuse if unavailable), none, or auto (sandbox when available, otherwise none)."""
    if requested == "none":
        return Isolation("none", reason="--isolation none")
    reason = probe_sandbox(root, hidden)
    if not reason:
        return Isolation("sandbox", hidden=hidden)
    if requested == "sandbox":
        raise MrabError(
            f"per-arm isolation is required but {reason}. On Linux, allow unprivileged user namespaces "
            "(for example sysctl kernel.apparmor_restrict_unprivileged_userns=0 on Ubuntu) or run inside a container "
            "that allows them; or pass --isolation none (recorded as isolated: false; such pairs are refused by "
            "mrab compare unless --allow-unisolated)."
        )
    return Isolation("none", reason=reason)


def sandbox_failed(stderr_file: Path) -> bool:
    """True when the launcher reported that the sandbox could not be set up for this run."""
    try:
        return SETUP_FAILED_MARK in stderr_file.read_text(errors="ignore")
    except OSError:
        return False
