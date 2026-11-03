"""Regression checks for the frozen offline import and its public-data boundary."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import re
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("offline_board", REPO / "tools" / "build_offline_leaderboard.py")
board_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(board_tool)


class OfflineLeaderboardTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = board_tool.read_json(board_tool.SNAPSHOT)

    def fake_study(self, root: Path) -> dict[str, str]:
        """Include forbidden payloads at every source layer to test the allowlist."""
        summary = copy.deepcopy(self.snapshot["statistics"])
        secret = "DO_NOT_EXPORT_PRIVATE_TASK_TRACE_OR_SEED"
        summary["unapproved"] = {"trace": secret}
        for split in ("core", "hard"):
            summary[split]["by_family"] = {secret: {"task": secret, "seed": secret}}
            summary[split]["excluded"] = {secret: secret}
            summary[split]["all"]["trace"] = secret
            for stat in summary[split]["by_model"].values():
                stat["task"] = secret
        summary["hard"]["multistage"]["trace"] = secret
        pairs = [dict(row, set="core", prompt=secret, trace=secret, seed=secret) for row in self.snapshot["core_pairs"]]
        # Hard rows do not even need the fields that a Core row requires.
        pairs += [{"set": "hard", "task": secret, "trace": secret, "seed": secret, "family": secret}]
        for key, value in (("summary", summary), ("pairs", pairs)):
            path = root / board_tool.SOURCE_FILES[key]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
        (root / board_tool.SOURCE_FILES["handoff"]).write_text("Approved aggregate-only handoff\n", encoding="utf-8")
        return {
            name: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for name, path in board_tool.SOURCE_FILES.items()
        }

    def test_import_uses_positive_allowlist_and_never_copies_hard_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins = self.fake_study(root)
            with patch.object(board_tool, "SOURCE_SHA256", pins):
                imported = board_tool.import_study(root)
                output = board_tool.serialized(imported) + board_tool.serialized(board_tool.build(imported))
        self.assertNotIn("DO_NOT_EXPORT_PRIVATE_TASK_TRACE_OR_SEED", output)
        self.assertNotIn('"by_family"', output)
        self.assertNotIn('"trace"', output)
        self.assertNotIn('"seed"', output)
        self.assertEqual(len(imported["core_pairs"]), 240)
        self.assertEqual(imported["statistics"], self.snapshot["statistics"])
        self.assertEqual(
            set(imported["statistics"]["hard"]),
            {"all", "n_families", "n_models", "by_model", "multistage", "system", "strong", "other"},
        )
        self.assertTrue(all(set(row) == set(board_tool.PAIR_FIELDS) for row in imported["core_pairs"]))

    def test_snapshot_rebuild_also_strips_unapproved_fields(self):
        raw = copy.deepcopy(self.snapshot)
        raw["hard_pairs"] = [{"task": "PRIVATE_SENTINEL"}]
        raw["core_pairs"][0]["trace"] = "PRIVATE_SENTINEL"
        raw["statistics"]["hard"]["by_family"] = {"PRIVATE_SENTINEL": {}}
        raw["provenance"]["private_path"] = "PRIVATE_SENTINEL"
        self.assertEqual(board_tool.sanitize_snapshot(raw), self.snapshot)
        self.assertNotIn("PRIVATE_SENTINEL", board_tool.serialized(board_tool.build(raw)))

    def test_core_rows_reproduce_paired_statistics_and_all_board_entries(self):
        board = board_tool.build(self.snapshot)
        self.assertEqual(board["protocol"], "offline")
        self.assertEqual(len(board["entries"]), 20)
        self.assertEqual(sum(entry["runs"] for entry in board["entries"]), 480)
        for entry in board["entries"]:
            arm = "S" if entry["addon"] else "A"
            expected = self.snapshot["statistics"]["core"]["by_model"][entry["model"]]
            self.assertEqual((entry["runs"], entry["verified"]), (24, expected[arm]))
            self.assertEqual(sum(value["verified"] for value in entry["per_instance"].values()), expected[arm])
            self.assertEqual(sum(value["verified"] for value in entry["by_domain"].values()), expected[arm])
            self.assertEqual(len(entry["per_instance"]), 24)
            self.assertTrue(entry["complete"])
            self.assertIn("Wilson", entry["ci95_method"])
            for unavailable in ("timeouts", "pass_all_runs", "instances_with_repeats"):
                self.assertNotIn(unavailable, entry)
            if entry["addon"]:
                self.assertEqual(entry["addon"]["version"], "0.14.0")
                self.assertEqual(entry["addon"]["commit"], "bd49b95")
        evaluation = board["offline_evaluation"]
        for split, expected in (("core", (240, 162, 188)), ("hard", (134, 49, 60))):
            self.assertEqual(tuple(evaluation[split]["all"][k] for k in ("n", "A", "S")), expected)
        self.assertEqual(tuple(evaluation["combined"][k] for k in ("n", "A", "S")), (374, 211, 248))
        self.assertEqual(evaluation["core"]["by_domain"]["diff"]["A"], 17)
        self.assertEqual(evaluation["core"]["by_domain"]["diff"]["S"], 15)
        self.assertEqual(evaluation["core"]["all"]["ci"], [0.008333333333333333, 0.2125])
        self.assertEqual(evaluation["hard"]["all"]["ci"], [-0.0392156862745098, 0.19718309859154928])
        self.assertGreater(evaluation["hard"]["all"]["p"], 0.05)

    def test_hard_cohorts_are_explicit_and_unequal(self):
        hard = self.snapshot["statistics"]["hard"]
        self.assertEqual(hard["strong"]["n"], 90)
        self.assertEqual(hard["other"]["n"], 44)
        self.assertEqual(hard["system"]["n"], 24)
        for model, stat in hard["by_model"].items():
            self.assertEqual(stat["n"], 30 if model in board_tool.FRONTIER else 11)

    def test_rejects_corrupted_counts_rows_statistics_and_hidden_identifiers(self):
        changes = [
            lambda x: x["statistics"]["hard"]["all"].update(A=50),
            lambda x: x["statistics"]["core"]["all"].update(p=0.5),
            lambda x: x["statistics"]["hard"]["all"].update(ci=[float("nan"), 0.2]),
            lambda x: x["statistics"]["core"]["all"].update(tok_ratio=0.9),
            lambda x: x["core_pairs"][0].update(A=not x["core_pairs"][0]["A"]),
            lambda x: x["core_pairs"][0].update(task="PRIVATE_UNPUBLISHED_TASK"),
            lambda x: x["core_pairs"].append(copy.deepcopy(x["core_pairs"][0])),
            lambda x: x["statistics"]["hard"]["by_model"].update(PRIVATE_MODEL={}),
        ]
        for change in changes:
            with self.subTest(change=change):
                corrupted = copy.deepcopy(self.snapshot)
                change(corrupted)
                with self.assertRaises(ValueError):
                    board_tool.build(corrupted)

    def test_check_detects_stale_outputs_without_writing(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            snapshot = root / "snapshot.json"
            board = root / "board.json"
            snapshot.write_text(board_tool.serialized(self.snapshot), encoding="utf-8")
            arguments = ["--snapshot", str(snapshot), "--out", str(board)]
            self.assertEqual(board_tool.main(arguments), 0)
            original = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (snapshot, board)}
            self.assertEqual(board_tool.main([*arguments, "--check"]), 0)
            self.assertEqual(board_tool.main(arguments), 0)
            self.assertEqual(original, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in original})
            board.write_text("stale\n", encoding="utf-8")
            modified = board.stat().st_mtime_ns
            self.assertEqual(board_tool.main([*arguments, "--check"]), 1)
            self.assertEqual(board.read_text(encoding="utf-8"), "stale\n")
            self.assertEqual(board.stat().st_mtime_ns, modified)

    def test_study_import_check_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            pins = self.fake_study(root / "study")
            arguments = [
                "--study-root",
                str(root / "study"),
                "--snapshot",
                str(root / "snapshot.json"),
                "--out",
                str(root / "board.json"),
            ]
            with patch.object(board_tool, "SOURCE_SHA256", pins):
                self.assertEqual(board_tool.main(arguments), 0)
                self.assertEqual(board_tool.main([*arguments, "--check"]), 0)
                self.assertEqual(board_tool.main(arguments[2:] + ["--check"]), 0)

    def test_import_rejects_changed_source_bytes_before_assigning_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins = self.fake_study(root)
            with patch.object(board_tool, "SOURCE_SHA256", pins):
                board_tool.import_study(root)
                for name, relative_path in board_tool.SOURCE_FILES.items():
                    with self.subTest(source=name):
                        path = root / relative_path
                        original = path.read_bytes()
                        path.write_bytes(original + b"\n")
                        with self.assertRaisesRegex(ValueError, "source hash does not match approved handoff"):
                            board_tool.import_study(root)
                        path.write_bytes(original)

    def test_snapshot_rejects_unapproved_provenance_hashes(self):
        for name in board_tool.SOURCE_FILES:
            with self.subTest(source=name):
                changed = copy.deepcopy(self.snapshot)
                changed["provenance"]["files"][name]["sha256"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "source hash does not match approved handoff"):
                    board_tool.sanitize_snapshot(changed)

    def test_frozen_payload_rejects_plausible_ci_and_median_edits(self):
        for field in ("ci", "A_wall", "A_tok"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.snapshot)
                if field == "ci":
                    changed["statistics"]["hard"]["all"]["ci"][0] += 0.001
                else:
                    model = changed["core_pairs"][0]["model"]
                    rows = sorted(
                        (row for row in changed["core_pairs"] if row["model"] == model), key=lambda row: row[field]
                    )
                    old_median = statistics.median(row[field] for row in rows)
                    old_total = sum(row[field] for row in rows)
                    rows[len(rows) // 2][field] += 2
                    rows[0][field] -= 2
                    self.assertAlmostEqual(sum(row[field] for row in rows), old_total)
                    self.assertNotEqual(statistics.median(row[field] for row in rows), old_median)
                with self.assertRaisesRegex(ValueError, "frozen payload changed"):
                    board_tool.sanitize_snapshot(changed)

    def test_compatibility_wrapper_propagates_stale_check_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "snapshot.json"
            board = root / "board.json"
            snapshot.write_text(board_tool.serialized(self.snapshot), encoding="utf-8")
            board.write_text("stale\n", encoding="utf-8")
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (snapshot, board)}
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "tools" / "build_leaderboard.py"),
                    "--snapshot",
                    str(snapshot),
                    "--out",
                    str(board),
                    "--check",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("out of date", result.stdout)
            self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before})

    def test_committed_outputs_are_current_and_only_offline(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(board_tool.main(["--check"]), 0)
        for path in (board_tool.SNAPSHOT, board_tool.BOARD):
            content = path.read_text(encoding="utf-8")
            self.assertFalse(
                re.search(r'round[ -]?5|"version":\s*"0\.15|/mnt/localssd', content.lower()),
                f"{path.name} contains an obsolete protocol, version or private machine path",
            )


if __name__ == "__main__":
    unittest.main()
