"""Tests for task family metadata, public aliases and frozen legacy identities.

The schema checks need jsonschema (pip install -r requirements-dev.txt); without it they are skipped, and CI always
installs it.
Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "schemas" / "family.schema.json"

_spec = importlib.util.spec_from_file_location("make_family_metadata", REPO / "tools" / "make_family_metadata.py")
assert _spec and _spec.loader
metadata = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metadata)

try:
    import jsonschema
except ImportError:  # pragma: no cover - CI installs it
    jsonschema = None


def family_files() -> list[Path]:
    return [d / "family.json" for d in metadata.family_dirs()]


class FamilyMetadataTest(unittest.TestCase):
    def test_every_family_has_metadata(self) -> None:
        dirs = metadata.family_dirs()
        self.assertEqual(set(metadata.load_index()), {d.name for d in dirs})
        self.assertEqual(len(dirs), len(list((REPO / "families").glob("*/README.md"))))
        self.assertGreater(len(dirs), 0)
        for path in family_files():
            with self.subTest(family=path.parent.name):
                self.assertTrue(path.is_file(), "run make families")
        stray = sorted(p.parent.name for p in (REPO / "families").glob("*/family.json") if p.parent not in dirs)
        self.assertEqual(stray, [])

    def test_metadata_matches_its_sources(self) -> None:
        for path in family_files():
            with self.subTest(family=path.parent.name):
                expected = metadata.render(metadata.build(path.parent))
                self.assertEqual(path.read_text(encoding="utf-8"), expected, "out of date: run make families")

    def test_metadata_agrees_with_the_files_it_summarizes(self) -> None:
        for path in family_files():
            family = json.loads(path.read_text(encoding="utf-8"))
            instances = json.loads((path.parent / "instances.json").read_text(encoding="utf-8"))
            readme = (path.parent / "README.md").read_text(encoding="utf-8")
            indexed = metadata.load_index()[path.parent.name]
            with self.subTest(family=family["id"]):
                self.assertEqual(family["id"], indexed["legacy_id"])
                self.assertEqual(family["public_id"], indexed["id"])
                self.assertEqual(family["directory"], path.parent.name)
                self.assertEqual(family["instance_aliases"], indexed["instances"])
                self.assertEqual(family["instances"], [x["instance"] for x in instances])
                self.assertTrue(all(x["cap_s"] == family["time_cap_s"] for x in instances))
                self.assertIn(f"- Automated checks ({len(family['checks'])}): {', '.join(family['checks'])}", readme)
                self.assertIn(f"- Time cap: {family['time_cap_s'] // 60} min", readme)

    def test_inconsistent_sources_are_refused(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="mrab-family-")
        self.addCleanup(temporary.cleanup)
        tmp = Path(temporary.name)
        source = metadata.family_dirs()[0]
        cases = {
            "time cap": ("README.md", lambda t: t.replace("- Time cap: ", "- Time cap: 1", 1)),
            "checks": ("README.md", lambda t: t.replace("- Automated checks (", "- Automated checks (9", 1)),
            "instances": ("instances.json", lambda t: json.dumps(json.loads(t)[:1])),
            "heading": ("README.md", lambda t: t.replace("# ", "# OTHER ", 1)),
            "public ID": ("README.md", lambda t: t.replace("- Task ID: ", "- Task ID: OTHER-", 1)),
            "legacy ID": ("README.md", lambda t: t.replace("- Legacy ID: ", "- Legacy ID: other-", 1)),
            "task identity": (
                "task.example.json",
                lambda t: json.dumps({**json.loads(t), "id": "heldout-v99-other-01"}),
            ),
        }
        for label, (name, edit) in cases.items():
            with self.subTest(label):
                family = tmp / label.replace(" ", "-") / source.name
                shutil.copytree(source, family, ignore=shutil.ignore_patterns("code"))
                shutil.copy(REPO / "families" / "index.json", family.parent / "index.json")
                (family / name).write_text(edit((family / name).read_text(encoding="utf-8")), encoding="utf-8")
                with self.assertRaises(metadata.MetadataError):
                    metadata.build(family)

    def test_inconsistent_alias_maps_are_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="blochbench-alias-") as temporary:
            root = Path(temporary)
            source = metadata.family_dirs()[0]
            family = root / source.name
            shutil.copytree(source, family, ignore=shutil.ignore_patterns("code"))
            original = json.loads((REPO / "families" / "index.json").read_text())
            position = next(i for i, t in enumerate(original["tasks"]) if t["directory"] == source.name)
            for case in ("missing alias", "duplicate task", "wrong directory", "wrong family", "wrong domain"):
                with self.subTest(case):
                    index = copy.deepcopy(original)
                    task = index["tasks"][position]
                    if case == "missing alias":
                        task["instances"].pop(next(iter(task["instances"])))
                    elif case == "duplicate task":
                        index["tasks"].append(copy.deepcopy(task))
                    elif case == "wrong directory":
                        task["directory"] = "../outside"
                    elif case == "wrong family":
                        task["instances"][next(iter(task["instances"]))] = "heldout-v99-other"
                    else:
                        task["id"] = "MRS-99"
                        task["directory"] = "mrs-99-wrong-domain"
                        task["instances"] = {
                            f"MRS-99-{i:02d}": name for i, name in enumerate(task["instances"].values(), 1)
                        }
                    (root / "index.json").write_text(json.dumps(index))
                    with self.assertRaises(metadata.MetadataError):
                        metadata.build(family)


@unittest.skipIf(jsonschema is None, "jsonschema is not installed (pip install -r requirements-dev.txt)")
class FamilySchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(cls.schema)
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_every_family_json_is_valid(self) -> None:
        for path in family_files():
            with self.subTest(family=path.parent.name):
                errors = [e.message for e in self.validator.iter_errors(json.loads(path.read_text(encoding="utf-8")))]
                self.assertEqual(errors, [])

    def test_schema_rejects_bad_metadata(self) -> None:
        good = json.loads(family_files()[0].read_text(encoding="utf-8"))
        self.assertTrue(self.validator.is_valid(good))
        bad = {
            "missing field": lambda d: d.pop("grader"),
            "unknown field": lambda d: d.update(extra=1),
            "unknown domain": lambda d: d.update(domain="xray"),
            "invalid public ID": lambda d: d.update(public_id="v4-t2epg"),
            "unsafe directory": lambda d: d.update(directory="../outside"),
            "invalid instance alias": lambda d: d["instance_aliases"].update(unknown="heldout-v4-t2epg"),
            "duplicate check": lambda d: d["checks"].append(d["checks"][0]),
            "time cap in minutes": lambda d: d.update(time_cap_s=60.5),
            "no outputs": lambda d: d["example"].update(required_outputs=[]),
        }
        for label, edit in bad.items():
            with self.subTest(label):
                data = copy.deepcopy(good)
                edit(data)
                self.assertFalse(self.validator.is_valid(data))


if __name__ == "__main__":
    unittest.main()
