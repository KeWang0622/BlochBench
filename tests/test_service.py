"""Tests for the hosted grading job and the submission bundle (standard library only).

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import hashlib
import sys
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mragentbench import client  # noqa: E402
from mragentbench.service import job  # noqa: E402

TOY_GRADER = textwrap.dedent("""
    import json, subprocess, sys
    from pathlib import Path
    work, out = Path(sys.argv[1]), Path(sys.argv[2])
    answer = work / "answer.txt"
    checks = {"answer_present": {"pass": answer.exists()},
              "answer_correct": {"pass": answer.exists() and answer.read_text().strip() == "42"}}
    entry = work / "solve.py"
    rerun = entry.exists() and subprocess.run([sys.executable, str(entry)], capture_output=True, text=True,
                                              timeout=30).stdout.strip() == "42"
    checks["entrypoint_reruns"] = {"pass": rerun}
    (out / "grade.json").write_text(json.dumps({"all_automated_checks_pass": all(c["pass"] for c in checks.values()),
                                                "checks": checks}))
""")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def make_instance(root: Path, name: str = "toy-r1") -> tuple[Path, dict]:
    d = root / "src" / name
    (d / "private").mkdir(parents=True)
    (d / "public").mkdir()
    (d / "prompt.txt").write_text("Write 42 to answer.txt and a solve.py that prints it.\n")
    (d / "private" / "grade_toy.py").write_text(TOY_GRADER)
    files = sorted(p for p in d.rglob("*") if p.is_file())
    (d / "FROZEN-SHA256.txt").write_text(
        "# sha256 of every task file\n" + "".join(f"{sha(p)}  {p.relative_to(d)}\n" for p in files)
    )
    pkg = root / "pkgs" / f"{name}.tar"
    pkg.parent.mkdir(parents=True)
    with tarfile.open(pkg, "w") as t:
        t.add(d, arcname=name)
    entry = dict(
        url=pkg.as_uri(),
        package=pkg.name,
        package_sha256=sha(pkg),
        manifest_sha256=sha(d / "FROZEN-SHA256.txt"),
        grader="grade_toy.py",
    )
    return pkg, entry


def make_run(runs: Path, instance: str, k: int, answer: str | None, solve: bool) -> None:
    w = runs / "toy-config" / instance / f"run{k}" / "work"
    w.mkdir(parents=True)
    if answer is not None:
        (w / "answer.txt").write_text(answer)
    if solve:
        (w / "solve.py").write_text("print(42)\n")
    (w / ".venv").mkdir()
    (w / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
    (w / "tools" / "julia-9" / "bin").mkdir(parents=True)
    (w / "tools" / "julia-9" / "bin" / "julia").write_text("")


class BundleAndJobTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mrab-test-"))
        self.pkg, self.entry = make_instance(self.tmp)
        runs = self.tmp / "runs"
        make_run(runs, "toy-r1", 1, "42", solve=True)  # correct
        make_run(runs, "toy-r1", 2, "41", solve=True)  # wrong answer
        make_run(runs, "toy-r1", 3, None, solve=False)  # empty submission
        self.runs = client.find_runs(runs)
        self.info = client.make_bundle(self.runs, self.tmp / "bundle.tar.gz", {"model": "m", "agent": "a"})

    def spec(self, **over) -> dict:
        s = dict(
            submission_id="sub-test",
            shards=1,
            grade_timeout_s=60,
            bundle_url=(self.tmp / "bundle.tar.gz").as_uri(),
            bundle_sha256=self.info["sha256"],
            callback_url="",
            job_token="",
            instances={"toy-r1": self.entry},
        )
        s.update(over)
        return s

    def test_bundle_skips_environments_and_runtimes(self) -> None:
        with tarfile.open(self.tmp / "bundle.tar.gz") as t:
            names = t.getnames()
        self.assertIn("submission.json", names)
        self.assertFalse(any(".venv" in n or "julia-9" in n for n in names))
        self.assertEqual(len(self.info["manifest"]["runs"]), 3)

    def test_grades_each_run(self) -> None:
        res = job.run_shard(self.spec(), 0, self.tmp / "scratch")
        by_run = {r["run"]: r for r in res["runs"]}
        self.assertTrue(by_run[1]["verified"])
        self.assertEqual(by_run[2]["failed_checks"], ["answer_correct"])
        self.assertFalse(by_run[3]["verified"])
        self.assertEqual(set(by_run[3]["failed_checks"]), {"answer_present", "answer_correct", "entrypoint_reruns"})

    def test_shards_partition_runs(self) -> None:
        seen = []
        for shard in range(2):
            seen += [
                (r["instance"], r["run"])
                for r in job.run_shard(self.spec(shards=2), shard, self.tmp / f"s{shard}")["runs"]
            ]
        self.assertEqual(sorted(seen), [("toy-r1", 1), ("toy-r1", 2), ("toy-r1", 3)])

    def test_rejects_altered_bundle(self) -> None:
        with self.assertRaises(ValueError):
            job.run_shard(self.spec(bundle_sha256="0" * 64), 0, self.tmp / "scratch")

    def test_rejects_altered_instance(self) -> None:
        bad = dict(self.entry, manifest_sha256="0" * 64)
        res = job.run_shard(self.spec(instances={"toy-r1": bad}), 0, self.tmp / "scratch")
        self.assertTrue(all("manifest" in r["error"] for r in res["runs"]))

    def test_safe_extract_blocks_path_traversal(self) -> None:
        evil = self.tmp / "evil.tar"
        payload = self.tmp / "payload.txt"
        payload.write_text("x")
        with tarfile.open(evil, "w") as t:
            t.add(payload, arcname="../../escaped.txt")
        with self.assertRaises(tarfile.FilterError):
            job.safe_extract(evil, self.tmp / "out")


if __name__ == "__main__":
    unittest.main()
