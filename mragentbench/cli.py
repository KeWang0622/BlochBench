"""mrab: command-line tool for MRI Agent Bench (standard library only).

  mrab list                                   families, domains, caps, instances
  mrab fetch INSTANCE [--url BASE | --from-dir DIR]   get an instance package into the data directory
  mrab verify INSTANCE                        check an instance against its FROZEN-SHA256 manifest
  mrab prepare INSTANCE WORKDIR               create an agent workspace (public inputs + TASK.txt only)
  mrab run INSTANCE --agent codex|claude|cmd --model M [--config NAME] [--run K] [--addon DIR] [--cmd TEMPLATE]
  mrab grade INSTANCE WORKDIR [--out DIR] [--python PY]
  mrab collect [RUNS_DIR]                     write a runs CSV for scoring
  mrab score RUNS.csv | --paired PAIRS.csv     verified completion, pass^k, cost; paired add-on analysis
  mrab addon validate|hash DIR | schema       check an add-on package, print its content hash or the schema
  mrab pair INSTANCE --agent A --model M --addon DIR [--run K]   one run with and one without the add-on, together
                                              (docs/EVALUATE-YOUR-SKILLS.md)
  mrab compare [RUNS_DIR] --base CONFIG --addon CONFIG [--json OUT]   paired comparison of two configurations
  mrab bundle | submit | status               hosted grading (docs/API.md)

Environment: MRAB_DATA (default ~/mragentbench/data), MRAB_RUNS (default ~/mragentbench/runs), MRAB_WORK (staging
folders, default the temporary folder), MRAB_DATA_URL (base URL of instance packages),
MRAB_API_URL and MRAB_TOKEN (hosted grading).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import addon as addons
from . import client, scoring
from .catalog import families, family_line, get_instance
from .common import MrabError, RunInterrupted
from .compare import RUN_FOLDER, compare_configs, compare_lines, write_pairs_csv
from .data import data_dir, fetch_instance, prepare_workspace, verify_instance
from .grading import failed_checks, grade_workspace, is_verified
from .isolation import check_outside_repositories
from .pairing import run_pair
from .runner import AGENTS, run_instance, run_summary, run_tokens, runs_dir


def cmd_list(args: argparse.Namespace) -> None:
    for family, entries in families().items():
        print(family_line(family, entries, legacy=args.legacy))


def cmd_fetch(args: argparse.Namespace) -> None:
    path, present = fetch_instance(get_instance(args.instance), args.url, args.from_dir)
    print("already present" if present else "fetched", path)


def cmd_verify(args: argparse.Namespace) -> None:
    result = verify_instance(get_instance(args.instance))
    for rel in result.mismatches:
        print("MISMATCH", rel)
    print(f"{result.files - len(result.mismatches)}/{result.files} files match the frozen manifest")
    sys.exit(0 if result.ok else 1)


def cmd_prepare(args: argparse.Namespace) -> None:
    instance = get_instance(args.instance)
    check_outside_repositories(workdir=Path(args.workdir), data=data_dir())
    print("prepared", prepare_workspace(instance, args.workdir))


def cmd_grade(args: argparse.Namespace) -> None:
    instance = get_instance(args.instance)
    out = args.out or Path(args.workdir).resolve().parent / "grade"
    grade = grade_workspace(instance, args.workdir, out, args.python)
    print(
        json.dumps(
            {"instance": instance["instance"], "verified": is_verified(grade), "failed_checks": failed_checks(grade)}
        )
    )


def cmd_run(args: argparse.Namespace) -> None:
    record = run_instance(
        get_instance(args.instance),
        args.agent,
        args.model,
        config=args.config,
        run=args.run,
        addon=args.addon,
        cmd=args.cmd,
        cap=args.cap,
        python=args.python,
        grade=not args.no_grade,
        effort=args.effort,
        isolation=args.isolation,
        agents_md=not args.no_agents_md,
    )
    print(json.dumps(run_summary(record)))


def cmd_collect(args: argparse.Namespace) -> None:
    root = Path(args.runs_dir or runs_dir())
    writer = csv.writer(sys.stdout)
    writer.writerow(["family", "instance", "domain", "config", "run", "passed", "tokens", "wall_s"])
    for path in sorted(root.glob("*/*/run*/run.json")):
        if not RUN_FOLDER.fullmatch(path.parent.name):
            print(f"warning: {path.parent} is not named run<k>; left out", file=sys.stderr)
            continue
        r = json.loads(path.read_text())
        writer.writerow(
            [
                r["family"],
                r["instance"],
                r["domain"],
                r["config"],
                r["run"],
                int(bool(r.get("verified"))),
                run_tokens(r),
                r["wall_s"],
            ]
        )


def cmd_score(args: argparse.Namespace) -> None:
    if not (args.csv or args.paired):
        raise MrabError("give a runs CSV (mrab collect) or --paired PAIRS.csv")
    if args.cluster == "family" and not args.paired:
        raise MrabError("--cluster family requires --paired PAIRS.csv")
    if args.paired:
        with open(args.paired) as f:
            scoring.paired(list(csv.DictReader(f)), cluster=args.cluster)
    else:
        with open(args.csv) as f:
            scoring.single(list(csv.DictReader(f)))


def cmd_addon_validate(args: argparse.Namespace) -> None:
    report = addons.validate_addon(args.dir, max_bytes=args.max_bytes)
    if args.json:
        print(json.dumps(report.as_dict(), indent=1))
        sys.exit(0 if report.ok else 1)
    manifest = report.manifest if isinstance(report.manifest, dict) else {}
    print(
        f"add-on {manifest.get('name', '?')} {manifest.get('version', '?')}: {len(report.skills)} skill(s), "
        f"{len(report.files)} files, {report.total_bytes / 1e3:.1f} kB"
    )
    print(f"  path       {report.root}")
    print(f"  skills     {', '.join(report.skills) or '-'}")
    print(f"  hosts      {', '.join(manifest.get('hosts') or []) or '-'}")
    print(f"  AGENTS.md  {'yes' if report.has_pointer else 'no'}")
    exposure = manifest.get("exposure") if isinstance(manifest.get("exposure"), dict) else {}
    seen = {True: "yes", False: "no", "partial": "partly"}.get(exposure.get("public_instances_seen"), "?")
    print(
        f"  exposure   public instances seen: {seen}" + (f" ({exposure['details']})" if exposure.get("details") else "")
    )
    if report.not_installed:
        print(f"  ignored    {', '.join(report.not_installed)} (not part of the installed add-on)")
    for warning in report.warnings:
        print("warning:", warning)
    for error in report.errors:
        print("error:", error)
    if report.ok:
        print("content sha256", report.content_sha256)
        print("valid")
    else:
        print(f"invalid: {len(report.errors)} error(s)")
        sys.exit(1)


def cmd_addon_hash(args: argparse.Namespace) -> None:
    print(addons.load_valid_addon(args.dir).content_sha256)


def cmd_addon_schema(args: argparse.Namespace) -> None:
    print(json.dumps(addons.ADDON_SCHEMA, indent=2))


def cmd_pair(args: argparse.Namespace) -> None:
    result = run_pair(
        get_instance(args.instance),
        args.agent,
        args.model,
        args.addon,
        run=args.run,
        cmd=args.cmd,
        cap=args.cap,
        python=args.python,
        grade=not args.no_grade,
        allow_host_context=args.allow_host_context,
        agents_md=not args.no_agents_md,
        effort=args.effort,
        isolation=args.isolation,
    )
    print(json.dumps(run_summary(result["base"])))
    print(json.dumps(run_summary(result["addon"])))
    pair = result["pair"]
    print(
        json.dumps(
            {
                "pair": pair["pair"],
                "start_skew_s": pair["start_skew_s"],
                "addon_intact": pair["addon_check"]["intact"],
                "isolated": pair["isolation"]["isolated"],
                "baseline_clean": pair["baseline_clean"],
            }
        )
    )
    if not pair["addon_check"]["intact"]:
        print("warning: the installed add-on changed during the run; see addon_check in pair.json", file=sys.stderr)
    if not pair["baseline_clean"]:
        found = [k for k, v in pair["contamination"].items() if v and k != "clean"]
        reasons = (["not isolated"] if not pair["isolation"]["isolated"] else []) + found
        if pair["host_skills"] or pair["host_instructions"]:
            reasons.append("host context allowed")
        print(f"warning: the baseline is not clean ({', '.join(reasons)}); see pair.json", file=sys.stderr)


def cmd_compare(args: argparse.Namespace) -> None:
    result = compare_configs(
        Path(args.runs_dir or runs_dir()),
        args.base,
        args.addon,
        allow_incomplete=args.allow_incomplete,
        allow_unpaired=args.allow_unpaired,
        allow_unisolated=args.allow_unisolated,
        cluster=args.cluster,
    )
    for line in compare_lines(result):
        print(line)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1) + "\n")
        print("written", args.json)
    if args.csv:
        write_pairs_csv(result, Path(args.csv))
        print("written", args.csv)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="mrab",
        description="MRI Agent Bench command-line tool",
        epilog="Environment: MRAB_DATA, MRAB_RUNS, MRAB_WORK, MRAB_DATA_URL, MRAB_API_URL, MRAB_TOKEN.",
    )
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("list", help="task IDs, names, time caps and instances")
    p.add_argument("--legacy", action="store_true", help="show the frozen identifiers used in saved run records")
    p.set_defaults(f=cmd_list)

    p = sp.add_parser("fetch", help="get an instance package into the data directory")
    p.add_argument("instance")
    p.add_argument("--url", help="package mirror (default: MRAB_DATA_URL or the public Core release)")
    p.add_argument("--from-dir", help="copy the instance from a local folder")
    p.set_defaults(f=cmd_fetch)

    p = sp.add_parser("verify", help="check an instance against its FROZEN-SHA256 manifest")
    p.add_argument("instance")
    p.set_defaults(f=cmd_verify)

    p = sp.add_parser("prepare", help="create an agent workspace with the public inputs and TASK.txt")
    p.add_argument("instance")
    p.add_argument("workdir")
    p.set_defaults(f=cmd_prepare)

    p = sp.add_parser("run", help="run an agent in a fresh workspace and grade the result")
    p.add_argument("instance")
    p.add_argument("--agent", required=True, choices=list(AGENTS))
    p.add_argument("--model", required=True)
    p.add_argument("--config", help="configuration name (default <agent>-<model>[+<addon>])")
    p.add_argument("--run", type=int, default=1)
    p.add_argument("--addon", help="skills folder, or add-on package with addon.json, for the agent's workspace")
    p.add_argument("--cmd", help='argv template as a JSON list, e.g. ["my-agent", "--cwd", "{workdir}"]')
    p.add_argument("--cap", type=int, help="time cap in seconds (default: the family's cap)")
    p.add_argument("--python", help="Python interpreter for the grader")
    p.add_argument("--no-grade", action="store_true")
    p.add_argument("--effort", help="reasoning effort (built-in codex adapter, or {effort} in --cmd); recorded")
    p.add_argument(
        "--isolation",
        choices=["auto", "sandbox", "none"],
        default="auto",
        help="run the agent in the Linux sandbox (auto: when available); recorded in run.json",
    )
    p.add_argument("--no-agents-md", action="store_true", help="do not install the add-on package's AGENTS.md")
    p.set_defaults(f=cmd_run)

    p = sp.add_parser("grade", help="grade a workspace")
    p.add_argument("instance")
    p.add_argument("workdir")
    p.add_argument("--out")
    p.add_argument("--python")
    p.set_defaults(f=cmd_grade)

    p = sp.add_parser("collect", help="write a runs CSV for scoring")
    p.add_argument("runs_dir", nargs="?")
    p.set_defaults(f=cmd_collect)

    p = sp.add_parser("score", help="verified completion, pass^k and cost; --paired for add-on pairs")
    p.add_argument("csv", nargs="?")
    p.add_argument("--paired")
    p.add_argument(
        "--cluster",
        choices=["instance", "family"],
        default="instance",
        help="independent unit for paired bootstrap and exact tests (default: instance)",
    )
    p.set_defaults(f=cmd_score)

    p = sp.add_parser("addon", help="validate an add-on package and print its content hash")
    asp = p.add_subparsers(dest="addon_cmd", required=True)
    q = asp.add_parser("validate", help="check addon.json, every SKILL.md, links and size")
    q.add_argument("dir")
    q.add_argument("--json", action="store_true", help="print the report as JSON")
    q.add_argument("--max-bytes", type=int, default=addons.MAX_BYTES)
    q.set_defaults(f=cmd_addon_validate)
    q = asp.add_parser("hash", help="print the content hash of a valid add-on")
    q.add_argument("dir")
    q.set_defaults(f=cmd_addon_hash)
    asp.add_parser("schema", help="print the JSON Schema of addon.json").set_defaults(f=cmd_addon_schema)

    p = sp.add_parser("pair", help="run one instance with and without an add-on, started together, and grade both")
    p.add_argument("instance")
    p.add_argument("--agent", required=True, choices=list(AGENTS))
    p.add_argument("--model", required=True)
    p.add_argument("--addon", required=True, help="add-on package (folder with addon.json and skills/)")
    p.add_argument("--run", type=int, default=1)
    p.add_argument("--cmd", help="argv template for --agent cmd (JSON list)")
    p.add_argument("--cap", type=int, help="time cap in seconds (default: the family's cap)")
    p.add_argument("--python", help="Python interpreter for the grader")
    p.add_argument("--no-grade", action="store_true")
    p.add_argument(
        "--no-agents-md",
        action="store_true",
        help="do not install the add-on's AGENTS.md (configuration name gets ,no-agents-md)",
    )
    p.add_argument("--effort", help="reasoning effort (built-in codex adapter, or {effort} in --cmd); recorded")
    p.add_argument(
        "--isolation",
        choices=["sandbox", "none"],
        default="sandbox",
        help="sandbox (default): each arm sees only its own workspace (Linux); none: unconfined, recorded as "
        "isolated: false",
    )
    p.add_argument(
        "--allow-host-context",
        "--allow-host-skills",
        dest="allow_host_context",
        action="store_true",
        help="run even if skills, plugins or instruction files outside the workspaces exist, or the runs folder is "
        "inside a Git repository (recorded; the baseline is then not clean)",
    )
    p.set_defaults(f=cmd_pair)

    p = sp.add_parser("compare", help="paired comparison of a base and an add-on configuration")
    p.add_argument("runs_dir", nargs="?", help="runs folder (default: MRAB_RUNS)")
    p.add_argument("--base", required=True, help="base configuration, e.g. codex-gpt-6")
    p.add_argument("--addon", required=True, help="add-on configuration, e.g. codex-gpt-6+MRFoundry@0.14.0")
    p.add_argument("--json", help="write the full comparison as JSON")
    p.add_argument("--csv", help="write the pairs in the CSV format of mrab score --paired")
    p.set_defaults(f=cmd_compare)
    p.add_argument(
        "--cluster",
        choices=["instance", "family"],
        default="instance",
        help="independent unit for bootstrap and exact tests (default: instance)",
    )
    p.add_argument("--allow-incomplete", action="store_true", help="count started runs without run.json as failures")
    p.add_argument(
        "--allow-unpaired",
        action="store_true",
        help="accept runs not started together by mrab pair, or with settings that were not recorded",
    )
    p.add_argument(
        "--allow-unisolated",
        action="store_true",
        help="accept pairs without enforced isolation or with a baseline that is not clean (listed)",
    )

    client.add_parsers(sp)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.f(args)
    except MrabError as e:
        sys.exit(str(e))
    except RunInterrupted as e:
        print(f"mrab: {e}", file=sys.stderr)
        sys.exit(128 + e.signum)


if __name__ == "__main__":
    main()
