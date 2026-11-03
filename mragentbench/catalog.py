"""The instance catalog: every public instance listed in families/<family>/instances.json."""

from __future__ import annotations

import json
from pathlib import Path

from .common import MrabError

REPO = Path(__file__).resolve().parents[1]
FAMILIES_DIR = REPO / "families"


def load_catalog(families_dir: Path | None = None) -> dict[str, dict]:
    """Map instance name to its catalog entry, with the family name added under "family".

    Families are read in sorted order, so the result is ordered by family and then by the order in instances.json.
    """
    root = families_dir or FAMILIES_DIR
    catalog: dict[str, dict] = {}
    for listing in sorted(root.glob("*/instances.json")):
        for entry in json.loads(listing.read_text()):
            entry["family"] = listing.parent.name
            catalog[entry["instance"]] = entry
    return catalog


def get_instance(name: str) -> dict:
    """Return the catalog entry of one instance, or raise MrabError if it is unknown."""
    catalog = load_catalog()
    if name not in catalog:
        raise MrabError(f"unknown instance {name}; see mrab list")
    return catalog[name]


def families() -> dict[str, list[dict]]:
    """Group catalog entries by family, keeping catalog order."""
    grouped: dict[str, list[dict]] = {}
    for entry in load_catalog().values():
        grouped.setdefault(entry["family"], []).append(entry)
    return grouped


def family_line(family: str, entries: list[dict]) -> str:
    """One line of mrab list: family, domain, time cap and instance names."""
    first = entries[0]
    names = ", ".join(e["instance"] for e in entries)
    return f"{family:20s} {first['domain']:6s} cap {first['cap_s'] // 60:3d} min  instances: {names}"
