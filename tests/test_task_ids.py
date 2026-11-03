"""Public task labels must resolve to the same frozen data and saved-run identities."""

from __future__ import annotations

import copy
import json
import shutil
import unittest

from toy import REPO, Toy, run_cli

from mragentbench.catalog import get_instance, load_catalog, load_task_index
from mragentbench.common import MrabError


class TaskIDsTest(unittest.TestCase):
    def test_all_aliases_resolve_to_identical_entries(self):
        index = load_task_index(REPO / "families")
        self.assertEqual(len(index), 24)
        self.assertEqual(sum(len(task["instances"]) for task in index.values()), 88)
        for task in index.values():
            for public, legacy in task["instances"].items():
                with self.subTest(instance=public):
                    entry = get_instance(public)
                    self.assertEqual(entry, get_instance(legacy))
                    self.assertEqual(entry, get_instance(public.lower()))
                    self.assertEqual(entry["family"], task["legacy_id"])
                    self.assertEqual(entry["instance"], legacy)
                    self.assertEqual(entry["public_instance"], public)
        self.assertEqual(len(load_catalog()), 88, "aliases must not duplicate scoring coverage")

    def test_variant_labels_are_explicit_and_do_not_guess_historical_suffixes(self):
        self.assertEqual(get_instance("PERF-01-04")["instance"], "heldout-v7-pcasl-r4")
        self.assertEqual(get_instance("RELAX-01-03")["instance"], "heldout-v4-t2epg-r4")
        with self.assertRaises(MrabError):
            get_instance("RELAX-01-04")
        with self.assertRaises(MrabError):
            get_instance("PERF-01")  # A task type alone must not silently pick a variant.

    def indexed_toy(self):
        toy = Toy()
        self.addCleanup(shutil.rmtree, toy.root)
        (toy.families / "z-toy").rename(toy.families / "TOY-01-answer".lower())
        index = {
            "version": 1,
            "tasks": [
                {
                    "id": "TOY-01",
                    "legacy_id": "z-toy",
                    "directory": "toy-01-answer",
                    "instances": {"TOY-01-01": "toy-r1"},
                }
            ],
        }
        (toy.families / "index.json").write_text(json.dumps(index))
        return toy, index

    def test_alias_fetch_verify_prepare_and_run_keep_existing_storage_and_identity(self):
        toy, _ = self.indexed_toy()
        with toy.active(FAKE_ALWAYS="1"):
            code, _, err = run_cli(["fetch", "TOY-01-01", "--url", toy.packages.as_uri()])
            self.assertEqual((code, err), (0, ""))
            code, out, err = run_cli(["fetch", "toy-r1"])
            self.assertEqual((code, err), (0, ""))
            self.assertIn("already present", out)
            self.assertEqual(run_cli(["verify", "TOY-01-01"])[0], 0)
            work = toy.root / "work"
            self.assertEqual(run_cli(["prepare", "TOY-01-01", str(work)])[0], 0)
            code, _, err = run_cli(["run", "TOY-01-01", "--agent", "cmd", "--model", "test", "--cmd", toy.agent_cmd()])
            self.assertEqual((code, err), (0, ""))
            record = json.loads(next(toy.runs.glob("*/toy-r1/run1/run.json")).read_text())
            self.assertEqual((record["family"], record["instance"]), ("z-toy", "toy-r1"))
            self.assertTrue(record["verified"])
            self.assertTrue((toy.data / "toy-r1").is_dir())
            self.assertFalse((toy.data / "TOY-01-01").exists())

    def test_invalid_index_never_silently_redirects_an_alias(self):
        toy, original = self.indexed_toy()
        cases = {
            "unknown schema": lambda d: d.update(version=2),
            "missing family": lambda d: d.update(tasks=[]),
            "duplicate family": lambda d: d["tasks"].append(copy.deepcopy(d["tasks"][0])),
            "wrong instance": lambda d: d["tasks"][0].update(instances={"TOY-01-01": "other"}),
            "extra alias": lambda d: d["tasks"][0]["instances"].update({"TOY-01-02": "toy-r1"}),
            "wrong prefix": lambda d: d["tasks"][0].update(instances={"OTHER-01-01": "toy-r1"}),
            "path escape": lambda d: d["tasks"][0].update(directory="../other"),
        }
        for label, edit in cases.items():
            with self.subTest(case=label):
                value = copy.deepcopy(original)
                edit(value)
                (toy.families / "index.json").write_text(json.dumps(value))
                with self.assertRaises(MrabError):
                    load_catalog(toy.families)


if __name__ == "__main__":
    unittest.main()
