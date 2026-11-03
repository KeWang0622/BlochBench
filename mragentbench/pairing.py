"""Paired add-on runs: the same instance, model and settings, with and without an add-on, started together.

mrab pair checks the add-on, the host and the instance, prepares two fresh workspaces in neutral staging folders
(random names under MRAB_WORK, outside the runs folder, naming neither the arm nor the add-on), installs the add-on
only in one, starts both agents at the same moment (each in its own sandbox where available), and after they stop:
verifies the instance again, checks that the installed add-on was not changed, scans the base workspace for skills or
instruction files and both traces for the other arm's paths and the add-on's name, moves the results into the run
folders, grades both arms, and writes run.json for both arms plus pair.json.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__
from . import addon as addons
from . import isolation as iso
from .common import MrabError, RunInterrupted, sha256_file, utc_now, write_json
from .data import data_dir, prepare_workspace
from .grading import grade_workspace
from .runner import (
    AgentProcess,
    AgentResult,
    agent_template,
    agent_version,
    build_argv,
    check_instance,
    collect_results,
    interrupted_message,
    outcome_record,
    require_executable,
    run_record,
    run_together,
    runs_dir,
    settings_record,
    start_run_folder,
    stop_on_signals,
    usage_from_trace,
    verify_before,
)

ARMS = ("base", "addon")
# Files that would give the baseline arm skills or instructions.
_ARM_CONTEXT = (".agents/skills", ".claude/skills", "AGENTS.md", "CLAUDE.md")
# Names that give an agent skills or instructions when found in its workspace.
CONTEXT_FILES = {"AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "CLAUDE.local.md", "SKILL.md"}
CONTEXT_DIRS = {(".agents", "skills"), (".claude", "skills"), (".claude", "commands"), (".claude", "agents")}
MIN_MATCH_BYTES = 64  # smaller files (empty __init__.py and the like) match by chance
MAX_MATCH_BYTES = 1 << 20


def pair_configs(agent: str, model: str, report: addons.AddonReport, agents_md: bool = True) -> tuple[str, str]:
    """Configuration names of the two arms: <agent>-<model> and <agent>-<model>+<name>@<version>[,no-agents-md]."""
    base = f"{agent}-{model}"
    manifest = report.manifest or {}
    return base, f"{base}+{addons.addon_label(manifest)}{addons.pointer_suffix(report, agents_md)}"


@dataclass
class PairPlan:
    """Everything fixed before the agents start."""

    instance: dict
    agent: str
    model: str
    run: int
    package: addons.AddonReport
    addon_path: str
    configs: dict[str, str]
    run_dirs: dict[str, Path]
    host: addons.HostContext
    isolation: iso.Isolation
    root: Path
    template: list[str]
    effort: str | None
    version: str | None
    agents_md: bool
    stages: dict[str, Path] = field(default_factory=dict)


def plan_pair(
    instance: dict,
    agent: str,
    model: str,
    addon_path: str,
    run: int,
    allow_host_context: bool,
    home: Path | None,
    *,
    cmd: str | None = None,
    effort: str | None = None,
    isolation: str = "sandbox",
    agents_md: bool = True,
) -> PairPlan:
    """Check everything that can refuse a pair before any folder is created."""
    template = agent_template(agent, cmd, effort)
    package = addons.load_valid_addon(addon_path)
    manifest = package.manifest or {}
    addons.check_host(manifest, agent)
    public = data_dir() / instance["instance"] / "public"
    present = [rel for rel in _ARM_CONTEXT if (public / rel).exists()]
    if present:
        raise MrabError(f"the public inputs of {instance['instance']} contain {', '.join(present)}; cannot pair")
    root = iso.work_root()
    iso.check_outside_repositories(runs=runs_dir(), data=data_dir())
    iso.check_work_root(root, runs_dir(), data_dir())
    host = addons.find_host_context(home=home, runs_root=root)
    if not host.clean and not allow_host_context:
        raise MrabError(addons.host_context_message(host))
    configs = dict(zip(ARMS, pair_configs(agent, model, package, agents_md), strict=True))
    run_dirs = {arm: runs_dir() / cfg / instance["instance"] / f"run{run}" for arm, cfg in configs.items()}
    for path in run_dirs.values():
        if path.exists():
            raise MrabError(f"{path} exists; choose another --run")
    verify_before(instance)
    require_executable(template[0])
    runs_dir().mkdir(parents=True, exist_ok=True)  # exists before the agent starts, so it is hidden
    hidden = iso.hidden_paths(runs_dir(), data_dir(), root, [Path(addon_path)])
    isolation_used = iso.resolve_isolation(isolation, root, hidden)
    if isolation_used.isolated:
        iso.check_command_visible(template, hidden)
    version = agent_version(template[0])
    return PairPlan(
        instance,
        agent,
        model,
        run,
        package,
        addon_path,
        configs,
        run_dirs,
        host,
        isolation_used,
        root,
        template,
        effort,
        version,
        agents_md,
    )


def scan_workspace(work: Path) -> list[str]:
    """Skill folders and instruction files anywhere in a workspace (relative paths)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(work):
        here = Path(dirpath)
        for name in dirnames:
            if (here.name, name) in CONTEXT_DIRS:
                found.append((here / name).relative_to(work).as_posix() + "/")
        found += [(here / n).relative_to(work).as_posix() for n in filenames if n in CONTEXT_FILES]
    return sorted(found)


