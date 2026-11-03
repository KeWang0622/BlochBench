"""The instance catalog: every public instance listed in families/<family>/instances.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .common import MrabError

REPO = Path(__file__).resolve().parents[1]
FAMILIES_DIR = REPO / "families"


def load_task_index(root: Path) -> dict[str, dict]:
    """Read the explicit public labels without changing frozen evaluation identities.

    Small external/test catalogues may omit index.json and retain their existing names.
    A supplied index must cover every family and instance exactly once.
    """
    path = root / "index.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        if set(raw) != {"version", "tasks"} or raw["version"] != 1 or not isinstance(raw["tasks"], list):
            raise ValueError("expected version 1 and a tasks list")
        by_directory = {}
        family_ids, legacy_ids, aliases, instances = set(), set(), set(), set()
        for task in raw["tasks"]:
            if set(task) != {"id", "legacy_id", "directory", "instances"}:
                raise ValueError("unexpected task fields")
            fid, legacy, directory = task["id"], task["legacy_id"], task["directory"]
            if not isinstance(fid, str) or not re.fullmatch(r"[A-Z]+-[0-9]{2}", fid):
                raise ValueError("invalid public task ID")
            if not isinstance(legacy, str) or not legacy or legacy in legacy_ids or fid in family_ids:
                raise ValueError("duplicate or empty task identity")
            if (
                not isinstance(directory, str)
                or not re.fullmatch(re.escape(fid.lower()) + r"-[a-z0-9]+(?:-[a-z0-9]+)*", directory)
                or directory in by_directory
            ):
                raise ValueError("invalid or duplicate family directory")
            mapping = task["instances"]
            if not isinstance(mapping, dict) or not mapping:
                raise ValueError("missing instance aliases")
            for alias, instance in mapping.items():
                if not re.fullmatch(re.escape(fid) + r"-[0-9]{2}", alias) or alias in aliases:
                    raise ValueError("invalid or duplicate instance alias")
                if not isinstance(instance, str) or not instance or instance in instances:
                    raise ValueError("duplicate or empty legacy instance")
                aliases.add(alias)
                instances.add(instance)
            listing = json.loads((root / directory / "instances.json").read_text())
            if len(mapping) != len(listing) or set(mapping.values()) != {row["instance"] for row in listing}:
                raise ValueError("instance aliases do not match frozen catalogue")
            family_ids.add(fid)
            legacy_ids.add(legacy)
            by_directory[directory] = task
        if set(by_directory) != {p.parent.name for p in root.glob("*/instances.json")}:
            raise ValueError("task index does not cover the family directories")
        if aliases & instances or family_ids & legacy_ids:
            raise ValueError("public and legacy identities collide")
        return by_directory
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise MrabError(f"invalid task index {path}: {exc}") from exc


def load_catalog(families_dir: Path | None = None) -> dict[str, dict]:
    """Map instance name to its catalog entry, with the family name added under "family".

    Families are read in sorted order, so the result is ordered by family and then by the order in instances.json.
    """
    root = families_dir or FAMILIES_DIR
    task_index = load_task_index(root)
    catalog: dict[str, dict] = {}
    for listing in sorted(root.glob("*/instances.json")):
        task = task_index.get(listing.parent.name)
        aliases = {legacy: public for public, legacy in task["instances"].items()} if task else {}
        for entry in json.loads(listing.read_text()):
            entry["family"] = task["legacy_id"] if task else listing.parent.name
            if task:
                entry["public_family"] = task["id"]
                entry["public_instance"] = aliases[entry["instance"]]
                entry["family_directory"] = task["directory"]
            catalog[entry["instance"]] = entry
    return catalog


def get_instance(name: str) -> dict:
    """Return the catalog entry of one instance, or raise MrabError if it is unknown."""
    catalog = load_catalog()
    if name in catalog:
        return catalog[name]
    for entry in catalog.values():
        if entry.get("public_instance") == name.upper():
            return entry
    raise MrabError(f"unknown instance {name}; see mrab list")


def families() -> dict[str, list[dict]]:
    """Group catalog entries by family, keeping catalog order."""
    grouped: dict[str, list[dict]] = {}
    for entry in load_catalog().values():
        grouped.setdefault(entry["family"], []).append(entry)
    return grouped


def family_line(family: str, entries: list[dict], *, legacy: bool = False) -> str:
    """One line of mrab list: family, domain, time cap and instance names."""
    first = entries[0]
    if first.get("public_family") and not legacy:
        names = ", ".join(e["public_instance"] for e in entries)
        label = first["family_directory"][len(first["public_family"]) + 1 :].replace("-", " ")
        return f"{first['public_family']:9s} {label:26s} cap {first['cap_s'] // 60:3d} min  instances: {names}"
    names = ", ".join(e["instance"] for e in entries)
    return f"{family:20s} {first['domain']:6s} cap {first['cap_s'] // 60:3d} min  instances: {names}"
