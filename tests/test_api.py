"""Tests for submission validation in the hosted grading API and for mrab submit --addon-manifest.

boto3 is replaced by stubs, so no AWS call is made. Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from addon_fixtures import make_addon
from toy import REPO

from mragentbench import client
from mragentbench.addon import manifest_record, validate_addon

MINIMAL = REPO / "examples" / "addons" / "minimal"


def import_api(catalog: dict) -> types.ModuleType:
    """Import mragentbench.service.api with stub boto3 modules and a temporary catalog."""
    path = Path(tempfile.mkdtemp(prefix="mrab-api-")) / "catalog.json"
    path.write_text(json.dumps(catalog))
    boto3 = types.ModuleType("boto3")
    boto3.client = lambda *a, **k: mock.MagicMock()
    boto3.resource = lambda *a, **k: mock.MagicMock()
    conditions = types.ModuleType("boto3.dynamodb.conditions")
    conditions.Key = mock.MagicMock()
    botocore_config = types.ModuleType("botocore.config")
    botocore_config.Config = mock.MagicMock()
    stubs = {
        "boto3": boto3,
        "boto3.dynamodb": types.ModuleType("boto3.dynamodb"),
        "boto3.dynamodb.conditions": conditions,
        "botocore": types.ModuleType("botocore"),
        "botocore.config": botocore_config,
    }
    with mock.patch.dict(sys.modules, stubs), mock.patch.dict(os.environ, {"MRAB_CATALOG_FILE": str(path)}):
        sys.modules.pop("mragentbench.service.api", None)
        return importlib.import_module("mragentbench.service.api")


class ValidateSubmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.api = import_api({"toy-r1": {"instance": "toy-r1", "package": "toy-r1.tar"}})

    def body(self, **config: object) -> dict:
        return dict(
            config={"model": "m", "agent": "codex", **config},
            runs=[{"instance": "toy-r1", "run": 1, "path": "runs/toy-r1/run1/work"}],
            bundle_sha256="a" * 64,
            bundle_bytes=10,
        )

    def manifest(self, **over: object) -> dict:
        return dict(manifest_record(validate_addon(MINIMAL)), **over)

    def rejected(self, body: object) -> str:
        with self.assertRaises(self.api.HttpError) as ctx:
            self.api.validate_submission(body)
        self.assertEqual(ctx.exception.status, 400)
        return ctx.exception.message

    def test_without_manifest_is_unchanged(self) -> None:
        out = self.api.validate_submission(self.body(addon="MRFoundry 0.14.0", label="x", extra="dropped"))
        self.assertEqual(out["config"], {"model": "m", "agent": "codex", "addon": "MRFoundry 0.14.0", "label": "x"})
        self.assertEqual(out["runs"], [{"instance": "toy-r1", "run": 1, "path": "runs/toy-r1/run1/work"}])

    def test_with_manifest(self) -> None:
        manifest = self.manifest()
        out = self.api.validate_submission(self.body(addon_manifest=manifest))
        expected = {k: v for k, v in manifest.items() if k != "$schema"}
        self.assertEqual(out["config"]["addon_manifest"], expected)
        self.assertEqual(out["config"]["addon"], "minimal-example 1.0.0")
        out = self.api.validate_submission(self.body(addon="My label", addon_manifest=manifest))
        self.assertEqual(out["config"]["addon"], "My label")
        partial = self.manifest(
            exposure={"public_instances_seen": "partial", "details": "v4 families"}, metadata={"commit": "abc123"}
        )
        self.assertEqual(
            self.api.validate_submission(self.body(addon_manifest=partial))["config"]["addon_manifest"]["metadata"],
            {"commit": "abc123"},
        )

    def test_rejects_bad_manifests(self) -> None:
        cases = {
            "must be an object": "MRFoundry",
            "content_sha256 must be": self.manifest(content_sha256="xyz"),
            "unknown fields skills": self.manifest(skills=["a"]),
            "hosts must be": self.manifest(hosts=["codex", "gemini"]),
            "exposure needs": self.manifest(exposure={"public_instances_seen": "yes", "details": ""}),
            "authors must be": self.manifest(authors=[]),
            "name is required": self.manifest(name="has space"),
            "description is required": self.manifest(description="x" * 1025),
            "metadata must map": self.manifest(metadata={"n": 1}),
            "larger than": self.manifest(metadata={f"k{i}": "v" * 400 for i in range(45)}),
        }
        for expected, manifest in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(expected, self.rejected(self.body(addon_manifest=manifest)))
        missing = self.manifest()
        del missing["exposure"]
        self.assertIn("exposure needs", self.rejected(self.body(addon_manifest=missing)))

    def test_rejects_unhashable_entries(self) -> None:
        for hosts in (["codex", ["claude"]], [{"a": 1}], [None]):
            with self.subTest(hosts=hosts):
                self.assertIn("hosts must be", self.rejected(self.body(addon_manifest=self.manifest(hosts=hosts))))
        body = self.body()
        body["runs"][0]["instance"] = ["toy-r1"]
        self.assertIn("unknown instance", self.rejected(body))

    def test_rejects_non_object_config(self) -> None:
        self.assertIn("must be JSON objects", self.rejected(dict(self.body(), config=["m"])))
        self.assertIn("each run must be a JSON object", self.rejected(dict(self.body(), runs=["toy-r1"])))

    def test_exposure_details_required_unless_unseen(self) -> None:
        for seen in (True, "partial"):
            with self.subTest(seen=seen):
                manifest = self.manifest(exposure={"public_instances_seen": seen, "details": " "})
                self.assertIn("must say what was seen", self.rejected(self.body(addon_manifest=manifest)))
        manifest = self.manifest(exposure={"public_instances_seen": False, "details": ""})
        self.assertFalse(
            self.api.validate_submission(self.body(addon_manifest=manifest))["config"]["addon_manifest"]["exposure"][
                "public_instances_seen"
            ]
        )


class SubmitManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="mrab-submit-"))
        self.addon = make_addon(self.root)
        work = self.root / "runs" / "cmd-m+demo@1.0" / "toy-r1" / "run1" / "work"
        work.mkdir(parents=True)
        self.runs = client.find_runs(self.root / "runs")

    def write_run_json(self, digest: str) -> None:
        (self.runs[0]["work"].parent / "run.json").write_text(
            json.dumps({"addon_manifest": {"content_sha256": digest}})
        )

    def test_manifest_with_content_hash(self) -> None:
        digest = validate_addon(self.addon).content_sha256
        self.write_run_json(digest)
        for path in (self.addon / "addon.json", self.addon):
            manifest = client.addon_manifest_for(path, self.runs)
            self.assertEqual((manifest["name"], manifest["content_sha256"]), ("demo", digest))

    def test_refuses_runs_of_other_content(self) -> None:
        self.write_run_json("0" * 64)
        with self.assertRaises(SystemExit) as ctx:
            client.addon_manifest_for(self.addon / "addon.json", self.runs)
        self.assertIn("was run with add-on content 000000000000", str(ctx.exception.code))

    def test_refuses_mislabelled_runs(self) -> None:
        run_json = self.runs[0]["work"].parent / "run.json"
        run_json.write_text(json.dumps({"addon": None}))
        with self.assertRaises(SystemExit) as ctx:
            client.addon_manifest_for(self.addon, self.runs)
        self.assertIn("was run with no add-on; its add-on cannot be checked", str(ctx.exception.code))
        client.check_runs_without_manifest(self.runs)
        self.write_run_json(validate_addon(self.addon).content_sha256)
        with self.assertRaises(SystemExit) as ctx:
            client.check_runs_without_manifest(self.runs)
        self.assertIn("pass its package with --addon-manifest", str(ctx.exception.code))
        self.assertEqual(client.addon_manifest_for(self.addon, self.runs)["name"], "demo")

    def test_refuses_plain_folder_runs_and_runs_without_records(self) -> None:
        run_json = self.runs[0]["work"].parent / "run.json"
        run_json.write_text(json.dumps({"addon": "/path/to/skills"}))  # review finding: plain skills folder
        with self.assertRaises(SystemExit) as ctx:
            client.check_runs_without_manifest(self.runs)
        self.assertIn("was run with the skills folder /path/to/skills", str(ctx.exception.code))
        with self.assertRaises(SystemExit) as ctx:
            client.addon_manifest_for(self.addon, self.runs)
        self.assertIn("a plain skills folder, not an add-on package", str(ctx.exception.code))
        run_json.unlink()  # review finding: a manifest attached to runs without any record
        client.check_runs_without_manifest(self.runs)
        with self.assertRaises(SystemExit) as ctx:
            client.addon_manifest_for(self.addon, self.runs)
        self.assertIn("run.json is missing; only runs recorded by mrab", str(ctx.exception.code))


if __name__ == "__main__":
    unittest.main()
