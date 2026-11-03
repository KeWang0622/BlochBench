"""Tests for mrab pair (both arms, add-on in one, started together, isolated, scanned) and mrab run --addon PACKAGE.

The agent is a fake command (tests/toy.py) that answers correctly only when skills are installed in its workspace.
Tests that need the per-arm sandbox are skipped where the kernel does not allow it (CI allows it).
Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import textwrap
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from addon_fixtures import make_addon
from test_cli import RUN_JSON_KEYS
from toy import Toy, isolation_mode, run_cli, sandbox_available

from mragentbench import addon as addons
from mragentbench import isolation
from mragentbench.common import MrabError
from mragentbench.grading import grade_workspace
from mragentbench.runner import collect_results

SANDBOX = sandbox_available()

# A base-arm agent that searches the folders given as arguments for skills (as a curious agent would search around),
# copies the first one it finds into its workspace, and answers correctly if it found any.
SNOOP_AGENT = textwrap.dedent("""
    import json, os, shutil, sys
    from pathlib import Path
    work = Path.cwd()
    sys.stdin.read()
    found = []
    for root in map(Path, sys.argv[1:]):
        if root.is_dir():
            found += [str(p) for p in root.rglob("SKILL.md") if work not in p.parents]
    own = sorted(str(p) for p in work.glob(".agents/skills/*/SKILL.md"))
    if found and not own:
        shutil.copyfile(found[0], work / "notes.md")
    (work / "answer.txt").write_text("42\\n" if (own or found) else "41\\n")
    (work / "solve.py").write_text("print(42)\\n")
    home = Path(os.environ["HOME"])
    (home / "written-by-agent.txt").write_text("x")
    print(json.dumps({"type": "snoop", "found": found, "own": own,
                      "listing": [sorted(os.listdir(r)) if os.path.isdir(r) else None for r in sys.argv[1:]],
                      "mrab_env": sorted(k for k in os.environ if k.startswith("MRAB_"))}))
