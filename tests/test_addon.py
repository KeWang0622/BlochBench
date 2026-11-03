"""Tests for add-on packages: manifest schema, SKILL.md front matter, links, size, hashing, host-level skills.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from addon_fixtures import DEMO_SKILL, make_addon, manifest
from toy import REPO, run_cli

from mragentbench import addon as addons

MINIMAL = REPO / "examples" / "addons" / "minimal"


def skill(name: str = "demo-skill", **fields: str) -> str:
    front = {"name": name, "description": "Use for demos."} | fields
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in front.items()) + "---\nBody\n"


class ExampleAndSchemaTest(unittest.TestCase):
    def test_minimal_example_is_valid(self) -> None:
        report = addons.validate_addon(MINIMAL)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.skills, ["deliverable-check"])
        self.assertEqual(sorted(report.files), ["AGENTS.md", "addon.json", "skills/deliverable-check/SKILL.md"])
        self.assertEqual(report.not_installed, ["README.md"])
        code, out, _ = run_cli(["addon", "validate", str(MINIMAL)])
        self.assertEqual(code, 0)
        self.assertIn(f"content sha256 {report.content_sha256}\nvalid\n", out)
        self.assertEqual(run_cli(["addon", "hash", str(MINIMAL)])[1], report.content_sha256 + "\n")

    def test_published_schema_matches_the_code(self) -> None:
        published = json.loads((REPO / "schemas" / "addon.schema.json").read_text())
        self.assertEqual(published, addons.ADDON_SCHEMA)
        example = json.loads((MINIMAL / "addon.json").read_text())
        self.assertEqual(addons.schema_errors(example, published), [])
        self.assertEqual(json.loads(run_cli(["addon", "schema"])[1]), published)


class ManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mrab-addon-"))

    def errors(self, **overrides: object) -> list[str]:
        folder = make_addon(self.tmp, folder_name=f"a{len(list(self.tmp.iterdir()))}", **overrides)
        return addons.validate_addon(folder).errors

    def assert_rejected(self, expected: str, **overrides: object) -> None:
        errors = self.errors(**overrides)
        self.assertTrue(any(expected in e for e in errors), f"{expected!r} not in {errors}")

    def test_valid(self) -> None:
        self.assertEqual(self.errors(), [])
        exposure = {"public_instances_seen": "partial", "details": "families v4-* during development"}
        self.assertEqual(self.errors(hosts=["claude"], exposure=exposure), [])

    def test_bad_fields(self) -> None:
        self.assert_rejected("hosts[1]: must be one of", hosts=["codex", "gemini"])
        self.assert_rejected("hosts: needs at least 1 item", hosts=[])
        self.assert_rejected("hosts: items must be unique", hosts=["codex", "codex"])
        self.assert_rejected(
            'public_instances_seen: must be one of true, false, "partial"',
            exposure={"public_instances_seen": "yes", "details": "x"},
        )
        self.assert_rejected(
            "public_instances_seen: must be one of", exposure={"public_instances_seen": 1, "details": ""}
        )
        self.assert_rejected("exposure.details: say which", exposure={"public_instances_seen": True, "details": " "})
        self.assert_rejected("missing required field 'details'", exposure={"public_instances_seen": False})
        self.assert_rejected("unknown field 'skills_url'", skills_url="https://example.org")
        self.assert_rejected("name: 'my addon' does not match", name="my addon")
        self.assert_rejected("name: 'demo\\n' does not match", name="demo\n")
        self.assert_rejected("version: '1.0+build' does not match", version="1.0+build")
        self.assert_rejected("homepage: 'ftp://x' does not match", homepage="ftp://x")
        self.assert_rejected("authors: must be of type array", authors="A. Author")
        self.assert_rejected("description: longer than 1024", description="x" * 1025)
        self.assert_rejected("description: must not be empty", description="")

    def test_missing_field_and_bad_json(self) -> None:
        folder = make_addon(self.tmp)
        data = manifest()
        del data["license"]
        (folder / "addon.json").write_text(json.dumps(data))
        self.assertIn("addon.json: missing required field 'license'", addons.validate_addon(folder).errors)
        (folder / "addon.json").write_text("{not json")
        self.assertTrue(addons.validate_addon(folder).errors[0].startswith("addon.json: not valid JSON"))
        (folder / "addon.json").unlink()
        self.assertIn("addon.json: missing", addons.validate_addon(folder).errors)


class SkillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mrab-skill-"))

    def assert_rejected(self, expected: str, skills: dict[str, str]) -> None:
        folder = make_addon(self.tmp, folder_name=f"a{len(list(self.tmp.iterdir()))}", skills=skills)
        errors = addons.validate_addon(folder).errors
        self.assertTrue(any(expected in e for e in errors), f"{expected!r} not in {errors}")

    def test_front_matter_rules(self) -> None:
        self.assert_rejected("must match the folder name 'demo-skill'", {"demo-skill": skill("other-skill")})
        self.assert_rejected("lowercase letters", {"Demo": skill("Demo")})
        self.assert_rejected("lowercase letters", {"a--b": skill("a--b")})
        self.assert_rejected("lowercase letters", {"-ab": skill("-ab")})
        self.assert_rejected("lowercase letters", {"a" * 65: skill("a" * 65)})
        self.assert_rejected("non-empty description", {"demo-skill": "---\nname: demo-skill\n---\n"})
        self.assert_rejected("description longer than 1024", {"demo-skill": skill(description="x" * 1025)})
        self.assert_rejected("compatibility must be a string of 1-500", {"demo-skill": skill(compatibility="y" * 501)})
        self.assert_rejected("metadata must be a mapping", {"demo-skill": skill(metadata="text")})
        self.assert_rejected("must start with YAML front matter", {"demo-skill": "# Demo\n"})
        self.assert_rejected("not closed", {"demo-skill": "---\nname: demo-skill\ndescription: d\n"})
        self.assert_rejected("quote the value", {"demo-skill": skill(description="Use when: demos")})
        self.assert_rejected("duplicate field", {"demo-skill": "---\nname: demo-skill\nname: x\ndescription: d\n---\n"})

    def test_folder_rules(self) -> None:
        folder = make_addon(self.tmp, folder_name="empty-skill")
        (folder / "skills" / "demo-skill" / "SKILL.md").unlink()
        self.assertIn("skills/demo-skill: missing SKILL.md", addons.validate_addon(folder).errors)
        folder = make_addon(self.tmp, folder_name="none", skills={})
        self.assertIn("skills/: no skill folders", addons.validate_addon(folder).errors)
        folder = make_addon(self.tmp, folder_name="loose-file")
        (folder / "skills" / "notes.md").write_text("x")
        self.assertIn("skills/notes.md: skills/ may only hold skill folders", addons.validate_addon(folder).errors)
        folder = make_addon(self.tmp, folder_name="no-skills-dir")
        shutil.rmtree(folder / "skills")
        self.assertTrue(any(e.startswith("skills/: missing") for e in addons.validate_addon(folder).errors))

    def test_warnings_do_not_invalidate(self) -> None:
        text = "---\nname: demo-skill\ndescription: d\ndisable-model-invocation: true\nmetadata:\n  version: 1.0\n---\n"
        report = addons.validate_addon(make_addon(self.tmp, skills={"demo-skill": text + "line\n" * 501}))
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 3, report.warnings)

    def test_links_and_size(self) -> None:
        folder = make_addon(self.tmp, folder_name="link-file")
        os.symlink("/etc/hosts", folder / "skills" / "demo-skill" / "hosts.txt")
        self.assertIn("skills/demo-skill/hosts.txt: links are not allowed", addons.validate_addon(folder).errors)
        folder = make_addon(self.tmp, folder_name="link-dir")
        os.symlink(MINIMAL / "skills" / "deliverable-check", folder / "skills" / "deliverable-check")
        self.assertIn("skills/deliverable-check: links are not allowed", addons.validate_addon(folder).errors)
        folder = make_addon(self.tmp, folder_name="link-pointer", agents_md=False)
        os.symlink(MINIMAL / "AGENTS.md", folder / "AGENTS.md")
        self.assertIn("AGENTS.md: links are not allowed", addons.validate_addon(folder).errors)
        folder = make_addon(self.tmp, folder_name="big")
        errors = addons.validate_addon(folder, max_bytes=100).errors
        self.assertTrue(any("the limit is" in e for e in errors), errors)
        self.assertTrue(any("more than 1 files" in e for e in addons.validate_addon(folder, max_files=1).errors))


class FrontMatterTest(unittest.TestCase):
    def test_yaml_subset(self) -> None:
        text = (
            "---\n"
            "# comment\n"
            "name: demo-skill\n"
            "description: >-\n"
            "  Folded text that spans\n"
            '  two lines (with \x60code\x60, quotes "x" and a colon:no-space).\n'
            "\n"
            "  New paragraph.\n"
            "license: 'Apache-2.0 (see ''LICENSE'')'\n"
            'compatibility: "Needs Python \\u2265 3.10"\n'
            "allowed-tools: Bash(git:*) Read  # trailing comment\n"
            "metadata:\n"
            "  author: Example Org\n"
            '  version: "1.0"\n'
            "notes: |\n"
            "  line one\n"
            "    indented\n"
            "flow: {a: 1, b: two}\n"
            "items:\n"
            "  - one\n"
            "  - 2\n"
            "plain: continued\n"
            "  on the next line\n"
            "empty:\n"
            "---\n"
            "Body\n"
        )
        fields, body = addons.parse_front_matter(text)
        self.assertEqual(
            fields,
            {
                "name": "demo-skill",
                "description": "Folded text that spans two lines "
                '(with \x60code\x60, quotes "x" and a colon:no-space).\nNew paragraph.',
                "license": "Apache-2.0 (see 'LICENSE')",
                "compatibility": "Needs Python \u2265 3.10",
                "allowed-tools": "Bash(git:*) Read",
                "metadata": {"author": "Example Org", "version": "1.0"},
                "notes": "line one\n  indented\n",
                "flow": {"a": 1, "b": "two"},
                "items": ["one", 2],
                "plain": "continued on the next line",
                "empty": None,
            },
        )
        self.assertEqual(body, "Body")

    def test_rejects_unsupported_yaml(self) -> None:
        for bad in ("name: &anchor x", "name: *alias", "a:\n  b:\n    c: d", "  indented: x", "just text"):
            with self.subTest(bad=bad), self.assertRaises(addons.FrontMatterError):
                addons.parse_front_matter(f"---\n{bad}\n---\n")


class HashTest(unittest.TestCase):
    def test_hash_covers_installed_content_only(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mrab-hash-"))
        folder = make_addon(tmp)
        first = addons.validate_addon(folder).content_sha256
        (folder / "README.md").write_text("not installed")
        (folder / "skills" / "demo-skill" / "__pycache__").mkdir()
        (folder / "skills" / "demo-skill" / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\0")
        (folder / "skills" / "demo-skill" / ".DS_Store").write_bytes(b"\0")
        self.assertEqual(addons.validate_addon(folder).content_sha256, first)
        moved = tmp / "moved"
        shutil.copytree(folder, moved)
        self.assertEqual(addons.validate_addon(moved).content_sha256, first)
        (folder / "skills" / "demo-skill" / "SKILL.md").write_text(DEMO_SKILL + "More.\n")
        second = addons.validate_addon(folder).content_sha256
        self.assertNotEqual(second, first)
        (folder / "AGENTS.md").write_text("Changed pointer.\n")
        self.assertNotIn(addons.validate_addon(folder).content_sha256, (first, second))
        self.assertIsNone(addons.validate_addon(make_addon(tmp, folder_name="bad", hosts=[])).content_sha256)

    def test_hash_covers_the_executable_bit(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mrab-mode-"))
        hashes = []
        for name, mode in (("a", 0o755), ("b", 0o644)):  # the reviewer's modetest/a and modetest/b
            folder = make_addon(tmp, folder_name=name)
            script = folder / "skills" / "demo-skill" / "scripts" / "run.sh"
            script.parent.mkdir()
            script.write_text("#!/bin/sh\necho ok\n")
            script.chmod(mode)
            report = addons.validate_addon(folder)
            self.assertTrue(report.files["skills/demo-skill/scripts/run.sh"].endswith(" x" if mode & 0o100 else " -"))
            hashes.append(report.content_sha256)
        self.assertNotEqual(hashes[0], hashes[1])
        (tmp / "b" / "skills" / "demo-skill" / "scripts" / "run.sh").chmod(0o664)  # group/other bits do not count
        self.assertEqual(addons.validate_addon(tmp / "b").content_sha256, hashes[1])


class HostSkillsTest(unittest.TestCase):
    def test_detects_user_level_skill_folders(self) -> None:
        home = Path(tempfile.mkdtemp(prefix="mrab-home-")).resolve()
        self.assertEqual(addons.find_host_skills(home=home, environ={}), [])
        (home / ".codex" / "skills" / ".system" / "builtin").mkdir(parents=True)
        (home / ".agents" / "skills").mkdir(parents=True)
        self.assertEqual(addons.find_host_skills(home=home, environ={}), [])
        (home / ".agents" / "skills" / "mine").mkdir()
        (home / ".claude" / "skills" / "other").mkdir(parents=True)
        found = addons.find_host_skills(home=home, environ={})
        self.assertEqual(
            [(f["path"], f["entries"]) for f in found],
            [(str(home / ".agents" / "skills"), ["mine"]), (str(home / ".claude" / "skills"), ["other"])],
        )
        for sub in ("commands", "agents"):  # Claude Code slash commands and subagents
            (home / ".claude" / sub / "x.md").parent.mkdir(parents=True)
            (home / ".claude" / sub / "x.md").write_text("x")
        paths = [f["path"] for f in addons.find_host_skills(home=home, environ={})]
        self.assertIn(str(home / ".claude" / "commands"), paths)
        self.assertIn(str(home / ".claude" / "agents"), paths)
        codex_home = home / "custom-codex"
        (codex_home / "skills" / "x").mkdir(parents=True)
        found = addons.find_host_skills(home=home, environ={"CODEX_HOME": str(codex_home)})
        self.assertIn(str(codex_home / "skills"), [f["path"] for f in found])
        self.assertIn("would not be clean", addons.host_skills_message(found))

    def test_detects_project_skills_above_the_runs_folder(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="mrab-proj-")).resolve()
        (root / ".claude" / "skills" / "p").mkdir(parents=True)
        found = addons.find_host_skills(home=root / "home", environ={}, search_from=root / "a" / "runs")
        self.assertEqual([f["path"] for f in found], [str(root / ".claude" / "skills")])

    def test_system_folders_plugins_and_instruction_files(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="mrab-host-")).resolve()
        home, etc = root / "home", root / "etc"
        system = (etc / "codex" / "skills", etc / "claude-code" / ".claude" / "skills")
        self.assertEqual(addons.find_host_skills(home=home, environ={}, system_dirs=system), [])
        (system[0] / "admin-skill").mkdir(parents=True)
        found = addons.find_host_skills(home=home, environ={}, system_dirs=system)
        self.assertEqual(found, [{"path": str(system[0]), "entries": ["admin-skill"]}])
        config = root / "claude-config"
        (config / "plugins").mkdir(parents=True)
        (config / "plugins" / "installed_plugins.json").write_text('{"plugins": {"b@m": [], "a@m": []}}')
        found = addons.find_host_skills(home=home, environ={"CLAUDE_CONFIG_DIR": str(config)}, system_dirs=())
        self.assertEqual(
            found, [{"path": str(config / "plugins" / "installed_plugins.json"), "entries": ["a@m", "b@m"]}]
        )

        runs = root / "repo" / "sub" / "runs"
        self.assertEqual(addons.find_host_instructions(home=home, environ={}, search_from=runs, system_files=()), [])
        files = [
            home / ".codex" / "AGENTS.md",
            root / "codex-home" / "AGENTS.override.md",
            home / ".claude" / "CLAUDE.md",
            root / "repo" / "CLAUDE.local.md",
            root / "repo" / "sub" / ".claude" / "AGENTS.md",
            etc / "claude-code" / "CLAUDE.md",
        ]
        for path in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("instructions\n")
        (root / "repo" / "AGENTS.md").write_text("")  # empty: not read
        (home / ".claude" / "rules").mkdir()
        (home / ".claude" / "rules" / "style.md").write_text("rule\n")
        found = addons.find_host_instructions(
            home=home, environ={"CODEX_HOME": str(root / "codex-home")}, search_from=runs, system_files=(files[-1],)
        )
        self.assertEqual(sorted(found), sorted(map(str, files + [home / ".claude" / "rules"])))
        self.assertIsNone(addons.find_repository(runs))
        (root / "repo" / ".git").write_text("gitdir: elsewhere\n")  # a worktree has a .git file
        self.assertEqual(addons.find_repository(runs), str(root / "repo"))
        context = addons.find_host_context(home=home, environ={}, runs_root=runs)
        self.assertFalse(context.clean)
        self.assertEqual(context.repository, str(root / "repo"))
        message = addons.host_context_message(context)
        self.assertIn("inside the Git repository", message)
        self.assertIn(f"  {root / 'repo' / 'CLAUDE.local.md'}", message)


class InstallTest(unittest.TestCase):
    def test_install_keeps_modes_and_checks_hashes(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mrab-install-"))
        folder = make_addon(tmp)
        script = folder / "skills" / "demo-skill" / "scripts" / "run.py"
        script.parent.mkdir()
        script.write_text("print('ok')\n")
        script.chmod(0o755)
        report = addons.validate_addon(folder)
        work = tmp / "work"
        work.mkdir()
        install = addons.install_addon(report, work, "claude")
        installed = work / ".claude" / "skills" / "demo-skill" / "scripts" / "run.py"
        self.assertTrue(os.access(installed, os.X_OK))
        self.assertEqual((install["pointer"], install["skills_dir"]), ("CLAUDE.md", ".claude/skills"))
        self.assertTrue(addons.check_install(work, install)["intact"])
        installed.chmod(0o644)
        check = addons.check_install(work, install)
        self.assertEqual((check["intact"], check["changed"]), (False, ["demo-skill/scripts/run.py"]))
        (work / "CLAUDE.md").write_text("changed\n")
        installed.unlink()
        check = addons.check_install(work, install)
        self.assertEqual(
            (check["intact"], check["pointer_intact"], check["removed"]), (False, False, ["demo-skill/scripts/run.py"])
        )


class ValidateCommandTest(unittest.TestCase):
    def test_reports_errors(self) -> None:
        folder = make_addon(
            Path(tempfile.mkdtemp(prefix="mrab-cli-")), hosts=["gemini"], skills={"demo-skill": skill("wrong")}
        )
        code, out, _ = run_cli(["addon", "validate", str(folder)])
        self.assertEqual(code, 1)
        self.assertIn("error: addon.json.hosts[0]: must be one of", out)
        self.assertTrue(out.endswith("invalid: 2 error(s)\n"), out)
        self.assertNotIn("content sha256", out)
        code, out, _ = run_cli(["addon", "validate", str(folder), "--json"])
        self.assertEqual((code, json.loads(out)["valid"], json.loads(out)["content_sha256"]), (1, False, None))
        code, _, err = run_cli(["addon", "hash", str(folder)])
        self.assertEqual(code, 1)
        self.assertIn("invalid add-on", err)


if __name__ == "__main__":
    unittest.main()
