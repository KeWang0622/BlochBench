# Core data

The [Core v0.1.0 release](https://github.com/KeWang0622/BlochBench/releases/tag/core-v0.1.0) contains 88 frozen instance
packages (5.74 GB total). Download one task at a time with `mrab fetch`; a GitHub account is not needed.

```bash
mrab fetch heldout-v7-pcasl-r4
mrab verify heldout-v7-pcasl-r4
```

Default package base URL:
`https://github.com/KeWang0622/BlochBench/releases/download/core-v0.1.0`.
Set `MRAB_DATA_URL` or pass `mrab fetch <instance> --url <base-url>` to use a mirror.
For an existing extracted collection, use `mrab fetch <instance> --from-dir <collection>`.

## Package contents

| Path | Purpose | Agent access |
|---|---|---|
| `prompt.txt` | Requested task and deliverables | Copied to `TASK.txt` |
| `public/` | Task specification and input data | Copied to its workspace |
| `private/` | Grader, ground truth, reference solution and validation controls | Evaluator only |
| `FROZEN-SHA256.txt` | File integrity manifest | Evaluator only |

Here `private/` describes isolation **during an attempt**. Core packages are released in full for reproducibility;
it does not mean those files are secret after download. Hard packages are not included in this release.

## Integrity and versioning

[`families/*/instances.json`](../families/) pins each package SHA-256, byte size and manifest hash.
`mrab fetch` checks the package hash; `mrab verify` checks the manifest and every listed file. The release preserves every frozen file and manifest, including legacy technical IDs. Eighteen archives had
unmanifested environment artifacts removed so safe extraction works; 70 archives are byte-identical to the originals.
[Packaging provenance](DATA-PACKAGING.md) records old/new package hashes. Do not regenerate task data to reproduce the study.
Some frozen reference scripts retain original workstation defaults; the supported runner passes explicit paths.

[`croissant.json`](../croissant.json) describes the dataset. Its `catalog.csv` is also attached to the release.
Code is Apache-2.0 and task data/documentation are CC BY 4.0; see [LICENSE-DATA.md](../LICENSE-DATA.md).

Maintain package hashes across mirrors. A scoring change needs a versioned benchmark update, with regrading or
rerunning declared in [CHANGELOG.md](../CHANGELOG.md).