""")


def trace_start(path) -> dict:
    return json.loads(path.read_text().splitlines()[0])


class PairTest(unittest.TestCase):
    def setUp(self) -> None:
        self.toy = Toy()
        self.toy.fetch()
        self.addon = make_addon(self.toy.root)
        self.base_dir = self.toy.runs / "cmd-m1" / "toy-r1" / "run1"
        self.addon_dir = self.toy.runs / "cmd-m1+demo@1.0" / "toy-r1" / "run1"

    def pair(self, *extra: str, agent: str = "cmd", cmd: str | None = None, **env: str) -> tuple[int, str, str]:
        argv = ["pair", "toy-r1", "--agent", agent, "--model", "m1", "--addon", str(self.addon)]
        argv += ["--cmd", cmd or self.toy.agent_cmd(), "--isolation", isolation_mode(), *extra]
        with self.toy.active(**env):
            return run_cli(argv)

    def test_pair_runs_both_arms_with_the_addon_in_one(self) -> None:
        code, out, err = self.pair()
        self.assertEqual(code, 0, err)
        base, addon, summary = (json.loads(line) for line in out.splitlines())
        self.assertEqual((base["config"], base["verified"]), ("cmd-m1", False))
        self.assertEqual((addon["config"], addon["verified"]), ("cmd-m1+demo@1.0", True))
        self.assertEqual(
            (summary["addon_intact"], summary["isolated"], summary["baseline_clean"]), (True, SANDBOX, SANDBOX)
        )
        self.assertLess(summary["start_skew_s"], 1.0)

        base_work, addon_work = self.base_dir / "work", self.addon_dir / "work"
        self.assertFalse((base_work / ".agents").exists())
        self.assertFalse((base_work / "AGENTS.md").exists())
        self.assertTrue((addon_work / ".agents" / "skills" / "demo-skill" / "SKILL.md").is_file())
        self.assertEqual((addon_work / "AGENTS.md").read_text(), (self.addon / "AGENTS.md").read_text())
        starts = [trace_start(d / "trace.jsonl") for d in (self.base_dir, self.addon_dir)]
        self.assertEqual(starts[0]["skills"], [])
        self.assertEqual(starts[1]["skills"], [".agents/skills/demo-skill/SKILL.md"])
        self.assertLess(abs(starts[0]["started"] - starts[1]["started"]), 1.0)
        for start in starts:  # neutral working folders: outside the runs folder, naming neither arm nor add-on
            cwd = Path(start["cwd"])
            self.assertEqual(cwd.parent.parent, self.toy.stage)
            self.assertNotIn("demo", str(cwd))
            self.assertNotIn(str(self.toy.runs), str(cwd))
            self.assertEqual(start["mrab_env"], [])
        self.assertNotEqual(starts[0]["cwd"], starts[1]["cwd"])
        self.assertEqual(list(self.toy.stage.iterdir()), [])  # staging folders removed after the results moved

        pair = json.loads((self.base_dir / "pair.json").read_text())
        self.assertEqual(pair, json.loads((self.addon_dir / "pair.json").read_text()))
        self.assertEqual(pair["format"], "mragentbench-pair/2")
        report = addons.validate_addon(self.addon)
        self.assertEqual(pair["addon_manifest"]["content_sha256"], report.content_sha256)
        self.assertEqual(pair["arms"]["base"]["path"], "cmd-m1/toy-r1/run1")
        self.assertEqual(pair["arms"]["addon"]["path"], "cmd-m1+demo@1.0/toy-r1/run1")
        self.assertEqual(pair["addon_install"]["skills_dir"], ".agents/skills")
        self.assertEqual(
            pair["addon_check"],
            dict(intact=True, changed=[], added=[], removed=[], pointer_intact=True, source_unchanged=True),
        )
        self.assertEqual(pair["isolation"]["isolated"], SANDBOX)
        self.assertEqual(
            pair["contamination"],
            dict(
                base_workspace_context=[],
                base_files_matching_addon=[],
                base_trace_mentions=[],
                addon_trace_mentions=[],
                instance_modified=False,
                clean=True,
            ),
        )
        self.assertEqual(pair["instance_check"], dict(before="ok", after=dict(ok=True, mismatches=[])))
        self.assertEqual((pair["host_skills"], pair["host_instructions"], pair["baseline_clean"]), ([], [], SANDBOX))
        records = [json.loads((d / "run.json").read_text()) for d in (self.base_dir, self.addon_dir)]
        for record, start in zip(records, starts, strict=True):
            self.assertEqual(list(record)[: len(RUN_JSON_KEYS)], RUN_JSON_KEYS)
            self.assertEqual(record["pair"], pair["pair"])
            self.assertEqual(record["workdir_during_run"], start["cwd"])
            self.assertEqual(record["argv_template"], json.loads(self.toy.agent_cmd()))
            self.assertEqual((record["interrupted"], record["graded"]), (False, True))
        self.assertIsNone(records[0]["addon"])
        self.assertEqual(records[1]["addon"], str(self.addon))
        self.assertNotIn("addon_manifest", records[0])
        self.assertEqual(records[1]["addon_manifest"]["name"], "demo")
        self.assertEqual(records[1]["addon_pointer"], True)
        self.assertEqual((records[0]["usage"]["output_tokens"], records[1]["usage"]["output_tokens"]), (50, 60))
        self.assertTrue((self.base_dir / "started.json").is_file())

    def test_detects_changes_to_the_installed_addon(self) -> None:
        code, out, err = self.pair(FAKE_TAMPER="1")
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out.splitlines()[2])["addon_intact"])
        self.assertIn("warning: the installed add-on changed", err)
        check = json.loads((self.addon_dir / "run.json").read_text())["addon_check"]
        self.assertEqual((check["intact"], check["changed"]), (False, ["demo-skill/SKILL.md"]))

    def test_refuses_host_level_skills_unless_allowed(self) -> None:
        (self.toy.home / ".agents" / "skills" / "other-skill").mkdir(parents=True)
        code, _, err = self.pair()
        self.assertEqual(code, 1)
        self.assertIn("baseline would not be clean", err)
        self.assertIn("container", err)
        self.assertIn("--allow-host-context", err)
        self.assertFalse(self.toy.runs.exists())
        code, out, err = self.pair("--allow-host-context")
        self.assertEqual(code, 0, err)
        self.assertFalse(json.loads(out.splitlines()[2])["baseline_clean"])
        self.assertIn("warning: the baseline is not clean", err)
        self.assertIn("host context allowed", err)
        pair = json.loads((self.base_dir / "pair.json").read_text())
        self.assertEqual(
            pair["host_skills"], [{"path": str(self.toy.home / ".agents" / "skills"), "entries": ["other-skill"]}]
        )
        record = json.loads((self.base_dir / "run.json").read_text())
        self.assertEqual((record["baseline_clean"], record["host_skills"]), (False, pair["host_skills"]))
        self.assertEqual(self.pair("--allow-host-skills", "--run", "2")[0], 0)  # the earlier name of the flag

    def test_refuses_claude_commands_and_agents(self) -> None:
        for sub in ("commands", "agents"):
            with self.subTest(sub):
                folder = self.toy.home / ".claude" / sub
                (folder / "x.md").parent.mkdir(parents=True, exist_ok=True)
                (folder / "x.md").write_text("use tool X\n")
                code, _, err = self.pair()
                self.assertEqual(code, 1)
                self.assertIn(f"{folder} (1 entries: x.md)", err)
                (folder / "x.md").unlink()

    def test_refuses_instruction_files_plugins_and_repositories(self) -> None:
        cases = {
            "instruction files": self.toy.home / ".codex" / "AGENTS.md",
            "claude user memory": self.toy.home / ".claude" / "CLAUDE.md",
            "project file above the staging folder": self.toy.root / "AGENTS.md",
            "claude project file above the staging folder": self.toy.root / ".claude" / "CLAUDE.md",
        }
        for label, path in cases.items():
            with self.subTest(label):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("Always use tool X.\n")
                code, _, err = self.pair()
                self.assertEqual(code, 1)
                self.assertIn(f"instruction files:\n  {path}\n", err)
                path.unlink()
        self.assertFalse(self.toy.runs.exists())
        (self.toy.root / "AGENTS.md").write_text("")  # empty files are not read by the hosts
        plugins = self.toy.home / ".claude" / "plugins" / "installed_plugins.json"
        plugins.parent.mkdir(parents=True)
        plugins.write_text(json.dumps({"version": 2, "plugins": {"aip@market": [{"scope": "user"}]}}))
        code, _, err = self.pair()
        self.assertEqual(code, 1)
        self.assertIn(f"{plugins} (1 entries: aip@market)", err)
        plugins.unlink()
        (self.toy.root / ".git").mkdir()
        for extra in ((), ("--allow-host-context",)):  # runs, data and staging inside a repository are always refused
            code, _, err = self.pair(*extra)
            self.assertEqual(code, 1)
            self.assertIn(f"is inside the Git repository {self.toy.root}", err)
        self.assertFalse(self.toy.runs.exists())

    def test_installed_scripts_keep_their_mode(self) -> None:
        script = self.addon / "skills" / "demo-skill" / "scripts" / "check.sh"
        script.parent.mkdir()
        script.write_text("#!/bin/sh\necho ok\n")
        script.chmod(0o755)
        self.assertEqual(self.pair()[0], 0)
        installed = self.addon_dir / "work" / ".agents" / "skills" / "demo-skill" / "scripts" / "check.sh"
        self.assertTrue(os.access(installed, os.X_OK))

    def test_ignores_codex_system_skills(self) -> None:
        (self.toy.home / ".codex" / "skills" / ".system" / "builtin").mkdir(parents=True)
        self.assertEqual(self.pair()[0], 0)

    def test_claude_layout(self) -> None:
        code, out, err = self.pair(agent="claude")
        self.assertEqual(code, 0, err)
        work = self.toy.runs / "claude-m1+demo@1.0" / "toy-r1" / "run1" / "work"
        self.assertTrue((work / ".claude" / "skills" / "demo-skill" / "SKILL.md").is_file())
        self.assertTrue((work / "CLAUDE.md").is_file())
        self.assertFalse((work / "AGENTS.md").exists())
        self.assertEqual(json.loads(out.splitlines()[1])["verified"], True)

    def test_without_agents_md_is_its_own_configuration(self) -> None:
        self.assertEqual(self.pair("--no-agents-md")[0], 0)
        folder = self.toy.runs / "cmd-m1+demo@1.0,no-agents-md" / "toy-r1" / "run1"
        self.assertFalse((folder / "work" / "AGENTS.md").exists())
        pair = json.loads((folder / "pair.json").read_text())
        self.assertIsNone(pair["addon_install"]["pointer"])
        self.assertIs(pair["addon_pointer"], False)
        record = json.loads((folder / "run.json").read_text())
        self.assertIs(record["addon_pointer"], False)
        self.assertEqual(self.pair("--run", "2")[0], 0)
        with_pointer = json.loads((self.toy.runs / "cmd-m1+demo@1.0" / "toy-r1" / "run2" / "run.json").read_text())
        self.assertNotEqual(with_pointer["addon_installed_sha256"], record["addon_installed_sha256"])
        self.assertEqual(with_pointer["addon_manifest"], record["addon_manifest"])

    def test_refuses_unsupported_host_invalid_addon_and_existing_runs(self) -> None:
        self.addon = make_addon(self.toy.root, folder_name="claude-only", hosts=["claude"])
        code, _, err = self.pair(agent="codex")
        self.assertEqual((code, err), (1, "the add-on declares hosts claude; it does not support codex\n"))
        self.addon = make_addon(self.toy.root, folder_name="broken", hosts=[])
        code, _, err = self.pair()
        self.assertEqual(code, 1)
        self.assertIn("invalid add-on", err)
        self.assertFalse(self.toy.runs.exists())
        self.addon = make_addon(self.toy.root, folder_name="fine")
        self.assertEqual(self.pair()[0], 0)
        code, _, err = self.pair()
        self.assertEqual((code, err), (1, f"{self.base_dir} exists; choose another --run\n"))

    def test_refuses_a_changed_instance(self) -> None:
        (self.toy.data / "toy-r1" / "private" / "grade_toy.py").write_text("print('always pass')\n")
        code, _, err = self.pair()
        self.assertEqual(code, 1)
        self.assertIn("differs from its frozen manifest (private/grade_toy.py)", err)
        self.assertFalse(self.toy.runs.exists())

    @unittest.skipUnless(SANDBOX, "the per-arm sandbox is not available here")
    def test_refuses_an_agent_file_the_sandbox_hides(self) -> None:
        script = self.toy.root / "agent.py"  # under the temporary folder, which the sandbox hides
        script.write_text("print('hi')\n")
        code, _, err = self.pair(cmd=json.dumps([sys.executable, str(script)]))
        self.assertEqual(code, 1)
        self.assertIn(f"the agent command uses {script}", err)
        self.assertFalse((self.toy.runs / "cmd-m1").exists())

    def test_refuses_sandbox_when_unavailable(self) -> None:
        with mock.patch.object(isolation, "probe_sandbox", return_value="the sandbox is not available here (test)"):
            code, _, err = self.pair("--isolation", "sandbox")
        self.assertEqual(code, 1)
        self.assertIn("per-arm isolation is required but the sandbox is not available here (test)", err)
        self.assertIn("--isolation none", err)

    def test_timeout_applies_to_both_arms(self) -> None:
        code, out, _ = self.pair("--cap", "1", FAKE_SLEEP="20")
        self.assertEqual(code, 0)
        base, addon, _ = (json.loads(line) for line in out.splitlines())
        self.assertTrue(base["timed_out"] and addon["timed_out"])
        self.assertFalse(base["verified"] or addon["verified"])
        pair = json.loads((self.base_dir / "pair.json").read_text())
        ends = [
            datetime.fromisoformat(pair["arms"][a]["finished_at"].replace("Z", "+00:00")) for a in ("base", "addon")
        ]
        self.assertLess(abs((ends[0] - ends[1]).total_seconds()), 2)


class RepositoryGuardTest(unittest.TestCase):
    """Agents under evaluation must never work inside a clone (it holds AGENTS.md and families/)."""

    def setUp(self) -> None:
        self.toy = Toy()
        self.toy.fetch()
        self.repo = self.toy.root / "clone"
        (self.repo / ".git").mkdir(parents=True)

    def test_run_pair_and_prepare_refuse_folders_inside_a_repository(self) -> None:
        addon = make_addon(self.toy.root)
        run = ["run", "toy-r1", "--agent", "cmd", "--model", "m1", "--cmd", self.toy.agent_cmd()]
        pair = [
            "pair",
            "toy-r1",
            "--agent",
            "cmd",
            "--model",
            "m1",
            "--addon",
            str(addon),
            "--cmd",
            self.toy.agent_cmd(),
        ]
        cases = {
            "runs": (dict(MRAB_RUNS=str(self.repo / "runs")), "the runs folder (MRAB_RUNS)"),
            "staging": (dict(MRAB_WORK=str(self.repo)), "MRAB_WORK"),
        }
        for label, (env, expected) in cases.items():
            for argv in (run, pair):
                with self.subTest(label, command=argv[0]), self.toy.active(**env):
                    code, _, err = run_cli(argv)
                    self.assertEqual(code, 1)
                    self.assertIn(f"{expected} ", err)
                    self.assertIn(f"is inside the Git repository {self.repo}", err)
        shutil.copytree(self.toy.data, self.repo / "data")
        for argv in (run, pair, ["prepare", "toy-r1", str(self.toy.root / "w")]):
            with self.subTest("data", command=argv[0]), self.toy.active(MRAB_DATA=str(self.repo / "data")):
                code, _, err = run_cli(argv)
                self.assertEqual(code, 1)
                self.assertIn("the data folder (MRAB_DATA)", err)
        with self.toy.active():
            code, _, err = run_cli(["prepare", "toy-r1", str(self.repo / "w")])
        self.assertEqual(code, 1)
        self.assertIn(f"the workspace {self.repo / 'w'} is inside the Git repository {self.repo}", err)
        self.assertFalse((self.repo / "w").exists())

    def test_defaults_are_outside_the_clone(self) -> None:
        from mragentbench.data import data_dir
        from mragentbench.runner import runs_dir

        with self.toy.active():
            for name in ("MRAB_DATA", "MRAB_RUNS"):
                os.environ.pop(name)
            self.assertEqual(data_dir(), (self.toy.home / "mragentbench" / "data").resolve())
            self.assertEqual(runs_dir(), (self.toy.home / "mragentbench" / "runs").resolve())


class CrossArmTest(unittest.TestCase):
    """An agent in the base arm that looks for the other arm's skills (review finding: cross-arm isolation)."""

    def setUp(self) -> None:
        self.toy = Toy()
        self.toy.fetch()
        self.addon = make_addon(self.toy.root)
        # the folders searched; the listing in the trace is by position, so the trace names none of them
        roots = [str(p) for p in (self.toy.stage, self.toy.runs, self.toy.data, self.addon, self.toy.root)]
        self.snoop = json.dumps([sys.executable, "-c", SNOOP_AGENT, *roots])
        self.base_dir = self.toy.runs / "cmd-m1" / "toy-r1" / "run1"

    def pair(self, *extra: str) -> tuple[int, str, str]:
        argv = ["pair", "toy-r1", "--agent", "cmd", "--model", "m1", "--addon", str(self.addon), "--cmd", self.snoop]
        with self.toy.active():
            return run_cli([*argv, *extra])

    @unittest.skipUnless(SANDBOX, "the per-arm sandbox is not available here")
    def test_sandbox_keeps_the_base_arm_away_from_the_addon(self) -> None:
        code, out, err = self.pair()
        self.assertEqual(code, 0, err)
        base, addon, summary = (json.loads(line) for line in out.splitlines())
        self.assertEqual((base["verified"], addon["verified"]), (False, True))
        self.assertEqual((summary["isolated"], summary["baseline_clean"]), (True, True))
        snoop = trace_start(self.base_dir / "trace.jsonl")
        self.assertEqual(snoop["found"], [])
        self.assertEqual(snoop["mrab_env"], [])
        listing = snoop["listing"]
        for position in (1, 2, 3):  # runs, data, add-on source: empty, or gone with a hidden parent folder
            self.assertIn(listing[position], (None, []), position)
        self.assertFalse((self.toy.home / "written-by-agent.txt").exists())  # the home folder view is private
        pair = json.loads((self.base_dir / "pair.json").read_text())
        self.assertTrue(pair["contamination"]["clean"])

    def test_without_isolation_snooping_is_detected_and_compare_refuses(self) -> None:
        code, out, err = self.pair("--isolation", "none")
        self.assertEqual(code, 0, err)
        base, _, summary = (json.loads(line) for line in out.splitlines())
        self.assertTrue(base["verified"])  # the base arm used the add-on arm's skill
        self.assertEqual((summary["isolated"], summary["baseline_clean"]), (False, False))
        self.assertIn("not isolated", err)
        pair = json.loads((self.base_dir / "pair.json").read_text())
        found = pair["contamination"]
        self.assertEqual(found["base_files_matching_addon"], ["notes.md"])
        self.assertIn("add-on arm's workspace path", found["base_trace_mentions"])
        self.assertIn("add-on source folder", found["base_trace_mentions"])
        self.assertFalse(found["clean"])
        self.assertEqual(pair["isolation"]["mode"], "none")
        with self.toy.active():
            code, _, err = run_cli(["compare", str(self.toy.runs), "--base", "cmd-m1", "--addon", "cmd-m1+demo@1.0"])
            self.assertEqual(code, 1)
            self.assertIn("pairs without enforced isolation or with a baseline that is not clean", err)
            self.assertIn("toy-r1/run1: base arm not isolated", err)
            self.assertIn("base_files_matching_addon", err)
            code, out, err = run_cli(
                ["compare", str(self.toy.runs), "--base", "cmd-m1", "--addon", "cmd-m1+demo@1.0", "--allow-unisolated"]
            )
        self.assertEqual(code, 0, err)
        self.assertIn("warning: 3 problem(s) with isolation or baseline cleanliness (--allow-unisolated)", out)

    def test_changes_to_the_instance_are_detected(self) -> None:
        target = self.toy.data / "toy-r1" / "private" / "grade_toy.py"
        writer = textwrap.dedent(f"""
            import sys
            from pathlib import Path
            sys.stdin.read()
            target = Path({str(target)!r})
            if target.exists():
                target.write_text(target.read_text() + "# changed by the agent\\n")
        """)
        argv = ["pair", "toy-r1", "--agent", "cmd", "--model", "m1", "--addon", str(self.addon)]
        argv += ["--cmd", json.dumps([sys.executable, "-c", writer]), "--isolation", "none"]
        with self.toy.active():
            self.assertEqual(run_cli(argv)[0], 0)
        pair = json.loads((self.base_dir / "pair.json").read_text())
        self.assertEqual(pair["instance_check"]["after"], dict(ok=False, mismatches=["private/grade_toy.py"]))
        self.assertTrue(pair["contamination"]["instance_modified"])
        self.assertFalse(pair["baseline_clean"])


