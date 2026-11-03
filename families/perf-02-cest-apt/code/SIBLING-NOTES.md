# heldout-v7-cestapt-r4: sealed round-4 sibling

Family: heldout-v7-cestapt: CEST APT asymmetry with WASSR B0 correction.

Unchanged from the family template (rounds 1 to 3): prompt, deliverables, entrypoint and CLI, file schemas, task.json conventions and accuracy targets, the grader grade_cestapt.py and its tolerances, the arm wrapper, _v7common.py, _v7build.py, validate.py (control definitions) and the reference solution. Only gen_data.py CASES (seeds and acquisition, tissue and noise parameters) and the regenerated public inputs, public truth and hidden cases differ, plus the task id.

New instance (all values differ from rounds 1, 2 and 3): public 11.7 T, B1 1.0 uT, 3.5 s saturation, 105 offsets -5.2..5.2 ppm (0.1 ppm, random order), WASSR +-320 Hz in 16 Hz steps; hidden case1 3.0 T, B1 1.6 uT, 2.2 s, -6..6 ppm in 0.24 ppm steps (reversed interleaved order), WASSR +-140 Hz in 7 Hz steps; hidden case2 9.4 T, B1 0.9 uT, 2.8 s, nonuniform grid dense around +-3.5 ppm (random order), WASSR +-380 Hz in 19 Hz steps; new B0 field shapes and APT/MT scales; seeds 37301, 38401, 38402. The first public grid (0.18 ppm steps) made the linear-interpolation positive control fail on the public set, so the public grid was refined to 0.1 ppm before validation was repeated from scratch.

Validation (private/validation/summary.json, private/validation/eval/<control>/grade.json; reference workspace in reference_ws/, control workspaces in controls/; all graded through the _arm wrapper): reference pass; positives 2/2 pass; negatives 6/6 fail as targeted. Per-control outcomes are listed in private/README.md.

Regenerate data: python private/gen_data.py; rebuild and regrade controls: python private/validate.py (radial-gre-venv interpreter).

