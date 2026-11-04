"""AWS Lambda handler for the MRI Agent Bench hosted grading API (HTTP API v2 payloads and AWS Batch events).

Routes
  GET  /v1/health                        service status (no authentication)
  GET  /v1/instances                     public instance catalog (no authentication)
  POST /v1/submissions                   register a submission, get a presigned upload URL
  POST /v1/submissions/{id}/start        start grading after the upload
  GET  /v1/submissions/{id}              status and, when done, the results summary and a download URL
  GET  /v1/submissions                   the caller's recent submissions
  POST /v1/jobs/{id}/results             grading job callback (X-Job-Token, not a submitter token)

Submitters authenticate with "Authorization: Bearer <token>". Only the SHA-256 of each token is stored.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config

REGION = os.environ.get("AWS_REGION", "us-west-2")
S3 = boto3.client("s3", region_name=REGION, config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
BATCH = boto3.client("batch", region_name=REGION)
DDB = boto3.resource("dynamodb", region_name=REGION)
SUBMISSIONS = DDB.Table(os.environ.get("SUBMISSIONS_TABLE", "mragentbench-submissions"))
SUBMITTERS = DDB.Table(os.environ.get("SUBMITTERS_TABLE", "mragentbench-submitters"))
SUB_BUCKET = os.environ.get("SUBMISSIONS_BUCKET", "")
DATA_BUCKET = os.environ.get("DATA_BUCKET", "mragentbench-data")
DATA_PREFIX = os.environ.get("DATA_PREFIX", "v1/public/")
JOB_QUEUE = os.environ.get("JOB_QUEUE", "")
JOB_DEFINITION = os.environ.get("JOB_DEFINITION", "")
API_URL = os.environ.get("API_URL", "")
MAX_BUNDLE_BYTES = int(os.environ.get("MAX_BUNDLE_BYTES", str(2 * 1024**3)))
MAX_SHARDS = int(os.environ.get("MAX_SHARDS", "16"))
MAX_RUNS = int(os.environ.get("MAX_RUNS", "600"))
URL_TTL = int(os.environ.get("URL_TTL_SECONDS", "21600"))
VERSION = os.environ.get("BENCHMARK_VERSION", "0.1.0")
CATALOG_FILE = os.environ.get("MRAB_CATALOG_FILE", os.path.join(os.path.dirname(__file__), "catalog.json"))
with open(CATALOG_FILE) as _f:
    CATALOG: dict = json.load(_f)
ID_RE = re.compile(r"^sub-\d{8}T\d{6}Z-[0-9a-f]{8}$")
# Add-on manifests (mrab submit --addon-manifest): the client validates the package against schemas/addon.schema.json;
# the service re-checks the types and sizes of what it stores and shows with the results.
MAX_ADDON_MANIFEST_BYTES = 16 * 1024
ADDON_FIELDS = ("name", "version", "description", "homepage", "license", "authors", "hosts", "exposure")
ADDON_TEXT = {
    "name": (64, re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")),
    "version": (40, re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]{0,39}")),
    "description": (1024, None),
    "homepage": (500, re.compile(r"https?://\S+")),
    "license": (100, None),
}
ADDON_HOSTS = ("codex", "claude")


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def respond(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body, default=lambda o: int(o) if isinstance(o, Decimal) and o % 1 == 0 else float(o)),
    }


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def authenticate(event: dict) -> dict:
    auth = (event.get("headers") or {}).get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HttpError(401, "missing bearer token")
    item = SUBMITTERS.get_item(Key={"token_sha256": _sha(auth[7:].strip())}).get("Item")
    if not item or not item.get("active", True):
        raise HttpError(401, "unknown or inactive token")
    return item


def _body(event: dict) -> dict:
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HttpError(400, "body is not valid JSON") from None


def _owned(event: dict, submitter: dict) -> dict:
    sid = (event.get("pathParameters") or {}).get("id", "")
    if not ID_RE.match(sid):
        raise HttpError(404, "no such submission")
    item = SUBMISSIONS.get_item(Key={"submission_id": sid}).get("Item")
    if not item or item["submitter"] != submitter["submitter"]:
        raise HttpError(404, "no such submission")
    return item


def validate_addon_manifest(manifest: object) -> dict:
    """Check the optional add-on manifest of a submission (types, sizes, content hash); returns a clean copy."""
    where = "config.addon_manifest"
    if not isinstance(manifest, dict):
        raise HttpError(400, f"{where} must be an object")
    if len(json.dumps(manifest)) > MAX_ADDON_MANIFEST_BYTES:
        raise HttpError(400, f"{where} is larger than {MAX_ADDON_MANIFEST_BYTES} bytes")
    unknown = sorted(set(manifest) - set(ADDON_FIELDS) - {"$schema", "metadata", "content_sha256"})
    if unknown:
        raise HttpError(400, f"{where}: unknown fields {', '.join(unknown)}")
    clean: dict = {}
    for key, (limit, pattern) in ADDON_TEXT.items():
        value = manifest.get(key)
        if not isinstance(value, str) or not 0 < len(value) <= limit or (pattern and not pattern.fullmatch(value)):
            raise HttpError(400, f"{where}.{key} is required (string, at most {limit} characters)")
        clean[key] = value
    authors = manifest.get("authors")
    if (
        not isinstance(authors, list)
        or not 0 < len(authors) <= 50
        or not all(isinstance(a, str) and 0 < len(a) <= 200 for a in authors)
    ):
        raise HttpError(400, f"{where}.authors must be a list of 1 to 50 names")
    clean["authors"] = authors
    hosts = manifest.get("hosts")
    if (
        not isinstance(hosts, list)
        or not hosts
        or not all(isinstance(h, str) for h in hosts)
        or len(set(hosts)) != len(hosts)
        or not set(hosts) <= set(ADDON_HOSTS)
    ):
        raise HttpError(400, f"{where}.hosts must be a non-empty list of distinct values from {', '.join(ADDON_HOSTS)}")
    clean["hosts"] = hosts
    exposure = manifest.get("exposure")
    seen = exposure.get("public_instances_seen") if isinstance(exposure, dict) else None
    details = exposure.get("details") if isinstance(exposure, dict) else None
    if (
        not isinstance(exposure, dict)
        or set(exposure) != {"public_instances_seen", "details"}
        or not (isinstance(seen, bool) or seen == "partial")
        or not isinstance(details, str)
        or len(details) > 2000
    ):
        raise HttpError(
            400, f'{where}.exposure needs public_instances_seen (true, false or "partial") and details (string)'
        )
    if seen is not False and not details.strip():
        raise HttpError(400, f"{where}.exposure.details must say what was seen unless public_instances_seen is false")
    clean["exposure"] = {"public_instances_seen": seen, "details": details}
    metadata = manifest.get("metadata")
    if metadata is not None:
        if (
            not isinstance(metadata, dict)
            or len(metadata) > 50
            or not all(isinstance(k, str) and isinstance(v, str) and len(k) <= 100 for k, v in metadata.items())
            or any(len(v) > 500 for v in metadata.values())
        ):
            raise HttpError(400, f"{where}.metadata must map at most 50 names to strings of at most 500 characters")
        clean["metadata"] = metadata
    digest = manifest.get("content_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise HttpError(400, f"{where}.content_sha256 must be the hex SHA-256 printed by mrab addon hash")
    clean["content_sha256"] = digest
    return clean


def validate_submission(body: dict) -> dict:
    if not isinstance(body, dict) or not isinstance(body.get("config") or {}, dict):
        raise HttpError(400, "body and config must be JSON objects")
    cfg = body.get("config") or {}
    for k in ("model", "agent"):
        if not isinstance(cfg.get(k), str) or not 0 < len(cfg[k]) <= 120:
            raise HttpError(400, f"config.{k} is required (string, at most 120 characters)")
    runs = body.get("runs")
    if not isinstance(runs, list) or not 0 < len(runs) <= MAX_RUNS:
        raise HttpError(400, f"runs must be a list of 1 to {MAX_RUNS} entries")
    seen = set()
    for r in runs:
        if not isinstance(r, dict):
            raise HttpError(400, "each run must be a JSON object")
        name, k = r.get("instance"), r.get("run")
        if not isinstance(name, str) or name not in CATALOG:
            raise HttpError(400, f"unknown instance {name!r}")
        if not isinstance(k, int) or not 1 <= k <= 10 or (name, k) in seen:
            raise HttpError(400, f"run numbers must be unique integers 1-10 per instance ({name})")
        if not isinstance(r.get("path"), str) or r["path"].startswith("/") or ".." in r["path"].split("/"):
            raise HttpError(400, "each run needs a relative path inside the bundle")
        seen.add((name, k))
    sha, size = body.get("bundle_sha256", ""), body.get("bundle_bytes")
    if not re.fullmatch(r"[0-9a-f]{64}", sha or ""):
        raise HttpError(400, "bundle_sha256 must be a hex SHA-256")
    if not isinstance(size, int) or not 0 < size <= MAX_BUNDLE_BYTES:
        raise HttpError(400, f"bundle_bytes must be between 1 and {MAX_BUNDLE_BYTES}")
    clean_cfg = {k: str(cfg[k])[:500] for k in ("model", "agent", "addon", "label", "notes") if cfg.get(k)}
    if cfg.get("addon_manifest") is not None:
        manifest = validate_addon_manifest(cfg["addon_manifest"])
        clean_cfg["addon_manifest"] = manifest
        clean_cfg.setdefault("addon", f"{manifest['name']} {manifest['version']}")
    return dict(
        config=clean_cfg,
        runs=[{"instance": r["instance"], "run": r["run"], "path": r["path"]} for r in runs],
        bundle_sha256=sha,
        bundle_bytes=size,
    )


def create_submission(event: dict) -> dict:
    who = authenticate(event)
    sub = validate_submission(_body(event))
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 86400))
    recent = SUBMISSIONS.query(
        IndexName="by-submitter",
        Select="COUNT",
        KeyConditionExpression=Key("submitter").eq(who["submitter"]) & Key("created_at").gt(since),
    )
    quota = int(who.get("daily_quota", 5))
    if recent["Count"] >= quota:
        raise HttpError(429, f"daily quota of {quota} submissions reached")
    sid = time.strftime("sub-%Y%m%dT%H%M%SZ-", time.gmtime()) + secrets.token_hex(4)
    key = f"bundles/{sid}.tar.gz"
    SUBMISSIONS.put_item(
        Item=dict(
            submission_id=sid,
            submitter=who["submitter"],
            status="awaiting_upload",
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            benchmark_version=VERSION,
            bundle_key=key,
            **sub,
        ),
        ConditionExpression="attribute_not_exists(submission_id)",
    )
    url = S3.generate_presigned_url("put_object", Params={"Bucket": SUB_BUCKET, "Key": key}, ExpiresIn=3600)
    return respond(
        201,
        {
            "submission_id": sid,
            "status": "awaiting_upload",
            "upload_url": url,
            "upload_method": "PUT",
            "upload_expires_in": 3600,
            "next": f"POST /v1/submissions/{sid}/start",
        },
    )


def start_submission(event: dict) -> dict:
    who = authenticate(event)
    item = _owned(event, who)
    if item["status"] != "awaiting_upload":
        raise HttpError(409, f"submission is {item['status']}")
    try:
        head = S3.head_object(Bucket=SUB_BUCKET, Key=item["bundle_key"])
    except S3.exceptions.ClientError:
        raise HttpError(409, "bundle not uploaded yet") from None
    if head["ContentLength"] != int(item["bundle_bytes"]):
        raise HttpError(409, f"uploaded {head['ContentLength']} bytes, declared {int(item['bundle_bytes'])}")
    sid = item["submission_id"]
    names = sorted({r["instance"] for r in item["runs"]})
    shards = max(1, min(MAX_SHARDS, len(item["runs"]) // 4 or 1, len(item["runs"])))
    token = secrets.token_urlsafe(32)

    def presign(bucket: str, key: str) -> str:
        return S3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=URL_TTL)

    spec = dict(
        submission_id=sid,
        shards=shards,
        grade_timeout_s=1800,
        bundle_url=presign(SUB_BUCKET, item["bundle_key"]),
        bundle_sha256=item["bundle_sha256"],
        callback_url=f"{API_URL.rstrip('/')}/v1/jobs/{sid}/results",
        job_token=token,
        instances={
            n: dict(
                url=presign(DATA_BUCKET, DATA_PREFIX + CATALOG[n]["package"]),
                package=CATALOG[n]["package"],
                package_sha256=CATALOG[n].get("package_sha256"),
                manifest_sha256=CATALOG[n].get("manifest_sha256"),
                grader=CATALOG[n]["grader"],
            )
            for n in names
        },
    )
    spec_key = f"jobs/{sid}.json"
    S3.put_object(Bucket=SUB_BUCKET, Key=spec_key, Body=json.dumps(spec).encode(), ContentType="application/json")
    job = dict(
        jobName=f"grade-{sid}",
        jobQueue=JOB_QUEUE,
        jobDefinition=JOB_DEFINITION,
        containerOverrides={"environment": [{"name": "MRAB_JOB_SPEC_URL", "value": presign(SUB_BUCKET, spec_key)}]},
        tags={"submission": sid},
        propagateTags=True,
    )
    if shards > 1:
        job["arrayProperties"] = {"size": shards}
    job_id = BATCH.submit_job(**job)["jobId"]
    SUBMISSIONS.update_item(
        Key={"submission_id": sid},
        UpdateExpression="SET #s=:q, job_id=:j, shards=:n, shards_done=:z, job_token_sha256=:t, started_at=:now",
        ConditionExpression="#s = :a",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":q": "queued",
            ":j": job_id,
            ":n": shards,
            ":z": [],
            ":t": _sha(token),
            ":a": "awaiting_upload",
            ":now": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    return respond(202, {"submission_id": sid, "status": "queued", "job_id": job_id, "shards": shards})


def get_submission(event: dict) -> dict:
    item = _owned(event, authenticate(event))
    out = {
        k: item.get(k)
        for k in (
            "submission_id",
            "status",
            "created_at",
            "started_at",
            "finished_at",
            "config",
            "benchmark_version",
            "shards",
            "summary",
            "error",
        )
    }
    out["shards_done"] = len(item.get("shards_done") or [])
    if item["status"] == "done":
        out["results_url"] = S3.generate_presigned_url(
            "get_object",
            Params={"Bucket": SUB_BUCKET, "Key": f"submissions/{item['submission_id']}/results.json"},
            ExpiresIn=900,
        )
    return respond(200, out)


def list_submissions(event: dict) -> dict:
    who = authenticate(event)
    q = SUBMISSIONS.query(
        IndexName="by-submitter",
        KeyConditionExpression=Key("submitter").eq(who["submitter"]),
        ScanIndexForward=False,
        Limit=20,
    )
    return respond(
        200,
        {
            "submissions": [
                {k: i.get(k) for k in ("submission_id", "status", "created_at", "config", "summary")}
                for i in q["Items"]
            ]
        },
    )


def summarize(runs: list[dict]) -> dict:
    by = {}
    for r in runs:
        by.setdefault(r["instance"], []).append(bool(r.get("verified")))
    n, k = len(runs), sum(bool(r.get("verified")) for r in runs)
    return dict(
        runs=n,
        verified=k,
        rate=round(k / n, 4) if n else 0.0,
        instances=len(by),
        pass_all_runs=sum(all(v) for v in by.values()),
        errors=sum(1 for r in runs if r.get("error")),
    )


def job_results(event: dict) -> dict:
    sid = (event.get("pathParameters") or {}).get("id", "")
    item = SUBMISSIONS.get_item(Key={"submission_id": sid}).get("Item") if ID_RE.match(sid) else None
    token = (event.get("headers") or {}).get("x-job-token", "")
    if not item or not token or not secrets.compare_digest(_sha(token), item.get("job_token_sha256", "")):
        raise HttpError(403, "forbidden")
    result = _body(event)
    shard = result.get("shard")
    if not isinstance(shard, int) or not 0 <= shard < int(item["shards"]):
        raise HttpError(400, "bad shard")
    S3.put_object(
        Bucket=SUB_BUCKET,
        Key=f"submissions/{sid}/results/part-{shard:03d}.json",
        Body=json.dumps(result).encode(),
        ContentType="application/json",
    )
    try:
        upd = SUBMISSIONS.update_item(
            Key={"submission_id": sid},
            UpdateExpression="SET shards_done=list_append(shards_done, :s), #s=:r",
            ConditionExpression="#s IN (:q, :r)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": [shard], ":r": "running", ":q": "queued"},
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except DDB.meta.client.exceptions.ConditionalCheckFailedException:
        return respond(200, {"ok": True, "note": "submission already final"})
    if len(set(int(x) for x in upd["shards_done"])) >= int(upd["shards"]):
        finalize(upd)
    return respond(200, {"ok": True})


def finalize(item: dict) -> None:
    sid = item["submission_id"]
    runs, errors = [], []
    for s in range(int(item["shards"])):
        part = json.loads(
            S3.get_object(Bucket=SUB_BUCKET, Key=f"submissions/{sid}/results/part-{s:03d}.json")["Body"].read()
        )
        runs += part.get("runs", [])
        if part.get("error"):
            errors.append(f"shard {s}: {part['error']}")
    runs.sort(key=lambda r: (r["instance"], r["run"]))
    summary = summarize(runs)
    doc = dict(
        submission_id=sid,
        benchmark_version=item.get("benchmark_version"),
        config=item.get("config"),
        graded_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        grader="hosted (maintainer environment)",
        summary=summary,
        shard_errors=errors,
        runs=runs,
    )
    S3.put_object(
        Bucket=SUB_BUCKET,
        Key=f"submissions/{sid}/results.json",
        Body=json.dumps(doc, indent=1).encode(),
        ContentType="application/json",
    )
    SUBMISSIONS.update_item(
        Key={"submission_id": sid},
        UpdateExpression="SET #s=:d, summary=:m, finished_at=:t" + (", #e=:e" if errors else ""),
        ExpressionAttributeNames={"#s": "status", **({"#e": "error"} if errors else {})},
        ExpressionAttributeValues={
            ":d": "done",
            ":m": json.loads(json.dumps(summary), parse_float=Decimal),
            ":t": doc["graded_at"],
            **({":e": "; ".join(errors)[:1000]} if errors else {}),
        },
    )


def on_batch_event(event: dict) -> dict:
    d = event.get("detail", {})
    sid = (d.get("tags") or {}).get("submission") or d.get("jobName", "").removeprefix("grade-")
    if "index" in (d.get("arrayProperties") or {}):  # children of an array job: wait for the parent's event
        return {"ignored": True}
    if d.get("status") not in ("FAILED", "SUCCEEDED") or not ID_RE.match(sid or ""):
        return {"ignored": True}
    item = SUBMISSIONS.get_item(Key={"submission_id": sid}).get("Item")
    if not item or item["status"] == "done":
        return {"ignored": True}
    reason = d.get("statusReason") or (
        "job finished without posting every shard" if d["status"] == "SUCCEEDED" else "job failed"
    )
    SUBMISSIONS.update_item(
        Key={"submission_id": sid},
        UpdateExpression="SET #s=:e, #r=:m, finished_at=:t",
        ExpressionAttributeNames={"#s": "status", "#r": "error"},
        ExpressionAttributeValues={
            ":e": "error",
            ":m": reason[:1000],
            ":t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    return {"updated": sid}


ROUTES = {
    "GET /v1/health": lambda e: respond(200, {"status": "ok", "benchmark_version": VERSION, "instances": len(CATALOG)}),
    "GET /v1/instances": lambda e: respond(
        200,
        {
            "instances": [
                {k: v.get(k) for k in ("instance", "family", "domain", "cap_s", "package", "package_sha256")}
                for v in CATALOG.values()
            ]
        },
    ),
    "POST /v1/submissions": create_submission,
    "GET /v1/submissions": list_submissions,
    "POST /v1/submissions/{id}/start": start_submission,
    "GET /v1/submissions/{id}": get_submission,
    "POST /v1/jobs/{id}/results": job_results,
}


def handler(event: dict, context=None) -> dict:
    if event.get("source") == "aws.batch":
        return on_batch_event(event)
    route = ROUTES.get(event.get("routeKey", ""))
    if not route:
        return respond(404, {"error": "not found"})
    try:
        return route(event)
    except HttpError as e:
        return respond(e.status, {"error": e.message})