class GradingIntegrityTest(unittest.TestCase):
    """A grade.json placed by an agent must never be read (review finding: grade into a fresh folder)."""

    def test_planted_grade_is_never_read(self) -> None:
        toy = Toy()
        toy.fetch()
        (toy.data / "toy-r1" / "private" / "grade_toy.py").write_text("raise SystemExit(1)\n")  # writes no grade
        work = toy.root / "w"
        work.mkdir()
        out = toy.root / "out"
        out.mkdir()
        (out / "grade.json").write_text(json.dumps({"all_automated_checks_pass": True, "checks": {}}))
        instance = dict(toy.entry, family="z-toy")
        with toy.active():
            with self.assertRaises(MrabError):  # an output folder that already holds files is refused
                grade_workspace(instance, work, out)
            grade = grade_workspace(instance, work, toy.root / "fresh-out")
        self.assertFalse(grade["all_automated_checks_pass"])

    def test_files_planted_in_the_run_folder_are_set_aside(self) -> None:
        toy = Toy()
        stage, run_dir = toy.root / "stage1", toy.root / "run1"
        (stage / "work").mkdir(parents=True)
        (stage / "trace.jsonl").write_text("{}\n")
        (run_dir / "grade").mkdir(parents=True)
        (run_dir / "started.json").write_text("{}")
        (run_dir / "grade" / "grade.json").write_text('{"all_automated_checks_pass": true}')
        self.assertEqual(collect_results(stage, run_dir), ["grade"])
        self.assertTrue((run_dir / "unexpected" / "grade" / "grade.json").is_file())
        self.assertFalse((run_dir / "grade").exists())
        self.assertTrue((run_dir / "work").is_dir() and (run_dir / "trace.jsonl").is_file())


