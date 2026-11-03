"""Public results export and consistency checks; no agents, graders or network are executed."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from prepare_submission import prepare  # noqa: E402
from validate_submission import FIELDS, validate  # noqa: E402


class SubmissionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runs = self.root / "runs"
        self.out = self.root / "submission"
        self.entries = {
            "public-one": dict(
                family="one", domain="seq", cap_s=60, manifest_sha256="a" * 64, checks=["output", "physics"]
            ),
        }
        self.record = dict(
            instance="public-one",
            family="one",
            domain="seq",
            config="test",
            run=1,
            model="test-model",
            agent="cmd",
            agent_version="test 1",
            mrab_version="0.1.0.dev0",
            manifest_sha256="a" * 64,
            cap_s=60,
            verified=True,
            graded=True,
            wall_s=3.2,
            usage={"input_tokens": 10, "output_tokens": 2},
            addon=None,
        )
        self.write_attempt(1)

    @staticmethod
    def write(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def write_attempt(self, run: int, complete: bool = True) -> Path:
        folder = self.runs / "test" / "public-one" / f"run{run}"
        self.write(
            folder / "started.json",
            dict(instance="public-one", config="test", run=run, started_at="2026-11-03T00:00:00Z"),
        )
        if complete:
            self.write(folder / "run.json", dict(self.record, run=run))
            self.write(
                folder / "grade" / "grade.json",
                dict(all_automated_checks_pass=True, checks={"output": {"pass": True}, "physics": {"pass": True}}),
            )
            (folder / "trace.jsonl").write_text('{"event":"done"}\n')
            self.write(folder / "work" / "must-not-copy.json", {"private": "workspace"})
        return folder

    def export(self) -> None:
        prepare(self.runs, "test", self.out, self.entries)
        self.edit(
            self.out / "metadata.json", benchmark_commit="b" * 40, hardware="test CPU", all_started_runs_included=True
        )

    def edit(self, path: Path, **updates: object) -> None:
        value = json.loads(path.read_text())
        value.update(updates)
        self.write(path, value)

    def rows(self) -> list[dict]:
        with (self.out / "runs.csv").open(newline="") as handle:
            return list(csv.DictReader(handle))

    def write_rows(self, rows: list[dict]) -> None:
        with (self.out / "runs.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_export_validates_without_workspace(self) -> None:
        self.export()
        result = validate(self.out, self.entries)
        self.assertEqual((result["attempts"], result["passed"], result["completion"]), (1, 1, 1))
        self.assertEqual(list(self.out.rglob("must-not-copy.json")), [])
        self.assertTrue((self.out / "records/public-one/run1/trace.jsonl.gz").is_file())

    def test_unfinished_attempt_counts_as_failure(self) -> None:
        self.write_attempt(2, complete=False)
        self.export()
        path = self.out / "records/public-one/run2/incomplete.json"
        with self.assertRaisesRegex(ValueError, "placeholder"):
            validate(self.out, self.entries)
        self.edit(path, reason="Host terminated before the final record was written.")
        result = validate(self.out, self.entries)
        self.assertEqual((result["attempts"], result["passed"], result["completion"]), (2, 1, 0.5))
        self.assertEqual((result["unfinished"], result["attempts_without_token_usage"]), (1, 1))

    def test_reject_missing_attempt_and_duplicate(self) -> None:
        self.export()
        rows = self.rows()
        self.write_rows(rows + rows)
        with self.assertRaisesRegex(ValueError, "duplicate CSV"):
            validate(self.out, self.entries)
        self.write_rows([])
        with self.assertRaisesRegex(ValueError, "missing 1"):
            validate(self.out, self.entries)

    def test_reject_unreported_record_folder(self) -> None:
        self.export()
        self.write(self.out / "records/public-one/run2/started.json", {})
        with self.assertRaisesRegex(ValueError, "record folders"):
            validate(self.out, self.entries)

    def test_reject_inconsistent_success_and_partial_grade(self) -> None:
        self.export()
        path = self.out / "records/public-one/run1/grade.json"
        self.edit(path, checks={"output": {"pass": True}, "physics": {"pass": False}})
        with self.assertRaisesRegex(ValueError, "inconsistent grade"):
            validate(self.out, self.entries)
        self.edit(path, checks={"output": {"pass": True}})
        with self.assertRaisesRegex(ValueError, "omits required checks"):
            validate(self.out, self.entries)

    def test_reject_resource_and_model_mismatch(self) -> None:
        self.export()
        rows = self.rows()
        rows[0]["tokens"] = "1"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "token total"):
            validate(self.out, self.entries)
        rows[0]["tokens"] = "12"
        self.write_rows(rows)
        self.edit(self.out / "metadata.json", model="different-model")
        with self.assertRaisesRegex(ValueError, "model disagrees"):
            validate(self.out, self.entries)

    def test_unknown_usage_is_not_zero(self) -> None:
        self.edit(self.runs / "test/public-one/run1/run.json", usage={})
        self.export()
        self.assertEqual(self.rows()[0]["tokens"], "")
        self.assertEqual(validate(self.out, self.entries)["attempts_without_token_usage"], 1)

    def test_full_core_requires_all_instances_and_three_attempts(self) -> None:
        self.export()
        self.edit(self.out / "metadata.json", track="full-core")
        with self.assertRaisesRegex(ValueError, "three attempts"):
            validate(self.out, self.entries)

    def test_manifest_and_addon_must_match(self) -> None:
        self.export()
        path = self.out / "records/public-one/run1/run.json"
        self.edit(path, manifest_sha256="c" * 64)
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            validate(self.out, self.entries)
        self.edit(path, manifest_sha256="a" * 64, addon="a-library")
        with self.assertRaisesRegex(ValueError, "undeclared addon"):
            validate(self.out, self.entries)

    def test_symlinks_and_nonpublic_tasks_rejected(self) -> None:
        self.export()
        (self.out / "external").symlink_to(self.runs, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symbolic links"):
            validate(self.out, self.entries)
        (self.out / "external").unlink()
        self.edit(self.out / "metadata.json", instances=["unknown-task"])
        with self.assertRaisesRegex(ValueError, "nonpublic"):
            validate(self.out, self.entries)


if __name__ == "__main__":
    unittest.main()
