# Submit results

Public submissions are **self-reported Core results**. Submit a small experiment or the full public suite; each is
labelled with its coverage. Local validation checks record consistency. It does not independently grade work or add
an entry to the frozen paper results.

| Track | Coverage | Use |
|---|---|---|
| `exploratory` | An explicitly listed subset; the same number of attempts per instance | Try an agent, model or add-on |
| `full-core` | All 88 public Core instances, three attempts each (264 attempts) | Full public-suite report |

The paper's 24-instance Core snapshot is a different evaluation. Do not compare different subsets, repeat counts,
network settings or time caps as one ranking. Hard tasks are not accepted through the public submission channel.

## 1. Run and export

Use a single configuration name and a separate run number for each attempt. Every started attempt counts, including
timeouts, crashes and interruptions. Follow the [quick start](GETTING-STARTED.md) and keep agent workspaces outside
the repository.

```bash
mrab run heldout-v7-pcasl-r4 --agent codex --model MODEL --config my-agent --run 1
python tools/prepare_submission.py ~/mragentbench/runs --config my-agent --output ../my-submission
```

The exporter copies run records, start records, grades and compressed traces. It excludes the agent workspace and
does not execute code. It also includes folders that have `started.json` but no final `run.json`, counting those
unfinished attempts as failures with unknown token use and duration. Explain each in `incomplete.json`; do not rerun
over an existing attempt or discard it. Complete the declared repeat schedule before submitting.

`mrab collect` alone omits unfinished attempts. `mrab bundle` prepares workspaces for the optional hosted-grading
client; it is not the public-results format. No hosted account or token is needed for this submission workflow.

## 2. Review and validate

Edit the exported `metadata.json`: record the full benchmark commit used, model and agent version, task IDs, repeat
count, network policy, hardware, add-on hash and deviations. Set `all_started_runs_included` to `true` after checking
the original run directory. Use `null` for an unavailable agent version and explain it under `deviations`.

Review records and traces for credentials, personal information and local paths before sharing. List any redactions
under `redactions`; preserve task IDs, outcomes, settings, hashes and resource totals. Do not include Hard material.

```bash
python tools/validate_submission.py ../my-submission > ../my-submission/validation.json
tar -czf ../my-submission.tar.gz -C .. my-submission
shasum -a 256 ../my-submission.tar.gz
```

Validation requires one CSV row and evidence folder for each declared attempt. It checks duplicates, public task
membership, family/domain, model/host settings, task and add-on hashes, completion against grade checks, and resource
totals. Unfinished attempts remain in the completion denominator; missing resource values are reported separately.
The benchmark commit, network settings, hardware and completeness declaration remain submitter attestations; task
hashes are checked against the local catalog.

```text
my-submission/
  metadata.json
  runs.csv                         # mrab collect columns; blank resources when unknown
  validation.json
  records/<instance>/run<k>/
    started.json
    run.json                       # or incomplete.json with a reason
    grade.json                     # when grading completed
    trace.jsonl.gz                  # completed attempts; partial trace if available otherwise
```

The [metadata template](../examples/submission/metadata.json) defines the required fields. Keep one configuration per
bundle. For an add-on comparison, export both configurations and provide the `mrab compare` output, add-on manifest
and content hash; see [paired evaluation](EVALUATE-YOUR-SKILLS.md).

## 3. Share the report

Open a [Results submission issue](https://github.com/KeWang0622/BlochBench/issues/new?template=results.yml). Include
`metadata.json`, the validation output, a public download link to the archive, and its SHA-256. A GitHub Release asset
or other stable public file host works. Avoid committing large traces to this repository.

A pull request may instead add a small `leaderboard/submissions/<date>-<name>/README.md` containing the same links,
hash, metadata and validation output. Maintainers review provenance and consistency before listing a community result.
Submission artifacts are never executed in pull-request CI. Independent regrading, if arranged separately, must use
an isolated environment. An accepted public report remains labelled self-reported.
