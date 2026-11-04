#!/usr/bin/env python3
"""Write croissant.json (Croissant 1.1 with Responsible AI fields) and the data catalog it describes.

    python tools/make_croissant.py [--base-url URL] [--out croissant.json] [--catalog-out catalog.csv]

The catalog (one row per public instance) is published next to the instance packages, under the same base URL.
Validate with: mlcroissant validate --jsonld croissant.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

try:
    from .make_family_metadata import build, family_dirs
except ImportError:  # Direct execution: python tools/make_croissant.py.
    from make_family_metadata import build, family_dirs

REPO = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "https://github.com/KeWang0622/MRIAgentBench/releases/download/core-v0.1.0/"
CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "containedIn": "cr:containedIn",
    "cr": "http://mlcommons.org/croissant/",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
    "extract": "cr:extract",
    "field": "cr:field",
    "fileObject": "cr:fileObject",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "parentField": "cr:parentField",
    "path": "cr:path",
    "recordSet": "cr:recordSet",
    "references": "cr:references",
    "regex": "cr:regex",
    "repeated": "cr:repeated",
    "replace": "cr:replace",
    "sc": "https://schema.org/",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
    "equivalentProperty": "cr:equivalentProperty",
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "fileProperty": "cr:fileProperty",
    "samplingRate": "cr:samplingRate",
}
COLUMNS = [
    ("instance", "sc:Text", "Frozen legacy instance name; public aliases are in families/index.json"),
    ("family", "sc:Text", "Frozen legacy family ID; public task IDs are in families/index.json"),
    ("domain", "sc:Text", "MRI research domain code"),
    ("cap_s", "sc:Integer", "Time cap for an agent run, seconds"),
    ("checks_grader", "sc:Text", "Grader script inside the package (private/)"),
    ("package", "sc:Text", "Package file name"),
    ("package_sha256", "sc:Text", "SHA-256 of the package"),
    ("package_bytes", "sc:Integer", "Package size in bytes"),
]
RAI = {
    "rai:dataCollection": "Every instance is produced by its family's generator script (families/<directory>/code; "
    "see families/index.json for public and legacy identifiers) "
    "from simulations, "
    "digital phantoms and synthetic study data with fixed seeds, then frozen with a SHA-256 manifest. "
    "No generator reads external data.",
    "rai:dataCollectionType": "Simulation",
    "rai:personalSensitiveInformation": "None. The public split contains no data from human participants.",
    "rai:dataLimitations": "Synthetic data lack many artefacts of real scanners and patients; a pass means "
    "the deliverables meet "
    "the family's stated checks, not that the work is publishable. Tasks are in English and cover ten "
    "MRI research domains chosen by the authors. Public instances can leak into training data; the "
    "future hidden evaluation is planned (docs/ROADMAP.md).",
    "rai:dataBiases": "Task construction used AI author agents with maintainer integration, and reflects their "
    "choice of methods, "
    "conventions and tolerances; "
    "independent expert review is pending for all families (docs/REVIEW-PROTOCOL.md).",
    "rai:dataUseCases": "Evaluating AI agents and agent add-ons on end-to-end MRI research tasks. Not for "
    "training models "
    "(see the canary in CANARY.txt) and not for any clinical use.",
    "rai:dataSocialImpact": "Measures whether agents produce MRI research results that survive independent "
    "checks, which can "
    "make claims about agent capability in medical imaging research more reliable.",
    "rai:dataAnnotationProtocol": "Each family defines automated checks (311 in total). Graders are "
    "validated with a reference "
    "solution, at least six negative controls that must fail named checks and two positive "
    "controls that must pass; an empty submission fails every check.",
    "rai:dataReleaseMaintenancePlan": "Versioned releases; a change that can alter scores is a minor "
    "(regrade) or major (rerun) "
    "version (CHANGELOG.md). Problems are reported through GitHub issues.",
}


def catalog_rows() -> list[dict]:
    """Keep the published catalog's names and row order stable after source directory renames."""
    rows = []
    families = sorted(((build(folder), folder) for folder in family_dirs(REPO / "families")), key=lambda p: p[0]["id"])
    for family, folder in families:
        f = folder / "instances.json"
        for x in json.loads(f.read_text()):
            if not x.get("package_sha256"):
                raise SystemExit(f"{x['instance']}: no package_sha256; run tools/make_packages.py first")
            rows.append(
                dict(
                    instance=x["instance"],
                    family=family["id"],
                    domain=x["domain"],
                    cap_s=x["cap_s"],
                    checks_grader=x["grader"],
                    package=x["package"],
                    package_sha256=x["package_sha256"],
                    package_bytes=x["package_bytes"],
                )
            )
    return rows


