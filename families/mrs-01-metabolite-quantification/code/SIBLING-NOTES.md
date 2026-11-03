# heldout-v7-mrsquant-r4: sealed round-4 sibling

Family: heldout-v7-mrsquant: MRS quantification (multi-coil single-voxel PRESS with water reference: coil combination, eddy-current and frequency/phase correction, relaxation and partial-volume corrected concentrations).

Unchanged from the family template (rounds 1 to 3): prompt, deliverables, entrypoint and CLI, file schemas, task.json conventions and accuracy targets, the grader grade_mrsquant.py and its tolerances, the arm wrapper, _v7common.py, _v7build.py, validate.py (control definitions) and the reference solution. Only gen_data.py CASES (seeds and acquisition, tissue and noise parameters) and the regenerated public inputs, public truth and hidden cases differ, plus the task id.

New instance (all values differ from rounds 1, 2 and 3): public 63.65 MHz (1.5 T), TE 40 ms, TR 2.4 s, 88 transients; hidden case1 298.03 MHz (7 T), TE 28 ms, TR 5.5 s, 56 transients; hidden case2 200.3 MHz (4.7 T), TE 45 ms, TR 3.4 s, 76 transients; new field-specific water and metabolite relaxation tables, tissue fractions, linewidths, eddy-current amplitudes and time constants, coil sensitivities, drifts, phase jitter and concentrations; seeds 37701, 38801, 38802.

Validation (private/validation/summary.json, private/validation/eval/<control>/grade.json; reference workspace in reference_ws/, control workspaces in controls/; all graded through the _arm wrapper): reference pass; positives 2/2 pass; negatives 6/6 fail as targeted. Per-control outcomes are listed in private/README.md.

Regenerate data: python private/gen_data.py; rebuild and regrade controls: python private/validate.py (radial-gre-venv interpreter).

