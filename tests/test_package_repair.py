"""Public package repairs must preserve frozen content and remain reproducible."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("repair_release_packages", REPO / "tools" / "repair_release_packages.py")
assert _spec and _spec.loader
repair = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repair)


class PackageRepairTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mrab-package-repair-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "cache"
        self.source.mkdir()
        self.repo = self.root / "repo"
        (self.repo / "docs").mkdir(parents=True)
        (self.repo / "families" / "toy").mkdir(parents=True)
        self.catalogue = self.repo / "families" / "toy" / "instances.json"
        self.package = self.source / "heldout-toy.tar"

    def fixture(self, dirty=True, protected=None, altered=False, unsafe=False):
        payloads = {"public/task.json": b'{"test": true}\n', "private/grader.py": b"# frozen grader\n"}
        extra = {"private/validation/result.json": b'{"passed": true}\n'}
        if dirty:
            extra["private/refenv/lib/local.py"] = b"# disposable environment\n"
        frozen = dict(payloads)
        if protected:
            frozen[protected] = extra.get(protected, b"symlink")
        manifest = b"# frozen test package\n" + b"".join(
            f"{hashlib.sha256(data).hexdigest()}  ./{name}\n".encode() for name, data in sorted(frozen.items())
        )
        if altered:
            payloads["private/grader.py"] = b"# modified grader\n"
        payloads.update(extra)
        payloads["FROZEN-SHA256.txt"] = manifest
        if unsafe:
            payloads["../escape.txt"] = b"unsafe\n"
        with tarfile.open(self.package, "w", format=tarfile.PAX_FORMAT) as archive:
            for name, data in sorted(payloads.items()):
                info = tarfile.TarInfo(f"heldout-toy/{name}")
                info.size = len(data)
                info.mtime = 1720000000
                archive.addfile(info, io.BytesIO(data))
            if dirty:
                info = tarfile.TarInfo("heldout-toy/private/validation/.venv")
                info.type = tarfile.SYMTYPE
                info.linkname = "/old-machine/environment"
                archive.addfile(info)
        record = {
            "instance": "heldout-toy",
            "source": "heldout-toy",
            "package": self.package.name,
            "package_sha256": repair.sha256_file(self.package),
            "package_bytes": self.package.stat().st_size,
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
            "domain": "seq",
            "cap_s": 3600,
            "grader": "grader.py",
        }
        self.catalogue.write_text(json.dumps([record], indent=1) + "\n", encoding="utf-8")
        return record, manifest, payloads

    def test_repair_preserves_frozen_bytes_manifest_and_all_non_environment_extras(self):
        record, manifest, payloads = self.fixture()
        original_hash = repair.sha256_file(self.package)
        output = self.root / "release"
        with contextlib.redirect_stdout(io.StringIO()):
            report = repair.repair_release(self.source, output, self.repo)
        with tarfile.open(output / self.package.name) as archive:
            names = set(archive.getnames())
            self.assertNotIn("heldout-toy/private/validation/.venv", names)
            self.assertNotIn("heldout-toy/private/refenv/lib/local.py", names)
            for name, data in payloads.items():
                if name.startswith("private/refenv/"):
                    continue
                self.assertEqual(archive.extractfile(f"heldout-toy/{name}").read(), data)
            self.assertEqual(archive.extractfile("heldout-toy/FROZEN-SHA256.txt").read(), manifest)
        after = json.loads(self.catalogue.read_text(encoding="utf-8"))[0]
        changed = {key for key in record if record[key] != after[key]}
        self.assertTrue(changed)
        self.assertLessEqual(changed, {"package_sha256", "package_bytes"})
        self.assertEqual(after["manifest_sha256"], record["manifest_sha256"])
        self.assertEqual(repair.sha256_file(self.package), original_hash)
        self.assertEqual(report["totals"]["verified_frozen_files"], 2)
        self.assertEqual(report["removed"]["symlinks"], 1)
        self.assertEqual(report["removed"]["files"], 1)

    def test_repair_is_deterministic_and_rerunnable_after_catalogue_update(self):
        self.fixture()
        first, second = self.root / "first", self.root / "second"
        with contextlib.redirect_stdout(io.StringIO()):
            report_a = repair.repair_release(self.source, first, self.repo)
            report_b = repair.repair_release(self.source, second, self.repo)
        self.assertEqual(report_a, report_b)
        self.assertEqual(repair.sha256_file(first / self.package.name), repair.sha256_file(second / self.package.name))

    def test_clean_package_is_copied_byte_for_byte(self):
        record, _, _ = self.fixture(dirty=False)
        before = self.catalogue.read_bytes()
        output = self.root / "clean"
        with contextlib.redirect_stdout(io.StringIO()):
            report = repair.repair_release(self.source, output, self.repo)
        self.assertEqual(repair.sha256_file(output / self.package.name), record["package_sha256"])
        self.assertEqual(self.catalogue.read_bytes(), before)
        self.assertEqual(report["totals"]["unchanged"], 1)

    def test_manifest_protected_environment_file_or_link_cannot_be_removed(self):
        for protected in ("private/refenv/lib/local.py", "private/validation/.venv"):
            with self.subTest(protected=protected):
                record, _, _ = self.fixture(protected=protected)
                with self.assertRaisesRegex(repair.PackagingError, "removal would affect"):
                    repair.archive_plan(self.package, record)

    def test_changed_frozen_content_and_unsafe_member_paths_are_rejected(self):
        for options, message in (({"altered": True}, "content differs"), ({"unsafe": True}, "unsafe")):
            with self.subTest(options=options):
                record, _, _ = self.fixture(**options)
                with self.assertRaisesRegex(repair.PackagingError, message):
                    repair.archive_plan(self.package, record)

    def test_unregistered_source_hash_does_not_update_catalogue(self):
        self.fixture()
        before = self.catalogue.read_bytes()
        with self.package.open("ab") as handle:
            handle.write(b"unregistered change")
        with self.assertRaisesRegex(repair.PackagingError, "not registered"):
            repair.repair_release(self.source, self.root / "bad", self.repo)
        self.assertEqual(self.catalogue.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
