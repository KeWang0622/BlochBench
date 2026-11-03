# heldout-v7-pcasl-r4: sealed round-4 sibling

Family: heldout-v7-pcasl: perfusion (pCASL CBF quantification with slice timing, background suppression, M0 TR and labelling efficiency).

Unchanged from the family template (rounds 1 to 3): prompt, deliverables, entrypoint and CLI, file schemas, task.json conventions and accuracy targets, the grader grade_pcasl.py and its tolerances, the arm wrapper, _v7common.py, _v7build.py, validate.py (control definitions) and the reference solution. Only gen_data.py CASES (seeds and acquisition, tissue and noise parameters) and the regenerated public inputs, public truth and hidden cases differ, plus the task id.

New instance (all values differ from rounds 1, 2 and 3): public 11 slices (descending odd-first order, 52 ms slice interval), LD 1.6 s, PLD 1.9 s, alpha 0.81, 3 BS pulses at 0.91, M0 TR 2.8 s, label first, T1 blood 1.58 s, CBF 56/21.5; hidden case1 17 slices ascending, LD 1.9 s, PLD 1.75 s, alpha 0.89, 2 BS pulses at 0.97, M0 TR 1.9 s, T1 blood 1.68 s, CBF 66/25.5; hidden case2 10 slices odd-first, LD 1.45 s, PLD 2.1 s, alpha 0.79, 4 BS pulses at 0.945, M0 TR 2.4 s, T1 blood 1.42 s, CBF 46/18; new tissue T1 and M0 values, pair counts and noise levels; seeds 37101, 38211, 38322.

Validation (private/validation/summary.json, private/validation/eval/<control>/grade.json; reference workspace in reference_ws/, control workspaces in controls/; all graded through the _arm wrapper): reference pass; positives 2/2 pass; negatives 7/7 fail as targeted. Per-control outcomes are listed in private/README.md.

Regenerate data: python private/gen_data.py; rebuild and regrade controls: python private/validate.py (radial-gre-venv interpreter).