def public_instances() -> dict[str, dict]:
    """Public IDs and source links are descriptive metadata, not changes to frozen packages."""
    lookup = {}
    for folder in family_dirs(REPO / "families"):
        family = build(folder)
        for alias, legacy in family["instance_aliases"].items():
            lookup[legacy] = {
                "alias": alias,
                "task_id": family["public_id"],
                "url": f"https://github.com/KeWang0622/MRIAgentBench/tree/main/families/{folder.name}",
            }
    return lookup


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--out", type=Path, default=REPO / "croissant.json")
    ap.add_argument(
        "--catalog-out",
        type=Path,
        default=REPO / "dist" / "catalog.csv",
        help="upload this file next to the instance packages",
    )
    ap.add_argument("--date-published", help="ISO date of the release; set when the data are published")
    a = ap.parse_args()
    rows = catalog_rows()
    identities = public_instances()
    a.catalog_out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=[c for c, _, _ in COLUMNS], lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    a.catalog_out.resolve().write_text(buf.getvalue())
    base = a.base_url.rstrip("/") + "/"
    dist = [
        {
            "@type": "cr:FileObject",
            "@id": "catalog.csv",
            "name": "catalog.csv",
            "description": "Frozen release catalog: legacy instance and family IDs, domain, time cap, grader, "
            "package and its SHA-256. Public task and instance aliases are mapped in families/index.json.",
            "contentUrl": base + "catalog.csv",
            "encodingFormat": "text/csv",
            "sha256": hashlib.sha256(buf.getvalue().encode()).hexdigest(),
        }
    ]
    for r in rows:
        identity = identities[r["instance"]]
        dist.append(
            {
                "@type": "cr:FileObject",
                "@id": r["package"],
                "name": r["package"],
                "description": f"Instance {identity['alias']} of task {identity['task_id']} "
                f"(legacy instance {r['instance']}, family {r['family']}): prompt, public inputs, private grader, "
                "reference, controls, hidden data and FROZEN-SHA256.txt.",
                "url": identity["url"],
                "contentUrl": base + r["package"],
                "encodingFormat": "application/x-tar",
                "contentSize": f"{r['package_bytes']} B",
                "sha256": r["package_sha256"],
            }
        )
    fields = [
        {
            "@type": "cr:Field",
            "@id": f"instances/{c}",
            "name": c,
            "description": d,
            "dataType": t,
            "source": {"fileObject": {"@id": "catalog.csv"}, "extract": {"column": c}},
        }
        for c, t, d in COLUMNS
    ]
    doc = {
        "@context": CONTEXT,
        "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.1",
        "name": "MRI Agent Bench",
        "version": "0.1.0",
        "description": "Benchmark for AI agents on end-to-end MRI research tasks: 24 task families in ten domains, "
        f"{len(rows)} public instances and 311 automated checks. Graders replay exported sequences in a "
        "Bloch simulator, rerun submitted code on hidden data, compare maps with ground truth and "
        "recompute statistics. Pre-release.",
        "url": "https://github.com/KeWang0622/MRIAgentBench",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "creator": {"@type": "sc:Person", "name": "Ke Wang"},
        "keywords": ["MRI", "benchmark", "AI agents", "evaluation", "Bloch simulation", "medical imaging"],
        "citeAs": "@misc{wang2026mriagentbench, "
        "title={MRI Agent Bench: a benchmark for AI agents on end-to-end MRI research}, "
        "author={Wang, Ke}, year={2026}, note={Pre-release}, url={https://github.com/KeWang0622/MRIAgentBench}}",
        "isLiveDataset": False,
        **({"datePublished": a.date_published} if a.date_published else {}),
        **RAI,
        "distribution": dist,
        "recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "instances",
                "name": "instances",
                "description": "Public instances of MRI Agent Bench.",
                "key": {"@id": "instances/instance"},
                "field": fields,
            }
        ],
    }
    a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print(f"{a.out}: {len(rows)} instances; catalog {a.catalog_out.resolve()}")


if __name__ == "__main__":
    main()
