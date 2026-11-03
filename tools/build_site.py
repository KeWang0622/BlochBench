#!/usr/bin/env python3
"""Build the static website data and the README tables.

    python tools/build_site.py [--check]

Reads families/*/instances.json, families/*/README.md, families/*/VALIDATION.md, docs/trivial-agent-grades.json,
CANARY.txt and leaderboard/leaderboard.json, and writes

- site/data/{families,leaderboard,summary}.json, plus site/data/data.js, which holds the same data as a script so
  that the pages also work when opened from file:// (no fetch needed);
- the numbers marked with data-stat="..." in site/*.html;
- the README tables between <!-- LEADERBOARD:START/END --> and <!-- DOMAINS:START/END -->.

Standard library only. Running it twice gives the same files. With --check it writes nothing and exits with status 1
if any output would change (useful in CI).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "site"
DATA = SITE / "data"
README = REPO / "README.md"
GITHUB = "https://github.com/KeWang0622/BlochBench"
BRANCH = "main"
MRFOUNDRY = "https://github.com/KeWang0622/MRFoundry"

# Display order and short labels of the ten domains; full names come from the family READMEs.
DOMAINS = [
    ("seq", "Sequences"),
    ("mrs", "MRS"),
    ("fmri", "fMRI"),
    ("relax", "Relax/QSM"),
    ("perf", "Perf/CEST"),
    ("diff", "Diffusion"),
    ("recon", "Recon"),
    ("hw", "Hardware"),
    ("stats", "Statistics"),
    ("write", "Writing"),
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def first_sentences(text: str, min_len: int = 90, max_len: int = 330) -> str:
    """First sentence of the task text, plus the next one if the first is very short."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(text.split()))
    out = parts[0]
    for p in parts[1:]:
        if len(out) >= min_len or len(out) + len(p) + 1 > max_len:
            break
        out += " " + p
    return out


def readme_field(readme: str, name: str) -> str:
    m = re.search(rf"^- {name}:\s*(.+)$", readme, re.M)
    return m.group(1).strip() if m else ""


def families() -> list[dict]:
    catalog = read_json(REPO / "docs" / "task-catalog.json")
    out = []
    index = read_json(REPO / "families" / "index.json")["tasks"]
    for identity in index:
        fam = REPO / "families" / identity["directory"]
        inst_file = fam / "instances.json"
        fid = identity["legacy_id"]
        instances = read_json(inst_file)
        readme = (fam / "README.md").read_text(encoding="utf-8")
        checks_m = re.search(r"^- Automated checks \((\d+)\):\s*(.+)$", readme, re.M)
        tier = readme_field(readme, "Tier")
        review_m = re.search(r"review status:\s*(\w+)", tier)
        task_m = re.search(r"~~~text\n(.*?)\n~~~", readme, re.S)
        cap_m = re.search(r"(\d+)\s*min", readme_field(readme, "Time cap"))
        val_path = fam / "VALIDATION.md"
        validation = val_path.read_text(encoding="utf-8") if val_path.exists() else ""
        kinds = re.findall(r"^\|[^|\n]+\|\s*(negative|positive|reference)\s*\|", validation, re.M)
        codes = sorted({x["domain"] for x in instances})
        if len(codes) != 1:
            raise SystemExit(f"{fid}: expected one domain code, found {codes}")
        caps = sorted({x["cap_s"] for x in instances})
        out.append(
            dict(
                id=fid,
                public_id=identity["id"],
                directory=identity["directory"],
                instance_aliases=identity["instances"],
                title=catalog[fid]["title"],
                input=catalog[fid]["input"],
                output=catalog[fid]["output"],
                verification=catalog[fid]["verification"],
                domain=codes[0],
                domain_name=readme_field(readme, "Domain"),
                tier=tier.split(";")[0].strip(),
                review=review_m.group(1) if review_m else "unknown",
                cap_min=int(cap_m.group(1)) if cap_m else round(caps[0] / 60),
                checks=int(checks_m.group(1)) if checks_m else None,
                check_names=[c.strip() for c in checks_m.group(2).split(",")] if checks_m else [],
                instances=[x["instance"] for x in instances],
                negative_controls=kinds.count("negative"),
                summary=first_sentences(task_m.group(1)) if task_m else "",
                url=f"{GITHUB}/tree/{BRANCH}/families/{identity['directory']}",
            )
        )
    return out


def domains(fams: list[dict]) -> list[dict]:
    names: dict[str, str] = {}
    for f in fams:
        names.setdefault(f["domain"], f["domain_name"])
    known = [c for c, _ in DOMAINS]
    short = dict(DOMAINS)
    out = []
    for code in known + sorted(set(names) - set(known)):
        fs = [f for f in fams if f["domain"] == code]
        if not fs:
            continue
        out.append(
            dict(
                code=code,
                name=names[code],
                short=short.get(code, code),
                families=len(fs),
                instances=sum(len(f["instances"]) for f in fs),
                checks=sum(f["checks"] or 0 for f in fs),
                family_ids=[f["id"] for f in fs],
            )
        )
    return out