CHILD = """
import sys
from pathlib import Path
sys.path[:0] = [{tree!r}]
from mragentbench import catalog, cli
catalog.FAMILIES_DIR = Path({families!r})
cli.main(sys.argv[1:])
"""


def processes_with(marker: str, agents_only: bool = False) -> list[int]:
    """Processes whose command line contains marker; with agents_only, only the agents (python -c ... marker)."""
    pids = []
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit() and int(proc.name) != os.getpid():
            try:
                argv = (proc / "cmdline").read_bytes().decode(errors="replace").split("\0")
            except OSError:
                continue
            if any(marker in part for part in argv) and (not agents_only or argv[1:2] == ["-c"]):
                pids.append(int(proc.name))
    return pids


def wait_for(predicate, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.2)
    return predicate()


@unittest.skipUnless(sys.platform.startswith("linux"), "uses /proc and the parent-death signal")
class InterruptTest(unittest.TestCase):
    """Every started run counts: signals stop both agents and record both runs (review finding 3)."""

    def setUp(self) -> None:
        self.toy = Toy()
        self.toy.fetch()
        self.addon = make_addon(self.toy.root)
        self.marker = f"agent-marker-{self.toy.root.name}"
        child = self.toy.root / "child.py"
        tree = str(Path(__file__).resolve().parents[1])
        child.write_text(CHILD.format(tree=tree, families=str(self.toy.families)))
        env = {k: v for k, v in os.environ.items() if k not in ("CODEX_HOME", "CLAUDE_CONFIG_DIR")}
        env.update(
            MRAB_DATA=str(self.toy.data),
            MRAB_RUNS=str(self.toy.runs),
            MRAB_WORK=str(self.toy.stage),
            HOME=str(self.toy.home),
            FAKE_SLEEP="30",
        )
        argv = [sys.executable, str(child), "pair", "toy-r1", "--agent", "cmd", "--model", "m1"]
        argv += ["--addon", str(self.addon), "--cmd", self.toy.agent_cmd(self.marker), "--isolation", isolation_mode()]
        self.proc = subprocess.Popen(
            argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
        )
        self.assertTrue(wait_for(lambda: len(processes_with(self.marker, True)) >= 2), "the agents did not start")

    def tearDown(self) -> None:
        for pid in processes_with(self.marker):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.communicate()

    def compare(self, *extra: str) -> tuple[int, str, str]:
        with self.toy.active():
            return run_cli(["compare", str(self.toy.runs), "--base", "cmd-m1", "--addon", "cmd-m1+demo@1.0", *extra])

    def check_interrupted(self, sig: signal.Signals) -> None:
        _, err = self.proc.communicate(timeout=30)
        self.assertEqual(self.proc.returncode, 128 + sig, err)
        self.assertIn(f"stopped by {sig.name}", err)
        self.assertTrue(wait_for(lambda: not processes_with(self.marker), 5), "agents still running")
        for cfg in ("cmd-m1", "cmd-m1+demo@1.0"):
            record = json.loads((self.toy.runs / cfg / "toy-r1" / "run1" / "run.json").read_text())
            self.assertEqual(
                (record["interrupted"], record["interrupted_by"], record["verified"]), (True, sig.name, False)
            )
            self.assertFalse(record["graded"])
        extra = () if SANDBOX else ("--allow-unisolated",)
        code, out, err = self.compare(*extra)
        self.assertEqual(code, 0, err)
        self.assertIn("warning: 2 interrupted run(s) counted as failures", out)
        self.assertIn("verified 0/1", out)

    def test_sigterm_to_mrab(self) -> None:
        self.proc.send_signal(signal.SIGTERM)
        self.check_interrupted(signal.SIGTERM)

    def test_sighup_to_the_process_group(self) -> None:
        os.killpg(self.proc.pid, signal.SIGHUP)  # a terminal hangup reaches mrab's whole process group
        self.check_interrupted(signal.SIGHUP)

    def test_sigkill_leaves_incomplete_runs_and_no_agents(self) -> None:
        self.proc.kill()
        self.proc.communicate(timeout=30)
        self.assertTrue(wait_for(lambda: not processes_with(self.marker), 5), "agents outlived mrab")
        for cfg in ("cmd-m1", "cmd-m1+demo@1.0"):
            folder = self.toy.runs / cfg / "toy-r1" / "run1"
            self.assertTrue((folder / "started.json").is_file())
            self.assertFalse((folder / "run.json").exists())
        code, _, err = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("started runs without run.json", err)
        self.assertIn("cmd-m1/toy-r1/run1", err)
        code, out, err = self.compare("--allow-incomplete")
        self.assertEqual(code, 0, err)
        self.assertIn("verified 0/1", out)
        self.assertIn("warning: 2 started run(s) without run.json counted as failures", out)


