# Hosted grading API

This reference is for a separately operated grading service, not the public result-submission route.
For community submissions, use [SUBMITTING.md](SUBMITTING.md). Operators configure MRAB_API_URL and issue tokens
privately. Version: v1. All bodies are JSON; requests carry Authorization: Bearer <token>.

The mrab command wraps the API:

    export MRAB_API_URL=https://<api-id>.execute-api.us-west-2.amazonaws.com
    export MRAB_TOKEN=mrab_...
    mrab submit ~/mragentbench/runs --config <config> --model claude-opus-5-5 --agent "Codex CLI 0.130" --wait \
        --results results.json
    mrab submit ~/mragentbench/runs --config <config> ... --addon-manifest path/to/addon.json   # with an add-on
    mrab status                     # your recent submissions
    mrab status <submission_id>     # one submission

| Method and path | Auth | Purpose |
|---|---|---|
| GET /v1/health | none | service status, benchmark version, number of instances |
| GET /v1/instances | none | instance catalog (name, family, domain, time cap, package, package SHA-256) |
| POST /v1/submissions | token | register a submission; returns submission_id and a presigned PUT URL (valid 1 hour) |
| POST /v1/submissions/{id}/start | token | start grading once the bundle is uploaded |
| GET /v1/submissions/{id} | token | status; when done, summary and a results URL (valid 15 minutes) |
| GET /v1/submissions | token | your 20 most recent submissions |

## Register

    POST /v1/submissions
    {
      "config": {"model": "claude-opus-5-5", "agent": "Codex CLI 0.130", "addon": "MRFoundry 0.14.0", "label": "my-run"},
      "runs": [{"instance": "heldout-v7-pcasl-r4", "run": 1, "path": "runs/heldout-v7-pcasl-r4/run1/work"}],
      "bundle_sha256": "<hex>",
      "bundle_bytes": 14200000
    }

Rules: model and agent are required; every instance must exist; run numbers are 1 to 10 and unique per instance; at
most 600 runs and 2 GiB per bundle; each submitter has a daily quota (default 5).

### Add-on submissions

Runs made with an add-on package (docs/EVALUATE-YOUR-SKILLS.md) can carry its manifest. `mrab submit --addon-manifest
path/to/addon.json` validates the package, adds its content hash, refuses runs whose run.json records another content
hash or no add-on, and sends the result as config.addon_manifest:

    "config": {
      "model": "claude-opus-5-5", "agent": "Codex CLI 0.130",
      "addon_manifest": {
        "name": "minimal-example", "version": "1.0.0", "description": "...", "homepage": "https://...",
        "license": "Apache-2.0", "authors": ["..."], "hosts": ["codex", "claude"],
        "exposure": {"public_instances_seen": false, "details": "..."},
        "content_sha256": "<hex, as printed by mrab addon hash>"
      }
    }

The service checks the fields of schemas/addon.schema.json (types, lengths, patterns; unknown fields are refused), that
exposure.details is non-empty unless public_instances_seen is false, that the manifest is at most 16 KiB, and that
content_sha256 is a hex SHA-256. It does not see the package itself, so the hash is the submitter's statement. When
config.addon is not given it becomes "<name> <version>". The manifest is stored with the submission and returned in
config by GET /v1/submissions/{id} and in results.json.

Response 201: {"submission_id": "sub-20261101T235959Z-1a2b3c4d", "upload_url": "...", "upload_method": "PUT", ...}

## Bundle format

A gzip tar with submission.json at the top (format "mragentbench-bundle/1", the config and the runs list) and one
directory per run: runs/<instance>/run<k>/work/ holding the agent's workspace, optionally runs/<instance>/run<k>/run.json.
mrab bundle RUNS_DIR -o bundle.tar.gz builds it from the layout that mrab run writes.

The hosted wire format uses frozen instance IDs, as shown above. Public CLI codes such as `PERF-01-04`
resolve to those IDs before run records are written. See [task numbering](TASK-IDS.md).

## Status values

awaiting_upload, queued, running, done, error. A done submission has a summary: runs, verified, rate (verified runs
divided by runs), instances, pass_all_runs (instances where every run passed) and errors (runs that could not be
graded, for example a missing workspace).

## Results

results.json lists every run with verified, failed_checks, the pass/fail value of each check, grader exit status and
time, and the tail of the grader log. Hosted grading records the environment, not secrecy: graders and reference data
of the public split are public. Results graded this way are labelled "maintainer-graded" on the public board.

## Errors

HTTP 400 (invalid body, including an invalid add-on manifest), 401 (missing or unknown token), 404 (unknown submission), 409 (wrong state, upload missing or
of the wrong size), 429 (daily quota or rate limit). The body is {"error": "<message>"}.
