"""Agent runs: adapters for Codex, Claude Code and any command-line agent; usage from traces; run records.

A run lives in RUNS/<config>/<instance>/run<k>/ with started.json (written when the run starts), work/ (the agent's
workspace), trace.jsonl (agent stdout), agent-stderr.txt, grade/ (grader output) and run.json (the run record).

The agent itself works in a neutral staging folder outside the runs folder (mragentbench.isolation), with the
environment variables of mrab (MRAB_*) removed, and, where available, inside the per-arm sandbox. Its results are moved
into the run folder after it stops, and the grader writes into a fresh folder created after that.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from . import __version__
from . import addon as addons
from . import isolation as iso
from .common import MrabError, RunInterrupted, utc_now, write_json
from .data import data_dir, prepare_workspace, verify_instance
from .grading import failed_checks, grade_workspace, is_verified

ADAPTERS: dict[str, list[str]] = {
    "codex": [
        "codex",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "-s",
        "workspace-write",
        "-C",
        "{workdir}",
        "-m",
        "{model}",
        "-",
    ],
    "claude": [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        "{model}",
        "--dangerously-skip-permissions",
    ],
}
# How a built-in adapter sets the reasoning effort (--effort); Codex reads it as a configuration override.
EFFORT_ARGS: dict[str, list[str]] = {"codex": ["-c", "model_reasoning_effort={effort}"]}
# Where each host looks for project skills inside its working directory.
ADDON_DIRS: dict[str, str] = addons.SKILL_DIRS
AGENTS = ("codex", "claude", "cmd")
# Entries that mrab itself puts in a run folder; anything else found there before grading is set aside.
RUN_FOLDER_ENTRIES = ("started.json", "work", "trace.jsonl", "agent-stderr.txt", "grade", "run.json", "pair.json")


def runs_dir() -> Path:
    """Directory holding run results (MRAB_RUNS, default ~/mragentbench/runs, outside any clone)."""
    return Path(os.environ.get("MRAB_RUNS") or Path.home() / "mragentbench" / "runs").resolve()


def agent_template(agent: str, cmd: str | None, effort: str | None = None) -> list[str]:
    """The argv template of an agent: the JSON list given with --cmd, or the built-in adapter (with --effort)."""
    template = json.loads(cmd) if cmd else ADAPTERS.get(agent)
    if not template:
        raise MrabError("use --cmd with a JSON list for agent cmd")
    if not isinstance(template, list) or not all(isinstance(part, str) and part for part in template):
        raise MrabError("--cmd must be a JSON list of non-empty strings")
    template = list(template)
    uses_effort = any("{effort}" in part for part in template)
    if effort:
        if cmd and not uses_effort:
            raise MrabError("--effort needs the placeholder {effort} in the --cmd template")
        if not cmd:
            if agent not in EFFORT_ARGS:
                raise MrabError(f"the {agent} adapter has no effort setting; use --agent cmd with {{effort}} in --cmd")
            at = template.index("-") if "-" in template else len(template)
            template[at:at] = EFFORT_ARGS[agent]
    elif uses_effort:
        raise MrabError("the --cmd template uses {effort}; pass --effort")
    return template


def build_argv(template: list[str], work: Path, model: str, effort: str | None = None) -> list[str]:
    """Fill the placeholders {workdir}, {model}, {prompt} (path of TASK.txt) and {effort} of an argv template."""
    return [
        part.replace("{workdir}", str(work))
        .replace("{model}", model)
        .replace("{prompt}", str(work / "TASK.txt"))
        .replace("{effort}", effort or "")
        for part in template
    ]


def require_executable(name: str) -> None:
    """Refuse an agent command that cannot be found, before any folder is created."""
    found = os.access(name, os.X_OK) if os.sep in name else shutil.which(name)
    if not found:
        raise MrabError(f"could not start the agent ({name}): not found or not executable")


def agent_version(name: str) -> str | None:
    """First line printed by '<agent> --version' (for cmd agents, of the command's first word), or None."""
    try:
        proc = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=30, env=agent_env())
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (proc.stdout.strip() or proc.stderr.strip()).splitlines()
    return lines[0].strip()[:200] if proc.returncode == 0 and lines else None


