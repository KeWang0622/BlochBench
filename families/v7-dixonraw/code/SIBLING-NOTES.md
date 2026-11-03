# heldout-v7-dixonraw-r4: sealed round-4 sibling

Family: heldout-v7-dixonraw: chemical-shift-encoded water-fat (raw multi-coil multi-echo k-space to PDFF and R2*).

Unchanged from the family template (rounds 1 to 3): prompt, deliverables, entrypoint and CLI, file schemas, task.json conventions and accuracy targets, the grader grade_dixonraw.py and its tolerances, the arm wrapper, _v7common.py, _v7build.py, validate.py (control definitions) and the reference solution. Only gen_data.py CASES (seeds and acquisition, tissue and noise parameters) and the regenerated public inputs, public truth and hidden cases differ, plus the task id.

New instance (all values differ from rounds 1, 2 and 3): public 1.5 T, 84 matrix, 7 coils, TE1 1.7 ms, dTE 2.2 ms, TR 12.5 ms, flip 13 deg; hidden case1 2.89 T, 104 matrix, 11 coils, TE1 1.05 ms, dTE 0.98 ms, TR 8.2 ms, flip 17 deg; hidden case2 3.0 T, 90 matrix, 6 coils, TE1 1.22 ms, dTE 1.08 ms, TR 7.8 ms, flip 19 deg; new water/fat T1, vial PDFF and R2* values, field-map shapes, B1 fields, coil phases; seeds 37801, 38901, 38902.

Validation (private/validation/summary.json, private/validation/eval/<control>/grade.json; reference workspace in reference_ws/, control workspaces in controls/; all graded through the _arm wrapper): reference pass; positives 2/2 pass; negatives 7/7 fail as targeted. Per-control outcomes are listed in private/README.md.

Regenerate data: python private/gen_data.py; rebuild and regrade controls: python private/validate.py (radial-gre-venv interpreter).