def files_matching(work: Path, digests: set[str]) -> list[str]:
    """Files of a workspace whose content equals a file of the add-on (64 bytes to 1 MiB)."""
    found = []
    for dirpath, _, filenames in os.walk(work):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if MIN_MATCH_BYTES <= size <= MAX_MATCH_BYTES and not path.is_symlink() and sha256_file(path) in digests:
                found.append(path.relative_to(work).as_posix())
    return sorted(found)


def mentions(files: list[Path], needles: dict[str, str]) -> list[str]:
    """Labels of the needles found in the given files ({label: text}; names match as whole words)."""
    text = ""
    for path in files:
        try:
            text += path.read_text(errors="ignore") + "\n"
        except OSError:
            continue
    found = []
    for label, needle in needles.items():
        if not needle:
            continue
        pattern = re.escape(needle) if "/" in needle else rf"(?<![\w.-]){re.escape(needle)}(?![\w-])"
        if re.search(pattern, text):
            found.append(label)
    return found


def scan_pair(plan: PairPlan, works: dict[str, Path], instance_after: dict[str, Any]) -> dict[str, Any]:
    """After the agents stop: what of the add-on or the other arm reached an arm, and whether the instance changed."""
    stages, run_dirs = plan.stages, plan.run_dirs
    name = (plan.package.manifest or {}).get("name", "")
    source = str(Path(plan.addon_path).resolve())
    digests = {entry.split()[0] for entry in plan.package.files.values()}
    base_needles = {
        "add-on arm's workspace path": str(stages["addon"]),
        "add-on arm's run folder": str(run_dirs["addon"]),
        "add-on source folder": source,
        f"add-on name {name!r}": name,
    }
    addon_needles = {"base arm's workspace path": str(stages["base"]), "base arm's run folder": str(run_dirs["base"])}
    logs = {arm: [stages[arm] / "trace.jsonl", stages[arm] / "agent-stderr.txt"] for arm in ARMS}
    result = dict(
        base_workspace_context=scan_workspace(works["base"]),
        base_files_matching_addon=files_matching(works["base"], digests),
        base_trace_mentions=mentions(logs["base"], base_needles),
        addon_trace_mentions=mentions(logs["addon"], addon_needles),
        instance_modified=not instance_after["ok"],
    )
    result["clean"] = not any(result.values())
    return result


def pair_record(
    plan: PairPlan,
    pair_id: str,
    cap_s: float,
    results: dict[str, AgentResult],
    records: dict[str, dict],
    install: dict[str, Any],
    check: dict[str, Any],
    isolation: dict[str, Any],
    scan: dict[str, Any],
    instance_after: dict[str, Any],
) -> dict[str, Any]:
    """pair.json: links the two run folders and records the add-on, its check, the isolation and the scans."""
    name = plan.instance["instance"]
    arms = {
        arm: dict(
            config=cfg,
            path=f"{cfg}/{name}/run{plan.run}",
            started_at=results[arm].started_at,
            finished_at=results[arm].finished_at,
            verified=records[arm]["verified"],
            timed_out=results[arm].timed_out,
            interrupted=records[arm]["interrupted"],
        )
        for arm, cfg in plan.configs.items()
    }
    return dict(
        format="mragentbench-pair/2",
        pair=pair_id,
        instance=name,
        family=plan.instance["family"],
        domain=plan.instance["domain"],
        run=plan.run,
        agent=plan.agent,
        model=plan.model,
        cap_s=cap_s,
        effort=plan.effort,
        agent_version=plan.version,
        mrab_version=__version__,
        manifest_sha256=plan.instance.get("manifest_sha256"),
        arms=arms,
        start_skew_s=_seconds_between(results["base"].started_at, results["addon"].started_at),
        addon_source=str(Path(plan.addon_path).resolve()),
        addon_manifest=addons.manifest_record(plan.package),
        addon_pointer=install["pointer"] is not None if plan.package.has_pointer else None,
        addon_install={k: v for k, v in install.items() if k != "installed_sha256"},
        addon_check=check,
        isolation=isolation,
        contamination=scan,
        instance_check=dict(before="ok", after=instance_after),
        **host_record(plan.host, isolation, scan),
    )


def host_record(host: addons.HostContext, isolation: dict[str, Any], scan: dict[str, Any]) -> dict[str, Any]:
    """Host context as stored in pair.json and run.json.

    baseline_clean is true only when nothing outside the workspaces could reach the agents, both arms ran isolated,
    and the scans after the run found nothing.
    """
    return dict(
        host_skills=host.skills,
        host_instructions=host.instructions,
        runs_repository=host.repository,
        baseline_clean=host.clean and bool(isolation["isolated"]) and bool(scan["clean"]),
    )


def _seconds_between(a: str, b: str) -> float:
    from datetime import datetime

    def parse(s: str) -> datetime:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    return round(abs((parse(a) - parse(b)).total_seconds()), 3)