def summary(fams: list[dict], doms: list[dict], board: dict) -> dict:
    trivial_path = REPO / "docs" / "trivial-agent-grades.json"
    trivial = read_json(trivial_path) if trivial_path.exists() else {}
    entries = board.get("entries", [])
    canary = (REPO / "CANARY.txt").read_text(encoding="utf-8")
    guid_m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", canary)
    caps = sorted({f["cap_min"] for f in fams})
    return dict(
        families=len(fams),
        domains=len(doms),
        instances=sum(len(f["instances"]) for f in fams),
        checks=sum(f["checks"] or 0 for f in fams),
        negative_controls=sum(f["negative_controls"] for f in fams),
        cap_range=f"{caps[0]}–{caps[-1]} min" if len(caps) > 1 else f"{caps[0]} min",
        empty_families=len(trivial),
        empty_checks_passed=sum(v["n"] - v["failed"] for v in trivial.values()),
        empty_checks_total=sum(v["n"] for v in trivial.values()),
        board=board.get("board", ""),
        board_date=board.get("generated", "")[:10],
        board_split=board.get("split", {}).get("name", ""),
        board_instances=len(board.get("split", {}).get("instances", [])),
        board_entries=len(entries),
        board_ranked=sum(1 for e in entries if e.get("complete")),
        board_in_progress=sum(1 for e in entries if not e.get("complete")),
        board_models=len({e["model"] for e in entries}),
        board_runs=sum(e["runs"] for e in entries),
        version=board.get("version", ""),
        canary=guid_m.group(0) if guid_m else "",
        github=GITHUB,
        mrfoundry=MRFOUNDRY,
    )


# ---------------------------------------------------------------- README tables


