"""Add-on packages: a skill library that BlochBench measures by pairing runs with and without it.

Layout of an add-on package (docs/EVALUATE-YOUR-SKILLS.md):

    addon.json                  manifest, validated against ADDON_SCHEMA (published as schemas/addon.schema.json)
    skills/<skill>/SKILL.md     one folder per skill in the Agent Skills format (https://agentskills.io/specification)
    skills/<skill>/...          optional scripts/, references/, assets/
    AGENTS.md                   optional pointer, placed at the root of the add-on arm's workspace

Only addon.json, AGENTS.md and skills/ belong to the package: they are hashed and installed. Other files (README,
LICENSE, tests) are allowed and ignored. Links are refused in the installed part.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import MrabError, sha256_file

HOSTS = ("codex", "claude")
# Project skill folders inside the working directory: Codex reads .agents/skills, Claude Code reads .claude/skills.
SKILL_DIRS = {"codex": ".agents/skills", "claude": ".claude/skills", "cmd": ".agents/skills"}
# Instruction file each host reads from the working directory; the add-on's AGENTS.md is installed under this name.
POINTER_FILES = {"codex": "AGENTS.md", "claude": "CLAUDE.md", "cmd": "AGENTS.md"}
MAX_BYTES = 25 * 1024 * 1024
MAX_FILES = 2000
MAX_POINTER_BYTES = 32 * 1024  # Codex reads at most this much of AGENTS.md by default
MAX_SKILL_LINES = 500  # recommended maximum length of SKILL.md (Agent Skills specification)
IGNORED_NAMES = {"__pycache__", ".DS_Store"}
IGNORED_SUFFIXES = (".pyc",)
SKILL_NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
SKILL_FIELDS = ("name", "description", "license", "compatibility", "metadata", "allowed-tools")

ADDON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/KeWang0622/BlochBench/blob/main/schemas/addon.schema.json",
    "title": "BlochBench add-on manifest (addon.json)",
    "description": "Describes a skill library evaluated on BlochBench by paired runs with and without it. "
    "Generated from mragentbench/addon.py (mrab addon schema).",
    "type": "object",
    "required": ["name", "version", "description", "homepage", "license", "authors", "hosts", "exposure"],
    "additionalProperties": False,
    "properties": {
        "$schema": {"type": "string", "maxLength": 500},
        "name": {
            "description": "Add-on name; part of the run configuration name <agent>-<model>+<name>@<version>.",
            "type": "string",
            "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        },
        "version": {
            "description": "Version of the frozen skill set that was evaluated.",
            "type": "string",
            "pattern": "^[0-9A-Za-z][0-9A-Za-z._-]{0,39}$",
        },
        "description": {"type": "string", "minLength": 1, "maxLength": 1024},
        "homepage": {"type": "string", "pattern": "^https?://\\S+$", "maxLength": 500},
        "license": {
            "description": "SPDX identifier or license name.",
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
        },
        "authors": {
            "type": "array",
            "minItems": 1,
            "maxItems": 50,
            "items": {"type": "string", "minLength": 1, "maxLength": 200},
        },
        "hosts": {
            "description": "Agent hosts the add-on supports: codex (skills in .agents/skills) and claude "
            "(Claude Code, skills in .claude/skills).",
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"enum": list(HOSTS)},
        },
        "exposure": {
            "description": "Whether the add-on's authors saw public BlochBench instances while building it.",
            "type": "object",
            "required": ["public_instances_seen", "details"],
            "additionalProperties": False,
            "properties": {
                "public_instances_seen": {"enum": [True, False, "partial"]},
                "details": {"type": "string", "maxLength": 2000},
            },
        },
        "metadata": {
            "description": "Optional extra string fields.",
            "type": "object",
            "maxProperties": 50,
            "additionalProperties": {"type": "string", "maxLength": 500},
        },
    },
}

_TYPES: dict[str, Any] = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def schema_errors(value: Any, schema: Mapping[str, Any], where: str = "addon.json") -> list[str]:
    """Validate a JSON value against the subset of JSON Schema used by ADDON_SCHEMA; returns error messages.

    Supported keywords: type, enum, required, properties, additionalProperties, maxProperties, minLength, maxLength,
    pattern, items, minItems, maxItems, uniqueItems. Annotations ($schema, title, description) are ignored.
    """
    errors: list[str] = []
    expected = schema.get("type")
    if expected and not _TYPES[expected](value):
        return [f"{where}: must be of type {expected}"]
    if "enum" in schema and not any(type(value) is type(e) and value == e for e in schema["enum"]):
        return [f"{where}: must be one of {', '.join(json.dumps(e) for e in schema['enum'])}"]
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: must not be empty" if schema["minLength"] == 1 else f"{where}: too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{where}: longer than {schema['maxLength']} characters")
        if "pattern" in schema:
            pattern = schema["pattern"]
            regex = pattern[:-1] + r"\Z" if pattern.endswith("$") else pattern  # ECMA-262: $ is the end of input
            if not re.search(regex, value):
                errors.append(f"{where}: {value!r} does not match {pattern}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: needs at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{where}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) < len(value):
            errors.append(f"{where}: items must be unique")
        if "items" in schema:
            for i, item in enumerate(value):
                errors += schema_errors(item, schema["items"], f"{where}[{i}]")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required field {key!r}")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errors.append(f"{where}: more than {schema['maxProperties']} fields")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors += schema_errors(item, properties[key], f"{where}.{key}")
            elif extra is False:
                errors.append(f"{where}: unknown field {key!r}")
            elif isinstance(extra, dict):
                errors += schema_errors(item, extra, f"{where}.{key}")
    return errors


# --- SKILL.md front matter -------------------------------------------------------------------------------------------


class FrontMatterError(ValueError):
    """SKILL.md front matter that is missing or outside the supported YAML subset."""


def split_front_matter(text: str) -> tuple[list[str], str]:
    """Split SKILL.md into its front matter lines (between the --- lines) and the Markdown body."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontMatterError("SKILL.md must start with YAML front matter: a line '---', fields, a line '---'")
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            return lines[1:i], "\n".join(lines[i + 1 :])
    raise FrontMatterError("the front matter is not closed by a line '---'")


