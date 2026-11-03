"""Client for the hosted grading API (standard library only).

  mrab bundle RUNS_DIR -o bundle.tar.gz [--config NAME]    pack workspaces for grading
  mrab submit RUNS_DIR --model M --agent A [--addon NAME] [--addon-manifest addon.json] [--config NAME] [--wait]
  mrab status [SUBMISSION_ID] [--results FILE]

Environment: MRAB_API_URL (service base URL), MRAB_TOKEN (submitter token issued by the maintainers).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

# Caches and environments are not deliverables: graders rerun submitted code in the pinned grader environment.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".ipynb_checkpoints",
    ".mypy_cache",
    ".pytest_cache",
    ".julia",
    ".cache",
    ".tmp",
    ".npm",
    ".local",
    ".conda",
    ".ruff_cache",
}


def is_runtime_install(d: Path) -> bool:
    """A Python virtual environment or a Julia/Python installation that an agent placed in its workspace."""
    return (d / "pyvenv.cfg").exists() or (d / "bin" / "julia").exists() or (d / "bin" / "python3").exists()


def find_runs(runs_dir: Path, config: str | None = None) -> list[dict]:
    """Runs laid out by mrab run: RUNS_DIR/<config>/<instance>/run<k>/work (folders named exactly run<k>)."""
    out = []
    for work in sorted(runs_dir.glob("*/*/run*/work")):
        cfg, inst, run = work.parts[-4], work.parts[-3], work.parts[-2]
        if config and cfg != config:
            continue
        match = re.fullmatch(r"run([1-9][0-9]*)", run)
        if not match:
            sys.exit(f"{work.parent} is not named run<k>; move it out of {runs_dir}")
        out.append(dict(config=cfg, instance=inst, run=int(match.group(1)), work=work))
    configs = {r["config"] for r in out}
    if len(configs) > 1:
        sys.exit(f"{runs_dir} holds several configurations ({', '.join(sorted(configs))}); pick one with --config")
    return out


def make_bundle(runs: list[dict], dest: Path, config: dict) -> dict:
    """Write a gzip tar with submission.json and runs/<instance>/run<k>/work/...

    Skipped: caches (SKIP_DIRS), runtimes installed inside the workspace, and links that point out of it.
    """
    manifest = dict(
        format="mragentbench-bundle/1",
        config=config,
        runs=[
            dict(instance=r["instance"], run=r["run"], path=f"runs/{r['instance']}/run{r['run']}/work") for r in runs
        ],
    )
    skipped = []
    with tarfile.open(dest, "w:gz") as t:
        data = json.dumps(manifest, indent=1).encode()
        info = tarfile.TarInfo("submission.json")
        info.size, info.mtime = len(data), int(time.time())
        import io

        t.addfile(info, io.BytesIO(data))
        for r in runs:
            root = r["work"].resolve()
            t.add(root, arcname=f"runs/{r['instance']}/run{r['run']}/work", recursive=False)
            for dirpath, dirnames, filenames in os.walk(root):
                keep = []
                for d in dirnames:
                    if d in SKIP_DIRS or is_runtime_install(Path(dirpath) / d):
                        skipped.append(str(Path(dirpath) / d) + "/")
                    else:
                        keep.append(d)
                dirnames[:] = keep
                for name in dirnames + filenames:
                    p = Path(dirpath) / name
                    if p.is_symlink():
                        target = (p.parent / os.readlink(p)).resolve()
                        if root not in target.parents and target != root:
                            skipped.append(str(p))
                            continue
                    arc = f"runs/{r['instance']}/run{r['run']}/work/{p.relative_to(root)}"
                    t.add(p, arcname=arc, recursive=False)
            for rec in ("run.json",):
                f = r["work"].parent / rec
                if f.exists():
                    t.add(f, arcname=f"runs/{r['instance']}/run{r['run']}/{rec}")
    h = hashlib.sha256()
    with open(dest, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return dict(manifest=manifest, sha256=h.hexdigest(), bytes=dest.stat().st_size, skipped=skipped)


def _api(method: str, path: str, body: dict | None = None) -> dict:
    base = os.environ.get("MRAB_API_URL")
    token = os.environ.get("MRAB_TOKEN")
    if not base or not token:
        sys.exit("set MRAB_API_URL and MRAB_TOKEN (see docs/API.md)")
    req = urllib.request.Request(
        base.rstrip("/") + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        sys.exit(f"API error {e.code}: {msg}")


def _upload(url: str, path: Path) -> None:
    size = path.stat().st_size
    with open(path, "rb") as f:
        req = urllib.request.Request(url, data=f, method="PUT", headers={"Content-Length": str(size)})
        with urllib.request.urlopen(req, timeout=3600) as r:
            if r.status not in (200, 204):
                sys.exit(f"upload failed with HTTP {r.status}")


def cmd_bundle(a) -> None:
    runs = find_runs(Path(a.runs_dir), a.config)
    if not runs:
        sys.exit("no runs found (expected RUNS_DIR/<config>/<instance>/run<k>/work)")
    info = make_bundle(runs, Path(a.output), dict(name=runs[0]["config"]))
    print(json.dumps({k: info[k] for k in ("sha256", "bytes")} | {"runs": len(runs), "skipped": info["skipped"]}))


def run_record_of(run: dict) -> dict | None:
    """The run.json next to a run's workspace, or None for runs made without mrab (no run.json)."""
    path = run["work"].parent / "run.json"
    return json.loads(path.read_text()) if path.exists() else None