def num(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def pct(x: float) -> str:
    return num(100 * x) + "%"


def ci(c: list[float]) -> str:
    return f"{num(100 * c[0])}–{num(100 * c[1])}"


def tokens(n) -> str:
    return "–" if n is None else f"{n / 1e6:.2f} M"


def minutes(s) -> str:
    return "–" if s is None else f"{s / 60:.1f} min"


def ranked(entries: list[dict]) -> list[tuple[int, dict]]:
    """Complete entries by verified rate, with standard competition ranks for ties."""
    done = sorted(
        (e for e in entries if e.get("complete")), key=lambda e: (-e["rate"], e["model_name"], bool(e["addon"]))
    )
    out, prev, rank = [], None, 0
    for i, e in enumerate(done, 1):
        if e["rate"] != prev:
            rank, prev = i, e["rate"]
        out.append((rank, e))
    return out


def keep(text: str) -> str:
    """Keep a short label on one line in a Markdown table (no-break spaces and hyphens)."""
    return text.replace(" ", "\u00a0").replace("-", "\u2011")


def paired(entries: list[dict]) -> list[tuple[dict, dict]]:
    base = {e["model"]: e for e in entries if not e["addon"] and e.get("complete")}
    pairs = [(base[e["model"]], e) for e in entries if e["addon"] and e.get("complete") and e["model"] in base]
    return sorted(pairs, key=lambda p: p[0]["model_name"])


def source_names(board: dict) -> list[str]:
    """Human-readable origins of the board's runs, from the top-level sources map or the per-entry fields."""
    names = board.get("sources") or {}
    keys: list[str] = []
    for e in board.get("entries", []):
        for k in e.get("sources") or ([e["source"]] if e.get("source") else []):
            if k not in keys:
                keys.append(k)
    if not keys:
        keys = list(names)
    return [names.get(k, k) for k in sorted(keys, key=lambda k: list(names).index(k) if k in names else len(names))]


def pp(value: float) -> str:
    return f"{100 * value:+.1f} pp"


def paired_ci(value: list[float]) -> str:
    return f"{100 * value[0]:+.1f} to {100 * value[1]:+.1f} pp"


def pvalue(value: float) -> str:
    return f"{value:.2g}" if value < 0.0001 else f"{value:.4f}"


def leaderboard_md(board: dict) -> str:
    evaluation = board["offline_evaluation"]
    lines = [
        "| Evaluation | Paired trials | Baseline | With MRFoundry | Difference (95% CI) |",
        "|---|---:|---:|---:|---:|",
    ]
    for tier in ("core", "hard"):
        value = evaluation[tier]["all"]
        lines.append(
            f"| {tier.title()} | {value['n']} | {value['A']}/{value['n']} ({pct(value['A'] / value['n'])}) | "
            f"{value['S']}/{value['n']} ({pct(value['S'] / value['n'])}) | "
            f"{pp(value['diff'])} ({paired_ci(value['ci'])}) |"
        )
    return "\n".join(lines)


def results_md(board: dict) -> str:
    evaluation = board["offline_evaluation"]
    entries = board["entries"]
    lines = [
        leaderboard_md(board),
        "",
        "## Core: paired model results",
        "",
        "One instance per task type, 24 trials per arm. Models are listed alphabetically. "
        "A pass means every automated check passed; it does not establish general MRI proficiency.",
        "",
        "| Model | Baseline passes | With MRFoundry | Difference | Median tokens, baseline → MRFoundry |",
        "|---|---:|---:|---:|---:|",
    ]
    for baseline, skills in paired(entries):
        lines.append(
            f"| {baseline['model_name']} | {baseline['verified']}/{baseline['runs']} | "
            f"{skills['verified']}/{skills['runs']} | {pp(skills['rate'] - baseline['rate'])} | "
            f"{tokens(baseline['median_tokens'])} → {tokens(skills['median_tokens'])} |"
        )
    labels = {e["model"]: e["model_name"] for e in entries}
    hard_models = evaluation["hard"]["by_model"]
    for size in sorted({v["n"] for v in hard_models.values()}, reverse=True):
        coverage = "15 task types × 2 instances" if size == 30 else "11 multi-stage task types × 1 instance"
        lines += [
            "",
            f"## Hard: {size}-trial cohort",
            "",
            coverage + ". Compare models within this cohort only.",
            "",
            "| Model | Baseline passes | With MRFoundry | Difference |",
            "|---|---:|---:|---:|",
        ]
        for model, value in sorted(hard_models.items(), key=lambda x: labels.get(x[0], x[0])):
            if value["n"] == size:
                lines.append(
                    f"| {labels.get(model, model)} | {value['A']}/{size} | {value['S']}/{size} | "
                    f"{pp((value['S'] - value['A']) / size)} |"
                )
    return "\n".join(lines)


def domains_md(doms: list[dict]) -> str:
    catalog = read_json(REPO / "docs" / "task-catalog.json")
    lines = ["| Domain | Task types | Data variants | Examples |", "|---|---:|---:|---|"]
    for d in doms:
        examples = "; ".join(catalog[f]["title"] for f in d["family_ids"][:2])
        lines.append(f"| {d['name']} | {d['families']} | {d['instances']} | {examples} |")
    return "\n".join(lines)


def replace_block(text: str, name: str, body: str) -> str:
    """Replace everything between the START and END markers (which may be empty) with body."""
    pat = re.compile(rf"(<!-- {name}:START[^>]*-->)(.*?)(<!-- {name}:END -->)", re.S)
    if not pat.search(text):
        print(f"warning: README has no {name} markers", file=sys.stderr)
        return text
    return pat.sub(lambda m: m.group(1) + "\n" + body + "\n" + m.group(3), text, count=1)


def fill_stats(page: str, stats: dict) -> str:
    """Refresh the text of elements marked data-stat="key" (no nested tags) with the computed value."""

    def sub(m: re.Match) -> str:
        key = m.group(2)
        if key not in stats:
            return m.group(0)
        return m.group(1) + html.escape(str(stats[key])) + m.group(4)

    return re.sub(r'(<[^>]*\bdata-stat="([a-z_]+)"[^>]*>)([^<]*)(<)', sub, page)


# ---------------------------------------------------------------- main


def outputs() -> dict[Path, str]:
    board = read_json(REPO / "leaderboard" / "leaderboard.json")
    fams = families()
    doms = domains(fams)
    stats = summary(fams, doms, board)
    fam_of = {i: f["id"] for f in fams for i in f["instances"]}
    site_board = dict(board, family_of_instance={i: fam_of.get(i) for i in board.get("split", {}).get("instances", [])})
    data = {"summary": stats, "domains": doms, "families": fams, "leaderboard": site_board}

    def dump(obj) -> str:
        return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"

    out: dict[Path, str] = {
        DATA / "families.json": dump({"canary": stats["canary"], "domains": doms, "families": fams}),
        DATA / "leaderboard.json": dump(dict(site_board, canary=stats["canary"])),
        DATA / "summary.json": dump(stats),
        DATA / "data.js": (
            "/* Generated by tools/build_site.py; do not edit. The JSON files in this folder as one script, "
            f"so that pages also work from file://. BlochBench canary GUID {stats['canary']} */\n"
            "window.MRAB_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
        ),
    }
    for page in sorted(SITE.glob("*.html")):
        out[page] = fill_stats(page.read_text(encoding="utf-8"), stats)
    if README.exists():
        text = README.read_text(encoding="utf-8")
        text = replace_block(text, "LEADERBOARD", leaderboard_md(board))
        text = replace_block(text, "DOMAINS", domains_md(doms))
        out[README] = text
    results = REPO / "docs" / "RESULTS.md"
    if results.exists():
        out[results] = replace_block(results.read_text(encoding="utf-8"), "RESULTS", results_md(board))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if any output is out of date")
    a = ap.parse_args()
    changed = []
    for path, content in outputs().items():
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old == content:
            continue
        changed.append(path.relative_to(REPO))
        if not a.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    verb = "out of date" if a.check else "updated"
    print(f"{len(changed)} file(s) {verb}" + (": " + ", ".join(map(str, changed)) if changed else ""))
    return 1 if (a.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