def agent_env() -> dict[str, str]:
    """The agent's environment: mrab's, without MRAB_* (paths of the runs and data folders, the API token)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("MRAB_")}


def usage_from_trace(path: Path) -> dict[str, float]:
    """Sum every numeric "*token*" field of every "usage" object in a JSON-lines trace.

    Lines that are not JSON are skipped. Codex and Claude Code both report usage this way.
    """
    totals: dict[str, float] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            usage = node.get("usage")
            if isinstance(usage, dict):
                for key, value in usage.items():
                    if isinstance(value, int | float) and "token" in key:
                        totals[key] = totals.get(key, 0) + value
            for value in node.values():
                if isinstance(value, dict | list):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    if not path.exists():
        return totals
    for line in path.read_text(errors="ignore").splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        walk(event)
    return totals


def run_tokens(record: dict) -> float:
    """Input plus output tokens of a run record (cached input is part of input), as mrab collect reports them."""
    usage = record.get("usage") or {}
    return sum(v for k, v in usage.items() if k in ("input_tokens", "output_tokens"))


# --- processes --------------------------------------------------------------------------------------------------

_LIVE: set[subprocess.Popen] = set()
_LIVE_LOCK = threading.Lock()
# Set by the signal handlers: a process registered afterwards (an agent that was still starting) is killed at once.
_STOPPING = threading.Event()


def register(proc: subprocess.Popen) -> None:
    with _LIVE_LOCK:
        _LIVE.add(proc)
        stopping = _STOPPING.is_set()
    if stopping:
        kill_group(proc)


def unregister(proc: subprocess.Popen) -> None:
    with _LIVE_LOCK:
        _LIVE.discard(proc)


def kill_group(proc: subprocess.Popen) -> None:
    """SIGKILL a process started with its own process group, and everything left in that group.

    Also used after the leader has exited: the kernel does not reuse a process id while a group of that id still has
    members, and once it has none, killpg fails harmlessly.
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def kill_all() -> None:
    """Stop every agent and grader that mrab is running, and any that start later (used by the signal handlers)."""
    with _LIVE_LOCK:
        _STOPPING.set()
        live = list(_LIVE)
    for proc in live:
        kill_group(proc)


@contextlib.contextmanager
def stop_on_signals() -> Iterator[dict[str, int | None]]:
    """While active, SIGTERM, SIGHUP and SIGINT stop every agent and grader; the signal number is kept in state."""
    state: dict[str, int | None] = {"signum": None}
    if threading.current_thread() is not threading.main_thread():
        yield state
        return

    def handler(signum: int, frame: object) -> None:
        state["signum"] = signum
        kill_all()

    _STOPPING.clear()
    previous = {sig: signal.signal(sig, handler) for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
    try:
        yield state
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)
        _STOPPING.clear()


@dataclass
class AgentResult:
    """How an agent process ended."""

    returncode: int | None
    timed_out: bool
    wall_s: float
    started_at: str
    finished_at: str