def run_pair(
    instance: dict,
    agent: str,
    model: str,
    addon_path: str,
    *,
    run: int = 1,
    cmd: str | None = None,
    cap: int | None = None,
    python: str | None = None,
    grade: bool = True,
    allow_host_context: bool = False,
    agents_md: bool = True,
    home: Path | None = None,
    effort: str | None = None,
    isolation: str = "sandbox",
) -> dict[str, Any]:
    """Run one pair and return {"pair": pair record, "base": run record, "addon": run record}.

    Both arms get the same instance, agent, model, effort, time cap and environment; only the add-on arm's workspace
    holds the add-on. A SIGTERM, SIGHUP or SIGINT stops both agents; both runs are then recorded as interrupted
    (failures) and RunInterrupted is raised.
    """
    plan = plan_pair(
        instance,
        agent,
        model,
        addon_path,
        run,
        allow_host_context,
        home,
        cmd=cmd,
        effort=effort,
        isolation=isolation,
        agents_md=agents_md,
    )
    cap_s = cap or instance["cap_s"]
    plan.stages = {arm: iso.new_stage(plan.root) for arm in ARMS}
    try:
        works = {arm: prepare_workspace(instance, plan.stages[arm] / "work") for arm in ARMS}
        install = addons.install_addon(plan.package, works["addon"], agent, agents_md=agents_md)
        argvs = {arm: build_argv(plan.template, works[arm], model, effort) for arm in ARMS}
        pair_id = f"{instance['instance']}/run{run}/{utc_now()}"
        for arm in ARMS:
            start_run_folder(
                plan.run_dirs[arm],
                pair=pair_id,
                arm=arm,
                instance=instance["instance"],
                config=plan.configs[arm],
                run=run,
                started_at=utc_now(),
            )
        agents = [
            AgentProcess(argvs[arm], works[arm], plan.stages[arm], plan.isolation.spec(plan.stages[arm]))
            for arm in ARMS
        ]
        with stop_on_signals() as state:
            try:
                results = dict(zip(ARMS, run_together(agents, cap_s), strict=True))
            except MrabError:
                for path in plan.run_dirs.values():
                    shutil.rmtree(path, ignore_errors=True)  # the agents never started
                raise
            interrupted = state["signum"]
            instance_after = check_instance(instance)
            check = addons.check_install(works["addon"], install)
            check["source_unchanged"] = addons.validate_addon(addon_path).content_sha256 == plan.package.content_sha256
            isolation_record = plan.isolation.record()
            if plan.isolation.isolated and any(
                iso.sandbox_failed(plan.stages[arm] / "agent-stderr.txt") for arm in ARMS
            ):
                isolation_record.update(isolated=False, reason="the sandbox could not be set up for this pair")
            scan = scan_pair(plan, works, instance_after)
            unexpected = {arm: collect_results(plan.stages[arm], plan.run_dirs[arm]) for arm in ARMS}
            if unexpected["base"] or unexpected["addon"]:
                scan.update(unexpected_files=unexpected, clean=False)
            grades: dict[str, dict] = {arm: {} for arm in ARMS}
            if grade and interrupted is None:
                for arm in ARMS:
                    grades[arm] = grade_workspace(
                        instance, plan.run_dirs[arm] / "work", plan.run_dirs[arm] / "grade", python
                    )
            interrupted = state["signum"]
    finally:
        for stage in plan.stages.values():
            iso.remove_stage(stage)

    records = {}
    for arm in ARMS:
        run_dir = plan.run_dirs[arm]
        record = run_record(
            instance,
            config=plan.configs[arm],
            agent=agent,
            model=model,
            addon=addon_path if arm == "addon" else None,
            run=run,
            argv=argvs[arm],
            cap_s=cap_s,
            result=results[arm],
            usage=usage_from_trace(run_dir / "trace.jsonl"),
            grade=grades[arm],
        )
        if interrupted is not None:
            record.update(verified=False, failed_checks=None)
        record.update(settings_record(instance, plan.template, effort, plan.version, works[arm]))
        record.update(outcome_record(results[arm], interrupted, bool(grades[arm])))
        record.update(pair=pair_id, arm=arm, isolation=isolation_record, contamination=scan)
        record.update(instance_check=dict(before="ok", after=instance_after))
        record.update(host_record(plan.host, isolation_record, scan))
        if arm == "addon":
            record.update(
                addon_manifest=addons.manifest_record(plan.package),
                addon_pointer=install["pointer"] is not None if plan.package.has_pointer else None,
                addon_installed_sha256=addons.installed_digest(install),
                addon_check=check,
            )
        records[arm] = record
    pair = pair_record(plan, pair_id, cap_s, results, records, install, check, isolation_record, scan, instance_after)
    for arm in ARMS:
        write_json(plan.run_dirs[arm] / "run.json", records[arm])
        write_json(plan.run_dirs[arm] / "pair.json", pair)
    if interrupted is not None:
        raise RunInterrupted(interrupted, interrupted_message(interrupted, list(plan.run_dirs.values())))
    return dict(pair=pair, base=records["base"], addon=records["addon"])
