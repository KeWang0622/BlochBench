"""Add-on packages for tests."""

from __future__ import annotations

import json
from pathlib import Path

DEMO_SKILL = "---\nname: demo-skill\ndescription: Use for demos.\n---\n# Demo\n\nSay hello.\n"


def manifest(**overrides: object) -> dict:
    data = dict(
        name="demo",
        version="1.0",
        description="Demo add-on",
        homepage="https://example.org/demo",
        license="MIT",
        authors=["A. Author"],
        hosts=["codex", "claude"],
        exposure={"public_instances_seen": False, "details": ""},
    )
    data.update(overrides)
    return data


def make_addon(
    root: Path,
    folder_name: str = "addon",
    skills: dict[str, str] | None = None,
    agents_md: bool = True,
    **overrides: object,
) -> Path:
    """Write an add-on package under root/name; returns its path."""
    folder = root / folder_name
    (folder / "skills").mkdir(parents=True)
    (folder / "addon.json").write_text(json.dumps(manifest(**overrides), indent=1))
    for skill, text in (skills if skills is not None else {"demo-skill": DEMO_SKILL}).items():
        (folder / "skills" / skill).mkdir()
        (folder / "skills" / skill / "SKILL.md").write_text(text)
    if agents_md:
        (folder / "AGENTS.md").write_text("Read the skills in your skills folder.\n")
    return folder
