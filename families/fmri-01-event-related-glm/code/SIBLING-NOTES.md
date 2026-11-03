# heldout-v7-fmriglm-r4: sealed round-4 sibling

Family: heldout-v7-fmriglm: task fMRI GLM (slice timing, dummy volumes, motion regressors, AR(1) prewhitening, high-pass) to percent signal change.

Unchanged from the family template (rounds 1 to 3): prompt, deliverables, entrypoint and CLI, file schemas, task.json conventions and accuracy targets, the grader grade_fmriglm.py and its tolerances, the arm wrapper, _v7common.py, _v7build.py, validate.py (control definitions) and the reference solution. Only gen_data.py CASES (seeds and acquisition, tissue and noise parameters) and the regenerated public inputs, public truth and hidden cases differ, plus the task id.

New instance (all values differ from rounds 1, 2 and 3): public 13 slices, TR 2.3 s, 3 dummies, 220 volumes, descending interleaved slice order; hidden case1 16 slices, TR 1.9 s, 5 dummies, 262 volumes, odd-first order; hidden case2 11 slices, TR 2.7 s, 4 dummies, 188 volumes, descending order; new amplitude and ISI ranges, motion coupling, drift, AR(1) and dummy decay factors; seeds 37501, 38601, 38602.

Validation (private/validation/summary.json, private/validation/eval/<control>/grade.json; reference workspace in reference_ws/, control workspaces in controls/; all graded through the _arm wrapper): reference pass; positives 2/2 pass; negatives 6/6 fail as targeted. Per-control outcomes are listed in private/README.md.

Regenerate data: python private/gen_data.py; rebuild and regrade controls: python private/validate.py (radial-gre-venv interpreter).