class StopFlagTest(unittest.TestCase):
    def test_signal_while_agents_start_stops_both(self) -> None:
        from mragentbench import runner

        class Proc:  # a process registered after the handler ran (an agent still starting) is killed at once
            pid, killed = -1, False

        with mock.patch.object(runner, "kill_group", side_effect=lambda p: setattr(p, "killed", True)):
            with runner.stop_on_signals():
                runner.kill_all()
                late = Proc()
                runner.register(late)
                runner.unregister(late)
            self.assertTrue(late.killed)
            after = Proc()
            runner.register(after)  # the flag is cleared when the guarded section ends
            runner.unregister(after)
            self.assertFalse(after.killed)


class RunWithPackageTest(unittest.TestCase):
    def test_run_installs_each_skill(self) -> None:
        toy = Toy()
        toy.fetch()
        addon = make_addon(toy.root)
        with toy.active():
            code, out, err = run_cli(
                ["run", "toy-r1", "--agent", "cmd", "--model", "m1", "--addon", str(addon), "--cmd", toy.agent_cmd()]
            )
        self.assertEqual(code, 0, err)
        self.assertEqual((json.loads(out)["config"], json.loads(out)["verified"]), ("cmd-m1+demo@1.0", True))
        base = toy.runs / "cmd-m1+demo@1.0" / "toy-r1" / "run1"
        self.assertTrue((base / "work" / ".agents" / "skills" / "demo-skill" / "SKILL.md").is_file())
        record = json.loads((base / "run.json").read_text())
        self.assertEqual(list(record)[: len(RUN_JSON_KEYS)], RUN_JSON_KEYS)
        self.assertTrue(record["addon_check"]["intact"])
        self.assertEqual(record["addon_manifest"]["content_sha256"], addons.validate_addon(addon).content_sha256)
        self.assertEqual(record["isolation"]["isolated"], SANDBOX)
        self.assertIs(record["addon_pointer"], True)

    def test_run_refuses_unsupported_host_and_missing_folder(self) -> None:
        toy = Toy()
        toy.fetch()
        claude_only = make_addon(toy.root, hosts=["claude"])
        for addon, expected in (
            (claude_only, "the add-on declares hosts claude; it does not support codex\n"),
            (toy.root / "nope", f"--addon {toy.root / 'nope'}: not a folder\n"),
        ):
            with self.subTest(addon=addon.name), toy.active():
                argv = ["run", "toy-r1", "--agent", "codex", "--model", "m1", "--addon", str(addon)]
                code, _, err = run_cli([*argv, "--cmd", toy.agent_cmd()])
            self.assertEqual((code, err), (1, expected))
        self.assertFalse(toy.runs.exists())