class AgentProcess:
    """An agent running in its workspace: TASK.txt on stdin, stdout to trace.jsonl, stderr to agent-stderr.txt.

    The logs are written into log_dir (the staging folder, outside the workspace). The agent starts through the launcher
    (mragentbench/sandbox.py) in its own process group, so a timeout, an interrupt or mrab's death stops every process
    it started.
    """

    def __init__(
        self,
        argv: list[str],
        work: Path,
        log_dir: Path,
        spec: dict[str, Any] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.argv, self.work, self.log_dir = argv, work, log_dir
        self.spec = spec or {"sandbox": False}
        self.env = agent_env() if env is None else env
        self.proc: subprocess.Popen | None = None
        self._files: list[IO] = []
        self._t0 = 0.0
        self.started_at = ""

    def start(self) -> None:
        stdout = open(self.log_dir / "trace.jsonl", "w")
        stderr = open(self.log_dir / "agent-stderr.txt", "w")
        stdin = open(self.work / "TASK.txt")
        self._files = [stdout, stderr, stdin]
        self.started_at, self._t0 = utc_now(), time.time()
        try:
            self.proc = subprocess.Popen(
                iso.launcher_argv(self.spec, self.argv),
                cwd=self.work,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=self.env,
                start_new_session=True,
            )
        except OSError as e:
            self._close()
            raise MrabError(f"could not start the agent ({self.argv[0]}): {e}") from e
        register(self.proc)

    def kill(self) -> None:
        """Kill the agent and everything it started."""
        if self.proc:
            kill_group(self.proc)
            self.proc.wait()

    def wait(self, cap_s: float) -> AgentResult:
        """Wait until the agent exits or cap_s seconds after it started, then kill it."""
        assert self.proc is not None, "start() first"
        timed_out = False
        try:
            self.proc.wait(timeout=max(0.0, self._t0 + cap_s - time.time()))
        except subprocess.TimeoutExpired:
            self.kill()
            timed_out = True
        except BaseException:
            self.kill()
            raise
        finally:
            self._close()
            unregister(self.proc)
        kill_group(self.proc)  # the agent exited; stop anything it left running in its group
        return AgentResult(
            returncode=self.proc.returncode,
            timed_out=timed_out,
            wall_s=time.time() - self._t0,
            started_at=self.started_at,
            finished_at=utc_now(),
        )

    def _close(self) -> None:
        for f in self._files:
            f.close()
        self._files = []


def run_together(agents: list[AgentProcess], cap_s: float) -> list[AgentResult]:
    """Start the agents at the same moment (one thread each, released by a barrier) and wait for all of them."""
    barrier = threading.Barrier(len(agents))
    results: list[AgentResult | None] = [None] * len(agents)
    errors: list[BaseException] = []

    def target(i: int) -> None:
        try:
            barrier.wait()
            agents[i].start()
            results[i] = agents[i].wait(cap_s)
        except BaseException as e:  # reported in the main thread
            errors.append(e)
            barrier.abort()
            for a in agents:
                a.kill()

    threads = [threading.Thread(target=target, args=(i,), daemon=True) for i in range(len(agents))]
    for t in threads:
        t.start()
    try:
        for t in threads:
            t.join()
    except BaseException:
        for a in agents:
            a.kill()
        raise
    if errors:
        error = next((e for e in errors if not isinstance(e, threading.BrokenBarrierError)), errors[0])
        raise error
    return [r for r in results if r is not None]


def run_agent(argv: list[str], work: Path, run_dir: Path, cap_s: float) -> AgentResult:
    """Run one agent, unconfined, to completion or to its time cap (logs in run_dir)."""
    return run_together([AgentProcess(argv, work, run_dir)], cap_s)[0]


# --- run folders ---------------------------------------------------------------------------------------------------


def start_run_folder(run_dir: Path, **info: object) -> None:
    """Create the run folder and started.json when the run starts, so a run that never finishes is still visible."""
    try:
        run_dir.mkdir(parents=True)
    except FileExistsError:
        raise MrabError(f"{run_dir} exists; choose another --run") from None
    write_json(run_dir / "started.json", dict(format="mragentbench-started/1", **info))


def collect_results(stage: Path, run_dir: Path) -> list[str]:
    """Move the workspace and logs from the staging folder into the run folder; returns entries set aside.

    Anything in the run folder that mrab did not write (for example a grade/ folder planted by an agent) is moved into
    run_dir/unexpected/ and listed, so it can never be read as the grader's output.
    """
    unexpected = sorted(p.name for p in run_dir.iterdir() if p.name != "started.json")
    if unexpected:
        aside = run_dir / "unexpected"
        aside.mkdir()
        for name in unexpected:
            if name != "unexpected":
                shutil.move(str(run_dir / name), str(aside / name))
    for name in ("work", "trace.jsonl", "agent-stderr.txt"):
        if (stage / name).exists():
            shutil.move(str(stage / name), str(run_dir / name))
    return unexpected


def check_instance(instance: dict) -> dict[str, Any]:
    """Verify the instance against its frozen manifest; returns {"ok": bool, "mismatches": [...]}."""
    result = verify_instance(instance)
    return dict(ok=result.ok, mismatches=result.mismatches)


def verify_before(instance: dict) -> None:
    """Refuse to start when the instance's files (prompt, inputs, grader, hidden data) differ from the manifest."""
    check = check_instance(instance)
    if not check["ok"]:
        raise MrabError(
            f"instance {instance['instance']} differs from its frozen manifest ({', '.join(check['mismatches'][:5])}); "
            "fetch it again"
        )


def run_record(
    instance: dict,
    *,
    config: str,
    agent: str,
    model: str,
    addon: str | None,
    run: int,
    argv: list[str],
    cap_s: float,
    result: AgentResult,
    usage: dict,
    grade: dict | None,
) -> dict:
    """The run.json record. Keys and their order are part of the output format; more keys follow these."""
    return dict(
        instance=instance["instance"],
        family=instance["family"],
        domain=instance["domain"],
        config=config,
        agent=agent,
        model=model,
        addon=addon,
        run=run,
        argv=argv,
        cap_s=cap_s,
        timed_out=result.timed_out,
        returncode=result.returncode,
        wall_s=round(result.wall_s, 1),
        usage=usage,
        verified=is_verified(grade) if grade else None,
        failed_checks=failed_checks(grade) if grade else None,
    )


def run_summary(record: dict) -> dict:
    """The line printed after a run."""
    return {k: record[k] for k in ("instance", "config", "run", "verified", "wall_s", "timed_out")}


def settings_record(
    instance: dict, template: list[str], effort: str | None, version: str | None, work: Path
) -> dict[str, Any]:
    """Settings that must match between the arms of a pair (mrab compare checks them)."""
    return dict(
        argv_template=template,
        effort=effort,
        agent_version=version,
        mrab_version=__version__,
        manifest_sha256=instance.get("manifest_sha256"),
        workdir_during_run=str(work),
    )


def outcome_record(result: AgentResult, interrupted: int | None, graded: bool) -> dict[str, Any]:
    """How the run ended: interrupted runs are failures (verified false) and are not graded."""
    out: dict[str, Any] = dict(started_at=result.started_at, finished_at=result.finished_at, graded=graded)
    out["interrupted"] = interrupted is not None
    if interrupted is not None:
        out["interrupted_by"] = signal.Signals(interrupted).name
    return out


def interrupted_message(signum: int, run_dirs: list[Path]) -> str:
    return (
        f"stopped by {signal.Signals(signum).name}; the agents were killed and the run(s) recorded as interrupted "
        f"(failures): {', '.join(map(str, run_dirs))}"
    )


def run_instance(
    instance: dict,
    agent: str,
    model: str,
    *,
    config: str | None = None,
    run: int = 1,
    addon: str | None = None,
    cmd: str | None = None,
    cap: int | None = None,
    python: str | None = None,
    grade: bool = True,
    effort: str | None = None,
    isolation: str = "auto",
    agents_md: bool = True,
) -> dict:
    """Run an agent on one instance in a fresh workspace, grade it and write run.json; returns the record.

    addon is either a plain folder, copied as one entry into the host's skills folder (the original behaviour), or
    an add-on package with addon.json, whose skills are installed one folder per skill (see mragentbench.addon).
    """
    template = agent_template(agent, cmd, effort)
    if addon and not Path(addon).is_dir():
        raise MrabError(f"--addon {addon}: not a folder")
    package = addons.load_valid_addon(addon) if addon and addons.is_package(addon) else None
    if package:
        addons.check_host(package.manifest or {}, agent)
    pointer = bool(package and package.has_pointer and agents_md)
    if config:
        cfg = config
    elif package:
        cfg = f"{agent}-{model}+{addons.addon_label(package.manifest)}" + addons.pointer_suffix(package, agents_md)
    else:
        cfg = f"{agent}-{model}" + (f"+{Path(addon).name}" if addon else "")
    base = runs_dir() / cfg / instance["instance"] / f"run{run}"
    if base.exists():
        raise MrabError(f"{base} exists; choose another --run")
    root = iso.work_root()
    iso.check_outside_repositories(runs=runs_dir(), data=data_dir())
    iso.check_work_root(root, runs_dir(), data_dir())
    verify_before(instance)
    require_executable(template[0])
    runs_dir().mkdir(parents=True, exist_ok=True)  # exists before the agent starts, so it is hidden
    hidden = iso.hidden_paths(runs_dir(), data_dir(), root, [Path(addon)] if addon else [])
    isolation_used = iso.resolve_isolation(isolation, root, hidden)
    if isolation_used.isolated:
        iso.check_command_visible(template, hidden)
    version = agent_version(template[0])
    cap_s = cap or instance["cap_s"]

    stage = iso.new_stage(root)
    try:
        work = prepare_workspace(instance, stage / "work")
        install = None
        if package:
            install = addons.install_addon(package, work, agent, agents_md=agents_md)
        elif addon:
            shutil.copytree(addon, work / ADDON_DIRS[agent] / Path(addon).name)
        argv = build_argv(template, work, model, effort)
        start_run_folder(base, instance=instance["instance"], config=cfg, run=run, started_at=utc_now())
        process = AgentProcess(argv, work, stage, isolation_used.spec(stage))
        with stop_on_signals() as state:
            try:
                result = run_together([process], cap_s)[0]
            except MrabError:
                shutil.rmtree(base, ignore_errors=True)  # the agent never started
                raise
            interrupted = state["signum"]
            instance_after = check_instance(instance)
            check = addons.check_install(work, install) if install else None
            unexpected = collect_results(stage, base)
            graded: dict = {}
            if grade and interrupted is None:
                graded = grade_workspace(instance, base / "work", base / "grade", python)
            interrupted = state["signum"]
    finally:
        iso.remove_stage(stage)
    record = run_record(
        instance,
        config=cfg,
        agent=agent,
        model=model,
        addon=addon,
        run=run,
        argv=argv,
        cap_s=cap_s,
        result=result,
        usage=usage_from_trace(base / "trace.jsonl"),
        grade=graded,
    )
    if interrupted is not None:
        record.update(verified=False, failed_checks=None)
    record.update(settings_record(instance, template, effort, version, work))
    record.update(outcome_record(result, interrupted, bool(graded)))
    isolation_record = isolation_used.record()
    if isolation_used.isolated and iso.sandbox_failed(base / "agent-stderr.txt"):
        isolation_record.update(isolated=False, reason="the sandbox could not be set up for this run")
    record.update(isolation=isolation_record, instance_check=dict(before="ok", after=instance_after))
    if unexpected:
        record["unexpected_files"] = unexpected
    if package and install is not None:
        record["addon_manifest"] = addons.manifest_record(package)
        record["addon_pointer"] = pointer if package.has_pointer else None
        record["addon_installed_sha256"] = addons.installed_digest(install)
        record["addon_check"] = check
    write_json(base / "run.json", record)
    if interrupted is not None:
        raise RunInterrupted(interrupted, interrupted_message(interrupted, [base]))
    return record
