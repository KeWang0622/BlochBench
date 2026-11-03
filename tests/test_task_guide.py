"""Keep the public task catalogue, source links, and generated guide in agreement."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_task_guide", REPO / "tools" / "build_task_guide.py")
assert _spec and _spec.loader
guide = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guide)


class TaskGuideTest(unittest.TestCase):
    def copy_sources(self) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="mrab-task-guide-")
        self.addCleanup(temporary.cleanup)
        repo = Path(temporary.name)
        (repo / "docs").mkdir()
        for name in ("task-catalog.json", "PROTOCOL.md", "OFFLINE-RESULTS.md"):
            shutil.copyfile(REPO / "docs" / name, repo / "docs" / name)
        shutil.copyfile(REPO / "README.md", repo / "README.md")
        for source in (REPO / "families").glob("*/instances.json"):
            target = repo / "families" / source.parent.name
            target.mkdir(parents=True)
            for name in ("instances.json", "README.md", "task.example.json"):
                shutil.copyfile(source.parent / name, target / name)
        return repo

    def test_all_24_task_types_and_88_variants_have_full_specs(self):
        tasks = guide.load_catalogue()
        expected = {path.parent.name for path in (REPO / "families").glob("*/instances.json")}
        self.assertEqual({task["id"] for task in tasks}, expected)
        self.assertEqual(len(tasks), 24)
        self.assertEqual(sum(task["variants"] for task in tasks), 88)
        self.assertEqual({task["domain"] for task in tasks}, set(guide.DOMAIN_ORDER))
        for task in tasks:
            with self.subTest(task=task["id"]):
                self.assertNotEqual(task["title"], task["id"])
                self.assertTrue((REPO / "docs" / task["url"]).is_file())
                self.assertTrue(all(task[key].strip() for key in guide.FIELDS))

    def test_guide_has_exactly_one_catalogue_row_for_every_task(self):
        rendered = guide.build()
        rows = re.findall(r"^\| \[([^\]]+)\]\(\.\./families/([^/]+)/task\.example\.json\)", rendered, re.M)
        self.assertEqual(len(rows), 24)
        self.assertEqual(dict(rows), {task["title"]: task["id"] for task in guide.load_catalogue()})
        for target in re.findall(r"\]\(([^)]+)\)", rendered):
            self.assertTrue((REPO / "docs" / target).is_file(), target)

    def test_guide_is_current_and_deterministic(self):
        tasks = guide.load_catalogue()
        self.assertEqual(guide.render(tasks), guide.render(list(reversed(tasks))))
        self.assertEqual((REPO / "docs" / "TASKS.md").read_text(encoding="utf-8"), guide.build())
        self.assertEqual(guide.main(["--check"]), 0)

    def test_rejects_incomplete_extra_and_ambiguous_catalogue_entries(self):
        repo = self.copy_sources()
        path = repo / "docs" / "task-catalog.json"
        original = path.read_text(encoding="utf-8")
        cases = {
            "missing type": lambda data: data.pop("v4-qsm"),
            "unknown type": lambda data: data.update(unknown=data["v4-qsm"]),
            "missing deliverable": lambda data: data["v4-qsm"].pop("output"),
            "empty input": lambda data: data["v4-qsm"].update(input=""),
            "internal title": lambda data: data["v4-qsm"].update(title="v4-qsm"),
            "too verbose": lambda data: data["v4-qsm"].update(output="A" * 221),
            "broken table": lambda data: data["v4-qsm"].update(input="one | two"),
        }
        for label, change in cases.items():
            with self.subTest(case=label):
                data = json.loads(original)
                change(data)
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(guide.CatalogueError):
                    guide.load_catalogue(repo)

    def test_missing_public_source_or_documentation_link_is_rejected(self):
        for target in ("families/v4-qsm/task.example.json", "docs/PROTOCOL.md"):
            with self.subTest(target=target):
                repo = self.copy_sources()
                (repo / target).unlink()
                with self.assertRaises(guide.CatalogueError):
                    guide.build(repo)

    def test_check_detects_stale_output_without_writing(self):
        repo = self.copy_sources()
        output = repo / "docs" / "TASKS.md"
        output.write_text("outdated\n", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(guide.main(["--check"], repo), 1)
        self.assertEqual(output.read_text(encoding="utf-8"), "outdated\n")
        self.assertEqual(guide.main([], repo), 0)
        self.assertEqual(guide.main(["--check"], repo), 0)
        self.assertEqual(output.read_text(encoding="utf-8"), guide.build(repo))


if __name__ == "__main__":
    unittest.main()