class PairThenCompareTest(unittest.TestCase):
    def test_three_pairs(self) -> None:
        toy = Toy()
        toy.fetch()
        addon = make_addon(toy.root)
        for k, env in ((1, {}), (2, {}), (3, {"FAKE_ALWAYS": "1"})):
            with toy.active(**env):
                argv = ["pair", "toy-r1", "--agent", "cmd", "--model", "m1", "--addon", str(addon), "--run", str(k)]
                code, _, err = run_cli([*argv, "--cmd", toy.agent_cmd(), "--isolation", isolation_mode()])
            self.assertEqual(code, 0, err)
        out_json = toy.root / "compare.json"
        argv = ["compare", str(toy.runs), "--base", "cmd-m1", "--addon", "cmd-m1+demo@1.0", "--json", str(out_json)]
        with toy.active():
            code, out, err = run_cli(argv + ([] if SANDBOX else ["--allow-unisolated"]))
        self.assertEqual(code, 0, err)
        self.assertIn(
            "instances 1 (families 1): add-on better on 1, worse on 0, tied on 0; mean difference +66.7 pp", out
        )
        self.assertIn("primary test, instance level: exact sign-flip permutation P 1; exact sign test P 1\n", out)
        self.assertIn(
            "secondary, run level (treats repeated runs of an instance as independent): pairs 3: base 1 (33.3%), "
            "with add-on 3 (100.0%), add-on only 2, base only 0, exact McNemar P 0.5\n   toy      1 -> 3 of 3\n",
            out,
        )
        self.assertIn("pairs started together (mrab pair): 3 of 3\n", out)
        self.assertIn("add-on demo 1.0 (content sha256 ", out)
        result = json.loads(out_json.read_text())
        self.assertEqual((result["pairs"], result["started_together"], result["addon_modified"]), (3, 3, []))
        self.assertEqual(result["n_instances"], 1)
        self.assertAlmostEqual(result["tokens"]["ratio"], 1060 / 1050)


if __name__ == "__main__":
    unittest.main()
