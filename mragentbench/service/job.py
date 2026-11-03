"""Grading job of the hosted grading service.

Runs inside the grader image as an AWS Batch job (one child per shard of an array job). The container has no AWS
credentials. Everything it needs comes from a job specification that the API wrote and passed as a presigned URL:

    MRAB_JOB_SPEC_URL           presigned GET URL of the job specification (JSON)
    AWS_BATCH_JOB_ARRAY_INDEX   shard index, set by AWS Batch for array jobs (0 when absent)

The specification holds presigned GET URLs for the submission bundle and the instance packages, the bundle's SHA-256,
the number of shards, and a callback URL plus a one-time job token for posting results back to the API.

Graders execute code that the submitter wrote (for example, an entrypoint rerun on hidden data). When the job runs as
root, each grader runs as an unprivileged user in a fresh copy of the instance, so submitted code cannot read the job
specification, the token or other runs, and every process it leaves behind is killed before the grade is read.
Run locally (python -m mragentbench.service.job --spec FILE --shard 0) it grades as the current user.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path

GRADER_UID = 65534
MAX_BUNDLE_MEMBERS = 200_000
MAX_EXTRACTED_BYTES = 20 * 1024**3


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url: str, dest: Path, timeout: int = 600) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    return dest


def read_json_url(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read())


def post_json(url: str, payload: dict, token: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "X-Job-Token": token},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    return {}


def safe_extract(archive: Path, dest: Path) -> None:
    """Extract a tar archive with the 'data' filter (no absolute paths, no links out of dest) and size limits."""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as t:
        members = t.getmembers()
        if len(members) > MAX_BUNDLE_MEMBERS:
            raise ValueError(f"archive has {len(members)} members (limit {MAX_BUNDLE_MEMBERS})")
        if sum(m.size for m in members if m.isfile()) > MAX_EXTRACTED_BYTES:
            raise ValueError("archive expands beyond the size limit")
        t.extractall(dest, filter="data")


def verify_manifest(instance_dir: Path, manifest_sha256: str | None) -> tuple[int, int]:
    """Check every file of an instance against FROZEN-SHA256.txt; returns (files, mismatches)."""
    manifest = instance_dir / "FROZEN-SHA256.txt"
    if manifest_sha256 and sha256_file(manifest) != manifest_sha256:
        raise ValueError(f"{instance_dir.name}: manifest hash differs from the catalog")
    n = bad = 0
    for line in manifest.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):  # some manifests start with comment lines
            continue
        digest, rel = line.split(None, 1)
        p = instance_dir / rel.strip().lstrip("*")
        n += 1
        if not p.exists() or sha256_file(p) != digest:
            bad += 1
    return n, bad


def _chown_tree(path: Path, uid: int) -> None:
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            os.lchown(os.path.join(root, name), uid, uid)
    os.lchown(path, uid, uid)


def _kill_uid(uid: int) -> None:
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit():
            try:
                if proc.stat().st_uid == uid:
                    os.kill(int(proc.name), signal.SIGKILL)
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass


def grade_run(instance: dict, instance_dir: Path, work: Path, scratch: Path, timeout_s: int) -> dict:
    """Grade one workspace against one instance in a fresh copy of the instance; returns a result record."""
    as_root = os.geteuid() == 0
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=scratch))
    inst_copy, work_copy, out = run_dir / "instance", run_dir / "work", run_dir / "grade"
    shutil.copytree(instance_dir, inst_copy, symlinks=True)
    shutil.copytree(work, work_copy, symlinks=True)
    out.mkdir()
    home = run_dir / "home"
    home.mkdir()
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "PYTHON_JULIACALL_HANDLE_SIGNALS": "yes",
        "JULIA_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MPLBACKEND": "Agg",
    }
    for k, v in os.environ.items():  # the pinned Julia setup of the image (juliacall, juliapkg, depot)
        if k.startswith(("PYTHON_JULIACALL_", "PYTHON_JULIAPKG_", "JULIA_")):
            env[k] = v
    env.update(PYTHON_JULIACALL_HANDLE_SIGNALS="yes", JULIA_NUM_THREADS="1")
    if "JULIA_DEPOT_PATH" in env:
        env["JULIA_DEPOT_PATH"] = f"{home / 'julia'}:{env['JULIA_DEPOT_PATH']}"
    if not as_root:  # local mode: grade like "mrab grade", in the caller's own environment
        env = dict(
            os.environ,
            **{
                k: env[k]
                for k in (
                    "PYTHON_JULIACALL_HANDLE_SIGNALS",
                    "JULIA_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "MPLBACKEND",
                )
            },
        )
        env.pop("MRAB_JOB_SPEC_URL", None)
    preexec = None
    if as_root:
        _chown_tree(run_dir, GRADER_UID)

        def preexec() -> None:  # noqa: F811 - runs in the child before exec
            os.setsid()
            os.setgroups([])
            os.setgid(GRADER_UID)
            os.setuid(GRADER_UID)

    cmd = [sys.executable, str(inst_copy / "private" / instance["grader"]), str(work_copy), str(out)]
    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            cwd=inst_copy / "private",
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            preexec_fn=preexec,
            start_new_session=not as_root,
        )
        exit_code = proc.returncode
        log = (proc.stdout + proc.stderr)[-20000:]
    except subprocess.TimeoutExpired as e:
        timed_out, exit_code = True, None
        log = ((e.stdout or b"").decode(errors="replace") + (e.stderr or b"").decode(errors="replace"))[-20000:]
    if as_root:
        _kill_uid(GRADER_UID)
    seconds = round(time.time() - t0, 1)
    grade_file = out / "grade.json"
    grade = {}
    if grade_file.exists() and not grade_file.is_symlink():
        try:
            grade = json.loads(grade_file.read_text())
        except json.JSONDecodeError:
            grade = {}
    checks = {k: bool(v.get("pass")) for k, v in (grade.get("checks") or {}).items()}
    shutil.rmtree(run_dir, ignore_errors=True)
    return dict(
        verified=bool(grade.get("all_automated_checks_pass")) and not timed_out,
        failed_checks=sorted(k for k, ok in checks.items() if not ok),
        checks=checks,
        grader_exit=exit_code,
        grader_timed_out=timed_out,
        grader_seconds=seconds,
        grader_log_tail=log[-4000:],
    )


def run_shard(spec: dict, shard: int, scratch: Path) -> dict:
    scratch.mkdir(parents=True, exist_ok=True)
    bundle = fetch(spec["bundle_url"], scratch / "bundle.tar.gz")
    if sha256_file(bundle) != spec["bundle_sha256"]:
        raise ValueError("bundle SHA-256 differs from the value declared at submission")
    bundle_dir = scratch / "bundle"
    safe_extract(bundle, bundle_dir)
    bundle.unlink()
    manifest = json.loads((bundle_dir / "submission.json").read_text())
    runs = sorted(manifest["runs"], key=lambda r: (r["instance"], int(r["run"])))
    mine = [r for i, r in enumerate(runs) if i % spec["shards"] == shard]
    data = scratch / "data"
    results, verified_instances = [], {}
    for r in mine:
        name = r["instance"]
        inst = spec["instances"][name]
        record = dict(instance=name, run=int(r["run"]))
        try:
            if name not in verified_instances:
                pkg = fetch(inst["url"], scratch / "pkg" / inst["package"])
                if inst.get("package_sha256") and sha256_file(pkg) != inst["package_sha256"]:
                    raise ValueError("instance package SHA-256 differs from the catalog")
                safe_extract(pkg, data)
                pkg.unlink()
                n, bad = verify_manifest(data / name, inst.get("manifest_sha256"))
                if bad:
                    raise ValueError(f"{bad} of {n} instance files differ from the frozen manifest")
                verified_instances[name] = n
            work = (bundle_dir / r["path"]).resolve()
            if bundle_dir.resolve() not in work.parents or not work.is_dir():
                raise ValueError(f"run path {r['path']!r} is not a directory inside the bundle")
            record.update(grade_run(inst, data / name, work, scratch, spec.get("grade_timeout_s", 1800)))
        except Exception as e:  # one bad run must not stop the others
            record.update(verified=False, error=f"{type(e).__name__}: {e}")
        results.append(record)
        print(
            json.dumps({k: record.get(k) for k in ("instance", "run", "verified", "grader_seconds", "error")}),
            flush=True,
        )
    return dict(
        shard=shard,
        runs=results,
        instance_files_verified=verified_instances,
        image=os.environ.get("MRAB_GRADER_IMAGE"),
        python=sys.version.split()[0],
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BlochBench hosted grading job")
    ap.add_argument("--spec", help="local job specification (default: MRAB_JOB_SPEC_URL)")
    ap.add_argument("--shard", type=int, default=int(os.environ.get("AWS_BATCH_JOB_ARRAY_INDEX", "0")))
    ap.add_argument("--scratch", default=os.environ.get("MRAB_SCRATCH", "/tmp/mrab-job"))
    ap.add_argument("--out", help="write the shard result here instead of posting it")
    a = ap.parse_args(argv)
    spec = json.loads(Path(a.spec).read_text()) if a.spec else read_json_url(os.environ.pop("MRAB_JOB_SPEC_URL"))
    try:
        result = run_shard(spec, a.shard, Path(a.scratch))
    except Exception as e:
        traceback.print_exc()
        result = dict(shard=a.shard, error=f"{type(e).__name__}: {e}", runs=[])
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=1))
    else:
        post_json(spec["callback_url"], result, spec["job_token"])
    print(json.dumps({"shard": a.shard, "runs": len(result["runs"]), "error": result.get("error")}), flush=True)
    return 0 if not result.get("error") else 1


if __name__ == "__main__":
    sys.exit(main())