def addon_manifest_for(path: Path, runs: list[dict]) -> dict:
    """Validate the add-on package of addon.json (or its folder); return the manifest with its content hash.

    Every submitted run must have a run.json that records this add-on package with the same content hash: runs without
    a record, runs without an add-on, and runs made with a plain skills folder are refused, because their add-on
    cannot be checked.
    """
    from .addon import load_valid_addon, manifest_record

    report = load_valid_addon(path.parent if path.name == "addon.json" else path)
    manifest = manifest_record(report)
    for r in runs:
        record = run_record_of(r)
        rec = r["work"].parent / "run.json"
        if record is None:
            sys.exit(f"{rec} is missing; only runs recorded by mrab can be submitted with --addon-manifest")
        recorded = record.get("addon_manifest") or {}
        if not recorded:
            what = "a plain skills folder, not an add-on package" if record.get("addon") else "no add-on"
            sys.exit(f"{rec} was run with {what}; its add-on cannot be checked against --addon-manifest")
        if recorded.get("content_sha256") != manifest["content_sha256"]:
            sys.exit(
                f"{rec} was run with add-on content {str(recorded.get('content_sha256'))[:12]}, not "
                f"{manifest['content_sha256'][:12]} ({path})"
            )
    return manifest


def check_runs_without_manifest(runs: list[dict]) -> None:
    """Refuse runs whose run.json records any add-on (package or plain folder) when no --addon-manifest is given."""
    for r in runs:
        record = run_record_of(r) or {}
        if record.get("addon_manifest"):
            sys.exit(
                f"{r['work'].parent / 'run.json'} was run with the add-on {record['addon_manifest'].get('name')}; "
                "pass its package with --addon-manifest"
            )
        if record.get("addon"):
            sys.exit(
                f"{r['work'].parent / 'run.json'} was run with the skills folder {record['addon']}; only runs with "
                "an add-on package can be submitted, with --addon-manifest"
            )


def cmd_submit(a) -> None:
    runs = find_runs(Path(a.runs_dir), a.config)
    if not runs:
        sys.exit("no runs found (expected RUNS_DIR/<config>/<instance>/run<k>/work)")
    config = dict(model=a.model, agent=a.agent, addon=a.addon, label=a.label or runs[0]["config"])
    if a.addon_manifest:
        manifest = addon_manifest_for(Path(a.addon_manifest), runs)
        config["addon_manifest"] = manifest
        config["addon"] = a.addon or f"{manifest['name']} {manifest['version']}"
    else:
        check_runs_without_manifest(runs)
    path = Path(a.bundle or f"mrab-bundle-{int(time.time())}.tar.gz")
    info = make_bundle(runs, path, config)
    print(f"bundle {path}: {len(runs)} runs, {info['bytes'] / 1e6:.1f} MB, sha256 {info['sha256'][:12]}")
    sub = _api(
        "POST",
        "/v1/submissions",
        dict(
            config={k: v for k, v in config.items() if v},
            runs=info["manifest"]["runs"],
            bundle_sha256=info["sha256"],
            bundle_bytes=info["bytes"],
        ),
    )
    sid = sub["submission_id"]
    print(f"submission {sid}: uploading")
    _upload(sub["upload_url"], path)
    started = _api("POST", f"/v1/submissions/{sid}/start", {})
    print(f"submission {sid}: {started['status']} ({started['shards']} grading shards)")
    if a.wait:
        cmd_status(type("A", (), dict(submission_id=sid, results=a.results, wait=True))())


def cmd_status(a) -> None:
    if not a.submission_id:
        for s in _api("GET", "/v1/submissions")["submissions"]:
            summ = s.get("summary") or {}
            print(
                f"{s['submission_id']}  {s['status']:<16} {s.get('config', {}).get('label', '')}  "
                f"{summ.get('verified', '')}/{summ.get('runs', '')}"
            )
        return
    while True:
        s = _api("GET", f"/v1/submissions/{a.submission_id}")
        print(f"{s['submission_id']}: {s['status']} ({s.get('shards_done', 0)}/{s.get('shards') or '?'} shards)")
        if s["status"] in ("done", "error") or not getattr(a, "wait", False):
            break
        time.sleep(30)
    if s.get("summary"):
        print(json.dumps(s["summary"], indent=1))
    if s.get("error"):
        print("error:", s["error"])
    if s.get("results_url") and a.results:
        with urllib.request.urlopen(s["results_url"], timeout=120) as r:
            Path(a.results).write_bytes(r.read())
        print("results written to", a.results)


def add_parsers(sp) -> None:
    p = sp.add_parser("bundle", help="pack run workspaces for hosted grading")
    p.add_argument("runs_dir")
    p.add_argument("-o", "--output", default="mrab-bundle.tar.gz")
    p.add_argument("--config")
    p.set_defaults(f=cmd_bundle)
    p = sp.add_parser("submit", help="submit runs to the hosted grading service")
    p.add_argument("runs_dir")
    p.add_argument("--model", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--addon", help="add-on label shown with the results, e.g. 'MRFoundry 0.14.0'")
    p.add_argument("--addon-manifest", help="addon.json of the add-on package (validated; sent with its content hash)")
    p.add_argument("--label")
    p.add_argument("--config")
    p.add_argument("--bundle")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--results")
    p.set_defaults(f=cmd_submit)
    p = sp.add_parser("status", help="status of hosted grading submissions")
    p.add_argument("submission_id", nargs="?")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--results")
    p.set_defaults(f=cmd_status)
