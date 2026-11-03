# heldout-v7-epidti-r4: sealed round-4 sibling

Family: heldout-v7-epidti: EPI DTI from raw navigator-corrected EPI with field-map unwarping and gradient-nonlinearity-corrected b-matrices.

Unchanged from the family template (rounds 1 to 3): prompt, deliverables, entrypoint and CLI, file schemas, task.json conventions and accuracy targets, the grader grade_epidti.py and its tolerances, the arm wrapper, _v7common.py, _v7build.py, validate.py (control definitions) and the reference solution. Only gen_data.py CASES (seeds and acquisition, tissue and noise parameters) and the regenerated public inputs, public truth and hidden cases differ, plus the task id.

New instance (all values differ from rounds 1, 2 and 3): public 3 slices, 4 b0, 36 directions, b 950, ESP 0.66 ms, TE 64 ms, PE polarity -1; hidden case1 2 slices, 3 b0, 32 directions, b 1050, ESP 0.54 ms, TE 66 ms, PE polarity -1; hidden case2 3 slices, 2 b0, 27 directions, b 800, ESP 0.60 ms, TE 57 ms, PE polarity +1; new ghost parameters, field maps, gradient-nonlinearity coefficients, fibre directions, object shifts and diffusivity scales; seeds 37901, 39001, 39002. Hidden case1 keeps negative PE polarity because the family control neg_ignore_blip_polarity targets hidden_case1_geometry (a first draft had case1 positive; regenerated and revalidated from scratch).

Validation (private/validation/summary.json, private/validation/eval/<control>/grade.json; reference workspace in reference_ws/, control workspaces in controls/; all graded through the _arm wrapper): reference pass; positives 2/2 pass; negatives 7/7 fail as targeted. Per-control outcomes are listed in private/README.md.

Regenerate data: python private/gen_data.py; rebuild and regrade controls: python private/validate.py (radial-gre-venv interpreter).

