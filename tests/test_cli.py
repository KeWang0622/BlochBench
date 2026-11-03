"""Regression tests for the mrab commands that predate the refactor: list, fetch, verify, prepare, grade, run, collect,
score. Expected outputs were recorded from the single-file cli.py of commit 224b2fa.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from toy import REPO, Toy, run_cli

from mragentbench import data, runner, scoring

RUN_JSON_KEYS = [
    "instance",
    "family",
    "domain",
    "config",
    "agent",
    "model",
    "addon",
    "run",
    "argv",
    "cap_s",
    "timed_out",
    "returncode",
    "wall_s",
    "usage",
    "verified",
    "failed_checks",
]


class CatalogAndDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.toy = Toy()

    def test_list(self) -> None:
        with self.toy.active():
            code, out, _ = run_cli(["list"])
        self.assertEqual((code, out), (0, "z-toy                toy    cap   2 min  instances: toy-r1\n"))

    def test_list_real_catalog(self) -> None:
        code, out, _ = run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("PERF-01", out)
        self.assertIn("pcasl", out)
        self.assertIn("PERF-01-01, PERF-01-02, PERF-01-03, PERF-01-04", out)
        self.assertNotIn("heldout-", out)
        code, out, _ = run_cli(["list", "--legacy"])
        self.assertEqual(code, 0)
        self.assertIn(
            "v7-pcasl             perf   cap  60 min  instances: heldout-v7-pcasl, heldout-v7-pcasl-r2, "
            "heldout-v7-pcasl-r3, heldout-v7-pcasl-r4\n",
            out,
        )

    def test_unknown_instance(self) -> None:
        with self.toy.active():
            code, _, err = run_cli(["fetch", "nope-r1"])
        self.assertEqual((code, err), (1, "unknown instance nope-r1; see mrab list\n"))

    def test_fetch(self) -> None:
        with self.toy.active():
            code, out, _ = run_cli(["fetch", "toy-r1", "--from-dir", str(self.toy.src)])
            self.assertEqual((code, out), (0, f"fetched {self.toy.data / 'toy-r1'}\n"))
            code, out, _ = run_cli(["fetch", "toy-r1", "--from-dir", str(self.toy.src)])
            self.assertEqual(out, f"already present {self.toy.data / 'toy-r1'}\n")

    def test_fetch_uses_release_default_without_network(self) -> None:
        with self.toy.active(), patch.object(data, "DEFAULT_DATA_URL", self.toy.packages.as_uri()):
            code, _, err = run_cli(["fetch", "toy-r1"])
            self.assertEqual((code, err), (0, ""))
            self.assertTrue(data.verify_instance(self.toy.entry).ok)

    def test_fetch_environment_mirror_overrides_release(self) -> None:
        with (
            self.toy.active(MRAB_DATA_URL=self.toy.packages.as_uri()),
            patch.object(data, "DEFAULT_DATA_URL", "file:///nonexistent/release"),
        ):
            self.assertEqual(run_cli(["fetch", "toy-r1"])[0], 0)

    def test_fetch_from_url_checks_the_package(self) -> None:
        with self.toy.active():
            code, out, _ = run_cli(["fetch", "toy-r1", "--url", self.toy.packages.as_uri()])
            self.assertEqual((code, out), (0, f"fetched {self.toy.data / 'toy-r1'}\n"))
            self.assertTrue((self.toy.data / "toy-r1" / "private" / "grade_toy.py").exists())
            self.assertFalse((self.toy.data / "toy-r1.tar").exists())
        bad = dict(self.toy.entry, package_sha256="0" * 64)
        (self.toy.families / "z-toy" / "instances.json").write_text(json.dumps([bad]))
        with self.toy.active(MRAB_DATA=str(self.toy.root / "data2")):
            code, _, err = run_cli(["fetch", "toy-r1", "--url", self.toy.packages.as_uri()])
        self.assertEqual((code, err), (1, "package checksum mismatch\n"))

    def test_verify(self) -> None:
        self.toy.fetch()
        with self.toy.active():
            self.assertEqual(run_cli(["verify", "toy-r1"])[:2], (0, "5/5 files match the frozen manifest\n"))
            with open(self.toy.data / "toy-r1" / "public" / "input.txt", "a") as f:
                f.write("tampered\n")
            code, out, _ = run_cli(["verify", "toy-r1"])
        self.assertEqual((code, out), (1, "MISMATCH public/input.txt\n4/5 files match the frozen manifest\n"))

    def test_verify_needs_matching_manifest(self) -> None:
        self.toy.fetch()
        with open(self.toy.data / "toy-r1" / "FROZEN-SHA256.txt", "a") as f:
            f.write("# extra comment\n")
        with self.toy.active():
            self.assertEqual(run_cli(["verify", "toy-r1"])[2], "manifest hash differs from the catalog\n")

    def test_prepare(self) -> None:
        self.toy.fetch()
        work = self.toy.root / "w"
        with self.toy.active():
            self.assertEqual(run_cli(["prepare", "toy-r1", str(work)])[1], f"prepared {work}\n")
            files = sorted(p.relative_to(work).as_posix() for p in work.rglob("*") if p.is_file())
            self.assertEqual(files, ["TASK.txt", "input.txt", "sub/n.txt", "task.json"])
            self.assertEqual(run_cli(["prepare", "toy-r1", str(work)])[2], f"{work} is not empty\n")

    def test_prepare_needs_fetch(self) -> None:
        with self.toy.active():
            code, _, err = run_cli(["prepare", "toy-r1", str(self.toy.root / "w")])
        self.assertEqual((code, err), (1, f"instance toy-r1 not in {self.toy.data}; run mrab fetch first\n"))

    def test_grade(self) -> None:
        self.toy.fetch()
        work = self.toy.root / "w"
        with self.toy.active():
            run_cli(["prepare", "toy-r1", str(work)])
            out = run_cli(["grade", "toy-r1", str(work)])[1]
            self.assertEqual(
                json.loads(out),
                {
                    "instance": "toy-r1",
                    "verified": False,
                    "failed_checks": ["answer_present", "answer_correct", "entrypoint_reruns"],
                },
            )
            self.assertTrue((self.toy.root / "grade" / "grade.json").exists())
            (work / "answer.txt").write_text("42\n")
            (work / "solve.py").write_text("print(42)\n")
            out = run_cli(["grade", "toy-r1", str(work), "--out", str(self.toy.root / "g")])[1]
        self.assertEqual(out, '{"instance": "toy-r1", "verified": true, "failed_checks": []}\n')
        self.assertIn("grader-stdout.txt", [p.name for p in (self.toy.root / "g").iterdir()])


class RunCollectScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.toy = Toy()
        self.toy.fetch()

    def run_cli(self, *args: str, **env: str) -> tuple[int, str, str]:
        with self.toy.active(**env):
            return run_cli(list(args))

    def test_run_writes_the_run_layout(self) -> None:
        code, out, _ = self.run_cli("run", "toy-r1", "--agent", "cmd", "--model", "m1", "--cmd", self.toy.agent_cmd())
        self.assertEqual(code, 0)
        summary = json.loads(out)
        self.assertEqual(list(summary), ["instance", "config", "run", "verified", "wall_s", "timed_out"])
        self.assertEqual((summary["config"], summary["run"], summary["verified"]), ("cmd-m1", 1, False))
        base = self.toy.runs / "cmd-m1" / "toy-r1" / "run1"
        self.assertEqual(
            sorted(p.name for p in base.iterdir()),
            ["agent-stderr.txt", "grade", "run.json", "started.json", "trace.jsonl", "work"],
        )
        record = json.loads((base / "run.json").read_text())
        self.assertEqual(list(record)[: len(RUN_JSON_KEYS)], RUN_JSON_KEYS)
        for key in ("argv_template", "effort", "agent_version", "mrab_version", "manifest_sha256", "isolation"):
            self.assertIn(key, record)
        self.assertEqual((record["interrupted"], record["graded"], record["effort"]), (False, True, None))
        self.assertEqual(record["manifest_sha256"], self.toy.entry["manifest_sha256"])
        self.assertTrue(record["agent_version"].startswith("Python "))
        self.assertEqual(record["usage"], {"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 50})
        self.assertEqual(record["failed_checks"], ["answer_correct"])
        self.assertEqual(json.loads((base / "trace.jsonl").read_text().splitlines()[0])["task_chars"], 54)
        code, _, err = self.run_cli("run", "toy-r1", "--agent", "cmd", "--model", "m1", "--cmd", self.toy.agent_cmd())
        self.assertEqual((code, err), (1, f"{base} exists; choose another --run\n"))

    def test_run_with_a_skills_folder_and_placeholders(self) -> None:
        skills = self.toy.root / "my-skills"
        (skills / "demo").mkdir(parents=True)
        (skills / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\n")
        cmd = self.toy.agent_cmd("{workdir}", "{model}", "{prompt}")
        out = self.run_cli(
            "run", "toy-r1", "--agent", "cmd", "--model", "m1", "--run", "2", "--addon", str(skills), "--cmd", cmd
        )[1]
        self.assertEqual(json.loads(out)["config"], "cmd-m1+my-skills")
        base = self.toy.runs / "cmd-m1+my-skills" / "toy-r1" / "run2"
        work = base / "work"
        self.assertTrue((work / ".agents" / "skills" / "my-skills" / "demo" / "SKILL.md").exists())
        record = json.loads((base / "run.json").read_text())
        staged = record["workdir_during_run"]  # the agent worked in a neutral staging folder, moved here afterwards
        self.assertEqual(record["argv"][3:], [staged, "m1", staged + "/TASK.txt"])
        self.assertEqual(Path(staged).parent.parent, self.toy.stage)
        self.assertNotIn("my-skills", staged)
        self.assertEqual(record["addon"], str(skills))

    def test_timeout_kills_the_agent(self) -> None:
        cmd = json.dumps([sys.executable, "-c", "import time; time.sleep(30)"])
        out = self.run_cli("run", "toy-r1", "--agent", "cmd", "--model", "m1", "--cap", "1", "--cmd", cmd)[1]
        summary = json.loads(out)
        self.assertTrue(summary["timed_out"])
        self.assertLess(summary["wall_s"], 10)
        record = json.loads((self.toy.runs / "cmd-m1" / "toy-r1" / "run1" / "run.json").read_text())
        self.assertEqual((record["returncode"], record["cap_s"], record["verified"]), (-9, 1, False))

    def test_cmd_agent_needs_a_template_and_leaves_nothing_behind(self) -> None:
        code, _, err = self.run_cli("run", "toy-r1", "--agent", "cmd", "--model", "m1")
        self.assertEqual((code, err), (1, "use --cmd with a JSON list for agent cmd\n"))
        self.assertFalse(self.toy.runs.exists())

    def test_collect_and_score(self) -> None:
        self.run_cli("run", "toy-r1", "--agent", "cmd", "--model", "m1", "--cmd", self.toy.agent_cmd())
        self.run_cli(
            "run",
            "toy-r1",
            "--agent",
            "cmd",
            "--model",
            "m1",
            "--run",
            "2",
            "--cmd",
            self.toy.agent_cmd(),
            FAKE_ALWAYS="1",
        )
        self.run_cli(
            "run",
            "toy-r1",
            "--agent",
            "cmd",
            "--model",
            "m1",
            "--run",
            "3",
            "--no-grade",
            "--config",
            "custom",
            "--cmd",
            self.toy.agent_cmd(),
        )
        out = self.run_cli("collect")[1]
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows[0], ["family", "instance", "domain", "config", "run", "passed", "tokens", "wall_s"])
        self.assertEqual(
            [r[:7] for r in rows[1:]],
            [
                ["z-toy", "toy-r1", "toy", "cmd-m1", "1", "0", "1050"],
                ["z-toy", "toy-r1", "toy", "cmd-m1", "2", "1", "1050"],
                ["z-toy", "toy-r1", "toy", "custom", "3", "0", "1050"],
            ],
        )
        self.assertEqual(self.run_cli("collect", str(self.toy.runs))[1], out)
        (self.toy.root / "runs.csv").write_text(out)
        score = self.run_cli("score", str(self.toy.root / "runs.csv"))[1]
        self.assertEqual(
            score,
            "cmd-m1: verified 1/2 (50.0%), pass^2 0/1 (0.0%), tokens per verified result 0.00 M\n"
            "   toy      1/2\n"
            "custom: verified 0/1 (0.0%), pass^1 0/1 (0.0%), tokens per verified result 0.00 M\n"
            "   toy      0/1\n",
        )


class ScoringTest(unittest.TestCase):
    PAIRS = (
        "family,domain,model,base_passed,addon_passed,base_tokens,addon_tokens\n"
        "f1,seq,m,0,1,10,20\nf2,seq,m,1,1,10,20\nf3,mrs,m,0,1,1,1\nf4,mrs,m,1,0,1,1\nf5,diff,m,0,0,1,1\n"
    )
    PAIRED_OUT = (
        "pairs 5: base 2 (40.0%), with add-on 3 (60.0%), add-on only 2, base only 1, exact McNemar P 1\n"
        "   diff     0 -> 0 of 1\n   mrs      1 -> 1 of 2\n   seq      1 -> 2 of 2\n"
    )

    def test_mcnemar_exact(self) -> None:
        self.assertEqual(scoring.mcnemar(0, 0), 1.0)
        self.assertEqual(scoring.mcnemar(2, 1), 1.0)
        self.assertEqual(scoring.mcnemar(5, 0), 0.0625)
        self.assertAlmostEqual(scoring.mcnemar(10, 2), 2 * 79 / 4096)
        self.assertEqual(scoring.mcnemar(2, 10), scoring.mcnemar(10, 2))

    def test_wilson(self) -> None:
        lo, hi = scoring.wilson(20, 24)
        self.assertAlmostEqual(lo, 0.641, places=3)
        self.assertAlmostEqual(hi, 0.933, places=3)

    def test_score_paired(self) -> None:
        toy = Toy()
        (toy.root / "pairs.csv").write_text(self.PAIRS)
        self.assertEqual(run_cli(["score", "--paired", str(toy.root / "pairs.csv")])[1], self.PAIRED_OUT)

    def test_score_needs_a_file(self) -> None:
        self.assertEqual(run_cli(["score"])[::2], (1, "give a runs CSV (mrab collect) or --paired PAIRS.csv\n"))

    def test_score_py_still_runs_as_a_script(self) -> None:
        toy = Toy()
        (toy.root / "pairs.csv").write_text(self.PAIRS)
        proc = subprocess.run(
            [sys.executable, str(REPO / "mragentbench" / "score.py"), "--paired", str(toy.root / "pairs.csv")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.stdout, self.PAIRED_OUT, proc.stderr)

    def test_usage_from_trace(self) -> None:
        toy = Toy()
        trace = toy.root / "trace.jsonl"
        trace.write_text(
            '{"usage": {"input_tokens": 5, "output_tokens": 2, "note": "x"}}\nnot json\n'
            '{"msg": {"usage": {"input_tokens": 3, "cache_read_input_tokens": 7}}, "list": '
            '[{"usage": {"output_tokens": 1}}]}\n'
        )
        self.assertEqual(
            runner.usage_from_trace(trace), {"input_tokens": 8, "output_tokens": 3, "cache_read_input_tokens": 7}
        )


if __name__ == "__main__":
    unittest.main()
