#!/usr/bin/env python3
"""Maintainers: build one tar per public instance from the study folders and record package hashes in instances.json.
Usage: tools/make_packages.py SOURCE_ROOT OUT_DIR
(SOURCE_ROOT holds the instance folders named in instances.json 'source')"""

import hashlib
import json
import sys
import tarfile
from pathlib import Path

src = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
repo = Path(__file__).resolve().parents[1]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


for f in sorted((repo / "families").glob("*/instances.json")):
    xs = json.loads(f.read_text())
    for x in xs:
        d = src / x["source"]
        tp = out / x["package"]
        if not tp.exists():
            with tarfile.open(tp, "w") as t:
                t.add(d, arcname=x["instance"], filter=lambda ti: None if "__pycache__" in ti.name else ti)
        x["package_sha256"] = sha(tp)
        x["package_bytes"] = tp.stat().st_size
        print(x["instance"], x["package_bytes"])
    f.write_text(json.dumps(xs, indent=1) + "\n")
