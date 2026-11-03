#!/usr/bin/env python3
"""positive controls for heldout-v4-qsm: each variant of reference_solution.py is run as qsm.py in a clean workspace and graded."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import validation_harness as H
import reference_solution as R
CONTROLS = {'pos_tkd': [], 'pos_closed_form_tikhonov': []}
out = []
for mode, targeted in CONTROLS.items():
    ws, g = R.run_case(mode, H.entry_from(HERE/'reference_solution.py', mode))
    s = H.summarize(mode, g, targeted if targeted else None)
    s['measurements'] = g['measurements']
    out.append(s); print(json.dumps({k: s[k] for k in s if k != 'measurements'}), flush=True)
(HERE/'validation'/'positive_controls_summary.json').write_text(json.dumps(out, indent=1))