_KEY_RE = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:(?:\s+(.*)|\s*)$")


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Parse SKILL.md front matter with a small YAML subset; returns (fields, body).

    Supported: top-level "key: value" with plain, single-quoted or double-quoted scalars (plain scalars may continue
    on indented lines), block scalars (| and >, with - or + chomping), one level of nested mapping or list, and
    comments. Anchors, aliases, tags and deeper nesting are reported as errors.
    """
    lines, body = split_front_matter(text)
    fields: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        lineno = i + 2  # line 1 is the opening ---
        if line[0] in " \t":
            raise FrontMatterError(f"front matter line {lineno}: unexpected indentation")
        match = _KEY_RE.match(line)
        if not match:
            raise FrontMatterError(f"front matter line {lineno}: expected 'key: value'")
        key, raw = match.group(1), (match.group(2) or "").strip()
        if key in fields:
            raise FrontMatterError(f"front matter line {lineno}: duplicate field {key!r}")
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or lines[j][0] in " \t"):
            j += 1
        block = lines[i + 1 : j]
        while block and not block[-1].strip():
            block.pop()
        fields[key] = _yaml_value(raw, block, lineno)
        i = j
    return fields, body


def _yaml_value(raw: str, block: list[str], lineno: int) -> Any:
    if raw[:1] in ("|", ">"):
        return _block_scalar(raw, block, lineno)
    if not raw:
        content = [b for b in block if b.strip() and not b.lstrip().startswith("#")]
        if not content:
            return None
        if content[0].lstrip().startswith("-"):
            return _nested_list(content, lineno)
        return _nested_map(content, lineno)
    if block:
        if raw[0] in "\"'{[":
            raw = " ".join([raw] + [b.strip() for b in block])
        else:
            raw = " ".join([_strip_comment(raw)] + [_strip_comment(b.strip()) for b in block if b.strip()])
    return _scalar(raw, lineno)


def _nested_list(content: list[str], lineno: int) -> list[Any]:
    items = []
    for line in content:
        if not line.lstrip().startswith("-"):
            raise FrontMatterError(f"front matter near line {lineno}: mixed list and mapping entries")
        items.append(_scalar(line.lstrip()[1:].strip(), lineno))
    return items


def _nested_map(content: list[str], lineno: int) -> dict[str, Any]:
    indent = len(content[0]) - len(content[0].lstrip())
    result: dict[str, Any] = {}
    for line in content:
        if len(line) - len(line.lstrip()) != indent:
            raise FrontMatterError(f"front matter near line {lineno}: nesting deeper than one level is not supported")
        match = _KEY_RE.match(line.strip())
        if not match or not (match.group(2) or "").strip():
            raise FrontMatterError(f"front matter near line {lineno}: expected 'key: value' in a nested mapping")
        result[match.group(1)] = _scalar(match.group(2).strip(), lineno)
    return result


def _block_scalar(header: str, block: list[str], lineno: int) -> str:
    style, chomp = header[0], ""
    for ch in header[1:]:
        if ch in "+-":
            chomp = ch
        elif ch.isdigit() or ch == " ":
            continue
        elif ch == "#":
            break
        else:
            raise FrontMatterError(f"front matter line {lineno}: bad block scalar header {header!r}")
    content = [b for b in block if b.strip()]
    indent = min((len(b) - len(b.lstrip()) for b in content), default=0)
    lines = [b[indent:] if b.strip() else "" for b in block]
    if style == "|":
        text = "\n".join(lines)
    else:
        parts: list[str] = []
        for line in lines:
            if not line:
                parts.append("\n")
            elif parts and parts[-1] not in ("\n",):
                parts.append(" " + line)
            else:
                parts.append(line)
        text = "".join(parts)
    text = text.rstrip("\n")
    return text if chomp == "-" else text + "\n"


def _strip_comment(raw: str) -> str:
    return raw.split(" #", 1)[0].rstrip()


def _scalar(raw: str, lineno: int) -> Any:
    if not raw:
        return None
    if raw[0] == '"':
        end = _closing_quote(raw)
        if end < 0:
            raise FrontMatterError(f"front matter line {lineno}: unterminated double-quoted string")
        try:
            return json.loads(raw[: end + 1])
        except json.JSONDecodeError:
            return raw[1:end]
    if raw[0] == "'":
        end = raw.find("'", 1)
        while end > 0 and raw[end + 1 : end + 2] == "'":
            end = raw.find("'", end + 2)
        if end < 0:
            raise FrontMatterError(f"front matter line {lineno}: unterminated single-quoted string")
        return raw[1:end].replace("''", "'")
    if raw[0] in "{[":
        return _flow(raw, lineno)
    if raw[0] in "&*!%@\x60|>":
        raise FrontMatterError(f"front matter line {lineno}: {raw[0]!r} cannot start a plain value; quote it")
    value = _strip_comment(raw)
    if ": " in value or value.endswith(":"):
        raise FrontMatterError(f"front matter line {lineno}: a plain value cannot contain ': '; quote the value")
    lowered = value.lower()
    if lowered in ("null", "~"):
        return None
    if lowered in ("true", "false"):
        return lowered == "true"
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", value):
        return float(value)
    return value


def _closing_quote(raw: str) -> int:
    i = 1
    while i < len(raw):
        if raw[i] == "\\":
            i += 2
            continue
        if raw[i] == '"':
            return i
        i += 1
    return -1


def _flow(raw: str, lineno: int) -> Any:
    closing = "}" if raw[0] == "{" else "]"
    if not raw.rstrip().endswith(closing):
        raise FrontMatterError(f"front matter line {lineno}: unterminated flow collection")
    inner = raw.strip()[1:-1].strip()
    items = [p.strip() for p in inner.split(",") if p.strip()] if inner else []
    if closing == "]":
        return [_scalar(p, lineno) for p in items]
    result = {}
    for item in items:
        key, sep, value = item.partition(":")
        if not sep:
            raise FrontMatterError(f"front matter line {lineno}: expected key: value in a flow mapping")
        result[key.strip().strip("\"'")] = _scalar(value.strip(), lineno)
    return result


def check_skill(skill_dir: Path) -> tuple[list[str], list[str], dict[str, Any]]:
    """Check one skill folder against the Agent Skills specification; returns (errors, warnings, front matter)."""
    rel = f"skills/{skill_dir.name}"
    errors: list[str] = []
    warnings: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file() or skill_md.is_symlink():
        return [f"{rel}: missing SKILL.md"], warnings, {}
    try:
        text = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"{rel}/SKILL.md: not UTF-8 text"], warnings, {}
    try:
        meta, body = parse_front_matter(text)
    except FrontMatterError as e:
        return [f"{rel}/SKILL.md: {e}"], warnings, {}
    where = f"{rel}/SKILL.md"
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{where}: front matter needs a name (string)")
    else:
        if len(name) > 64 or not SKILL_NAME_RE.fullmatch(name):
            errors.append(
                f"{where}: name {name!r} must be 1-64 lowercase letters, digits and single hyphens, "
                "not starting or ending with a hyphen"
            )
        if name != skill_dir.name:
            errors.append(f"{where}: name {name!r} must match the folder name {skill_dir.name!r}")
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{where}: front matter needs a non-empty description (string)")
    elif len(description.strip()) > 1024:
        errors.append(f"{where}: description longer than 1024 characters")
    compatibility = meta.get("compatibility")
    if compatibility is not None and (not isinstance(compatibility, str) or not 0 < len(compatibility) <= 500):
        errors.append(f"{where}: compatibility must be a string of 1-500 characters")
    for key in ("license", "allowed-tools"):
        if key in meta and not isinstance(meta[key], str):
            errors.append(f"{where}: {key} must be a string")
    metadata = meta.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            errors.append(f"{where}: metadata must be a mapping of string keys to string values")
        elif any(not isinstance(v, str) for v in metadata.values()):
            warnings.append(f'{where}: metadata values should be strings (quote numbers such as version: "1.0")')
    unknown = sorted(set(meta) - set(SKILL_FIELDS))
    if unknown:
        warnings.append(
            f"{where}: fields outside the Agent Skills specification ({', '.join(unknown)}) "
            "may be ignored by some hosts"
        )
    if len(body.splitlines()) > MAX_SKILL_LINES:
        warnings.append(
            f"{where}: body longer than {MAX_SKILL_LINES} lines (the specification recommends moving "
            "detail into referenced files)"
        )
    return errors, warnings, meta


# --- packages ----------------------------------------------------------------------------------------------------


def _ignored(name: str) -> bool:
    return name in IGNORED_NAMES or name.endswith(IGNORED_SUFFIXES)


def file_entry(path: Path) -> str:
    """The manifest entry of a file: "<sha256> x" if executable, "<sha256> -" otherwise (content and the executable
    bit, the mode that Git keeps)."""
    executable = bool(path.stat().st_mode & stat.S_IXUSR)
    return f"{sha256_file(path)} {'x' if executable else '-'}"


def file_manifest(root: Path) -> dict[str, str]:
    """file_entry of every regular file below root (POSIX relative paths), skipping caches such as __pycache__."""
    manifest = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not _ignored(d))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if _ignored(name) or path.is_symlink() or not path.is_file():
                continue
            manifest[path.relative_to(root).as_posix()] = file_entry(path)
    return dict(sorted(manifest.items()))


def manifest_digest(manifest: Mapping[str, str]) -> str:
    """One SHA-256 over a file manifest: "<sha256> <x|->  <path>" lines in path order (content and executable bit)."""
    text = "".join(f"{entry}  {rel}\n" for rel, entry in sorted(manifest.items()))
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass
class AddonReport:
    """Result of validating an add-on package."""

    root: Path
    manifest: dict[str, Any] | None = None
    skills: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    total_bytes: int = 0
    not_installed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def content_sha256(self) -> str | None:
        """Hash of the installed content (addon.json, AGENTS.md and skills/); None when invalid."""
        return manifest_digest(self.files) if self.ok else None

    @property
    def has_pointer(self) -> bool:
        return "AGENTS.md" in self.files

    def as_dict(self) -> dict[str, Any]:
        return dict(
            path=str(self.root),
            valid=self.ok,
            manifest=self.manifest,
            skills=self.skills,
            files=len(self.files),
            bytes=self.total_bytes,
            agents_md=self.has_pointer,
            not_installed=self.not_installed,
            content_sha256=self.content_sha256,
            errors=self.errors,
            warnings=self.warnings,
        )


def is_package(path: str | Path) -> bool:
    """True when a folder is an add-on package (it holds addon.json)."""
    return (Path(path) / "addon.json").is_file()


def _walk_package(root: Path, report: AddonReport, max_files: int) -> None:
    """Collect the package files (addon.json, AGENTS.md, skills/**), refusing links and special files."""
    members = [root / "addon.json", root / "AGENTS.md"]
    for entry in sorted(root.iterdir()):
        if entry.name not in ("addon.json", "AGENTS.md", "skills") and not _ignored(entry.name):
            report.not_installed.append(entry.name + ("/" if entry.is_dir() else ""))
    for path in members:
        if path.is_symlink():
            report.errors.append(f"{path.name}: links are not allowed")
        elif path.exists() and not path.is_file():
            report.errors.append(f"{path.name}: must be a regular file")
    skills = root / "skills"
    if skills.is_symlink():
        report.errors.append("skills: links are not allowed")
        return
    if not skills.is_dir():
        report.errors.append("skills/: missing (one folder per skill, each with SKILL.md)")
        return
    paths = [p for p in members if p.is_file() and not p.is_symlink()]
    for dirpath, dirnames, filenames in os.walk(skills):
        here = Path(dirpath)
        keep = []
        for name in sorted(dirnames):
            p = here / name
            if p.is_symlink():
                report.errors.append(f"{p.relative_to(root).as_posix()}: links are not allowed")
            elif not _ignored(name):
                keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            p = here / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                report.errors.append(f"{rel}: links are not allowed")
            elif not p.is_file():
                report.errors.append(f"{rel}: not a regular file")
            elif "\n" in rel or "\r" in rel:
                report.errors.append(f"{rel!r}: file names must not contain line breaks")
            elif not _ignored(name):
                paths.append(p)
        if len(paths) > max_files:
            report.errors.append(f"more than {max_files} files in the package")
            return
    for p in paths:
        report.files[p.relative_to(root).as_posix()] = file_entry(p)
        report.total_bytes += p.stat().st_size
    report.files = dict(sorted(report.files.items()))


def validate_addon(path: str | Path, max_bytes: int = MAX_BYTES, max_files: int = MAX_FILES) -> AddonReport:
    """Validate an add-on package: manifest schema, exposure statement, skills, links and size."""
    root = Path(path).resolve()
    report = AddonReport(root=root)
    if not root.is_dir():
        report.errors.append(f"{path}: not a folder")
        return report
    manifest_file = root / "addon.json"
    if not manifest_file.is_file():
        report.errors.append("addon.json: missing")
    elif not manifest_file.is_symlink():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            report.errors.append(f"addon.json: not valid JSON ({e})")
        else:
            report.manifest = manifest
            report.errors += schema_errors(manifest, ADDON_SCHEMA)
            exposure = manifest.get("exposure") if isinstance(manifest, dict) else None
            if isinstance(exposure, dict) and exposure.get("public_instances_seen") is not False:
                details = exposure.get("details")
                if isinstance(details, str) and not details.strip():
                    report.errors.append(
                        "addon.json.exposure.details: say which public instances or families the "
                        "authors saw (required unless public_instances_seen is false)"
                    )
    _walk_package(root, report, max_files)
    skills_dir = root / "skills"
    if skills_dir.is_dir() and not skills_dir.is_symlink():
        for entry in sorted(skills_dir.iterdir()):
            if _ignored(entry.name) or entry.is_symlink():
                continue
            if not entry.is_dir():
                report.errors.append(f"skills/{entry.name}: skills/ may only hold skill folders")
                continue
            errors, warnings, _ = check_skill(entry)
            report.errors += errors
            report.warnings += warnings
            report.skills.append(entry.name)
        if not report.skills:
            report.errors.append("skills/: no skill folders")
    if report.total_bytes > max_bytes:
        report.errors.append(f"package is {report.total_bytes / 1e6:.1f} MB; the limit is {max_bytes / 1e6:.1f} MB")
    pointer = root / "AGENTS.md"
    if pointer.is_file() and not pointer.is_symlink() and pointer.stat().st_size > MAX_POINTER_BYTES:
        report.warnings.append(
            f"AGENTS.md is larger than {MAX_POINTER_BYTES // 1024} KiB; Codex reads only the first 32 KiB"
        )
    return report


def load_valid_addon(path: str | Path) -> AddonReport:
    """Validate an add-on package or raise MrabError listing every problem."""
    report = validate_addon(path)
    if not report.ok:
        problems = "\n".join(f"  {e}" for e in report.errors)
        raise MrabError(f"invalid add-on {path} (see mrab addon validate):\n{problems}")
    return report


def addon_label(manifest: Mapping[str, Any]) -> str:
    """name@version, used in configuration names such as codex-gpt-6+MRFoundry@0.14.0."""
    return f"{manifest['name']}@{manifest['version']}"


def pointer_suffix(report: AddonReport, agents_md: bool) -> str:
    """Configuration-name suffix of an add-on arm run without the add-on's AGENTS.md (pointer) installed."""
    return ",no-agents-md" if report.has_pointer and not agents_md else ""


def installed_digest(install: Mapping[str, Any]) -> str:
    """One SHA-256 over what was installed in a workspace: the skills and, when installed, the pointer file."""
    files = {f"skills/{rel}": entry for rel, entry in install["installed_sha256"].items()}
    if install.get("pointer"):
        files["AGENTS.md"] = install["pointer_sha256"]
    return manifest_digest(files)


def check_host(manifest: Mapping[str, Any], agent: str) -> None:
    """Refuse an agent host that the add-on does not declare (cmd agents are not checked)."""
    hosts = manifest.get("hosts") or []
    if agent != "cmd" and agent not in hosts:
        raise MrabError(f"the add-on declares hosts {', '.join(hosts)}; it does not support {agent}")


def manifest_record(report: AddonReport) -> dict[str, Any]:
    """The manifest plus its content hash, as stored in run records and hosted submissions."""
    return dict(report.manifest or {}, content_sha256=report.content_sha256)


# --- installing into a workspace ----------------------------------------------------------------------------------


def install_addon(report: AddonReport, work: Path, host: str, agents_md: bool = True) -> dict[str, Any]:
    """Copy the skills into the host's project skills folder of a workspace, and AGENTS.md if asked.

    Returns the install record, including the SHA-256 of every installed file for the check after the run.
    """
    skills_rel = SKILL_DIRS[host]
    dest = work / skills_rel
    if dest.exists():
        raise MrabError(f"{dest} already exists in the fresh workspace")
    for rel in report.files:
        if rel.startswith("skills/"):
            target = dest / rel[len("skills/") :]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(report.root / rel, target)
            shutil.copymode(report.root / rel, target)  # scripts/ may be run directly
    pointer = None
    if agents_md and report.has_pointer:
        pointer = POINTER_FILES[host]
        if (work / pointer).exists():
            raise MrabError(f"{work / pointer} already exists in the fresh workspace")
        shutil.copyfile(report.root / "AGENTS.md", work / pointer)
        shutil.copymode(report.root / "AGENTS.md", work / pointer)
    installed = file_manifest(dest)
    expected = {rel[len("skills/") :]: digest for rel, digest in report.files.items() if rel.startswith("skills/")}
    if installed != expected:
        raise MrabError("installed skills differ from the validated add-on; was it changed during installation?")
    return dict(
        host=host,
        skills_dir=skills_rel,
        skills=report.skills,
        pointer=pointer,
        pointer_sha256=report.files.get("AGENTS.md") if pointer else None,
        installed_sha256=installed,
    )


def check_install(work: Path, install: Mapping[str, Any]) -> dict[str, Any]:
    """Compare the installed add-on after a run with the hashes recorded at installation."""
    before: dict[str, str] = install["installed_sha256"]
    after = file_manifest(work / install["skills_dir"])
    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    pointer_intact = True
    if install.get("pointer"):
        p = work / install["pointer"]
        pointer_intact = p.is_file() and not p.is_symlink() and file_entry(p) == install["pointer_sha256"]
    return dict(
        intact=not (changed or added or removed) and pointer_intact,
        changed=changed,
        added=added,
        removed=removed,
        pointer_intact=pointer_intact,
    )


# --- host-level skills and instructions -------------------------------------------------------------------------

# System-wide skill folders: Codex's admin folder and Claude Code's managed folder on Linux.
SYSTEM_SKILL_DIRS: tuple[Path, ...] = (Path("/etc/codex/skills"), Path("/etc/claude-code/.claude/skills"))
# Organisation-wide instruction file of Claude Code on Linux.
SYSTEM_INSTRUCTION_FILES: tuple[Path, ...] = (Path("/etc/claude-code/CLAUDE.md"),)
# Instruction files that Codex (AGENTS.override.md, AGENTS.md) or Claude Code (CLAUDE.md, CLAUDE.local.md,
# .claude/CLAUDE.md and, without a CLAUDE.md, AGENTS.md) read from the working directory and the folders above it.
PROJECT_INSTRUCTION_FILES = (
    "AGENTS.override.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CLAUDE.local.md",
    ".claude/CLAUDE.md",
    ".claude/AGENTS.md",
)


def _homes(home: Path | None, environ: Mapping[str, str] | None) -> tuple[Path, list[Path], list[Path]]:
    """The home folder and the configuration folders of Codex (CODEX_HOME, ~/.codex) and Claude Code."""
    env = os.environ if environ is None else environ
    home = Path(home) if home else Path.home()
    codex = [Path(env["CODEX_HOME"])] if env.get("CODEX_HOME") else []
    claude = [Path(env["CLAUDE_CONFIG_DIR"])] if env.get("CLAUDE_CONFIG_DIR") else []
    return home, codex + [home / ".codex"], claude + [home / ".claude"]


def host_skill_folders(
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    system_dirs: tuple[Path, ...] = SYSTEM_SKILL_DIRS,
) -> list[tuple[Path, set]]:
    """Skill folders that Codex or Claude Code load in every workspace, with entries to ignore."""
    home, codex_homes, claude_homes = _homes(home, environ)
    folders: list[tuple[Path, set]] = [(home / ".agents" / "skills", set())]
    folders += [(c / "skills", {".system"}) for c in codex_homes]  # .system holds the host's built-in skills
    # Claude Code also loads user-level slash commands and subagents, which can carry the same knowledge as skills.
    folders += [(c / sub, set()) for c in claude_homes for sub in ("skills", "commands", "agents")]
    folders += [(d, set()) for d in system_dirs]
    return folders


def _installed_plugins(claude_home: Path) -> list[str]:
    """Claude Code plugins installed for the user (plugins/installed_plugins.json); plugins can bring skills."""
    record = claude_home / "plugins" / "installed_plugins.json"
    try:
        plugins = json.loads(record.read_text()).get("plugins")
    except FileNotFoundError:
        return []
    except (OSError, ValueError, AttributeError):
        return ["(unreadable)"]
    return sorted(plugins) if isinstance(plugins, dict) else []


def find_host_skills(
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    search_from: Path | None = None,
    system_dirs: tuple[Path, ...] = SYSTEM_SKILL_DIRS,
) -> list[dict[str, Any]]:
    """Skill folders outside the workspaces that an agent could load in both arms of a pair.

    Checks the user-level folders (~/.agents/skills, ~/.codex/skills except .system, ~/.claude/skills,
    ~/.claude/commands, ~/.claude/agents, and the CODEX_HOME and CLAUDE_CONFIG_DIR variants), the system folders
    (/etc/codex/skills, /etc/claude-code/.claude/skills), installed Claude Code plugins and, when search_from is given,
    project folders (.agents/skills, .claude/skills, .claude/commands, .claude/agents) in search_from and its parent
    folders.
    """
    candidates = host_skill_folders(home, environ, system_dirs)
    if search_from:
        for folder in (search_from, *search_from.parents):
            candidates += [(folder / ".agents" / "skills", set())]
            candidates += [(folder / ".claude" / sub, set()) for sub in ("skills", "commands", "agents")]
    found: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for folder, skip in candidates:
        try:
            resolved = folder.resolve()
            if resolved in seen or not folder.is_dir():
                continue
            seen.add(resolved)
            entries = sorted(p.name for p in folder.iterdir() if p.name not in skip and not p.name.startswith("."))
        except OSError:
            continue
        if entries:
            found.append(dict(path=str(folder), entries=entries))
    homes_seen: set[Path] = set()
    for claude_home in _homes(home, environ)[2]:
        plugins = _installed_plugins(claude_home)
        if plugins and claude_home.resolve() not in homes_seen:
            homes_seen.add(claude_home.resolve())
            found.append(dict(path=str(claude_home / "plugins" / "installed_plugins.json"), entries=plugins))
    return found


def _nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _nonempty_dir(path: Path) -> bool:
    try:
        return path.is_dir() and any(path.iterdir())
    except OSError:
        return False


def find_host_instructions(
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    search_from: Path | None = None,
    system_files: tuple[Path, ...] = SYSTEM_INSTRUCTION_FILES,
) -> list[str]:
    """Instruction files outside the workspaces that Codex or Claude Code read at the start of a session.

    User level: AGENTS.override.md and AGENTS.md in CODEX_HOME or ~/.codex, CLAUDE.md and rules/ in
    CLAUDE_CONFIG_DIR or ~/.claude; system level: /etc/claude-code/CLAUDE.md; and, when search_from is given, the
    project instruction files (PROJECT_INSTRUCTION_FILES, .claude/rules/) in search_from and its parent folders.
    Such files reach both arms, but not always equally: Claude Code skips an AGENTS.md above the working directory
    when the working directory has a CLAUDE.md, which is where the add-on's pointer is installed.
    """
    _, codex_homes, claude_homes = _homes(home, environ)
    files = [c / name for c in codex_homes for name in ("AGENTS.override.md", "AGENTS.md")]
    files += [c / "CLAUDE.md" for c in claude_homes]
    folders = [c / "rules" for c in claude_homes]
    files += list(system_files)
    if search_from:
        for folder in (search_from, *search_from.parents):
            files += [folder / name for name in PROJECT_INSTRUCTION_FILES]
            folders.append(folder / ".claude" / "rules")
    found: list[str] = []
    seen: set[Path] = set()
    for path in files + folders:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if _nonempty_file(path) or (path in folders and _nonempty_dir(path)):
            found.append(str(path))
    return found


def find_repository(search_from: Path) -> str | None:
    """The nearest folder at or above search_from that holds .git (a Git repository or worktree), or None.

    Inside a repository, Codex and Claude Code treat the repository as the project: project instructions, project
    settings and Claude Code's auto memory are shared by every workspace below it, including both arms of a pair.
    """
    for folder in (search_from, *search_from.parents):
        if (folder / ".git").exists():
            return str(folder)
    return None


@dataclass
class HostContext:
    """Skills, instructions and project settings outside the workspaces that the agents of a pair could load."""

    skills: list[dict[str, Any]] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    repository: str | None = None

    @property
    def clean(self) -> bool:
        return not (self.skills or self.instructions or self.repository)


def find_host_context(
    home: Path | None = None, environ: Mapping[str, str] | None = None, runs_root: Path | None = None
) -> HostContext:
    """Everything outside the workspaces below runs_root that could reach the agents of both arms."""
    root = runs_root.resolve() if runs_root else None
    return HostContext(
        skills=find_host_skills(home, environ, search_from=root),
        instructions=find_host_instructions(home, environ, search_from=root),
        repository=find_repository(root) if root else None,
    )


def host_context_message(context: HostContext) -> str:
    """Why a pair is refused when the host gives agents skills or instructions, and what to do about it."""
    lines = []
    if context.skills:
        lines.append("skill folders or plugins:")
        lines += [
            f"  {f['path']} ({len(f['entries'])} entries: {', '.join(f['entries'][:5])}"
            f"{', ...' if len(f['entries']) > 5 else ''})"
            for f in context.skills
        ]
    if context.instructions:
        lines.append("instruction files:")
        lines += [f"  {path}" for path in context.instructions]
    if context.repository:
        lines.append(f"the runs folder is inside the Git repository {context.repository} (project settings and memory)")
    return (
        "found agent context outside the workspaces; an agent can load it in both arms, so the baseline would not be "
        "clean:\n" + "\n".join(lines) + "\nRun inside a container (or a user account) whose home holds no skills or "
        "instruction files, with MRAB_RUNS outside any repository; or pass --allow-host-context to run anyway (the "
        "pair is then recorded with host_skills, host_instructions and runs_repository, and baseline_clean false)."
    )


def host_skills_message(found: list[dict[str, Any]]) -> str:
    """host_context_message for skill folders only (kept for callers that check skills alone)."""
    return host_context_message(HostContext(skills=found))
