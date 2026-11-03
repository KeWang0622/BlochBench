#!/usr/bin/env python3
"""negative controls for heldout-v4-qsm: each variant of reference_solution.py is run as qsm.py in a clean workspace and graded."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import validation_harness as H
import reference_solution as R
CONTROLS = {'neg_no_background_removal': ['public_local_field', 'public_roi_susceptibility', 'public_chi_map', 'hidden_local_field'],
            'neg_wrong_b0_direction': ['public_roi_susceptibility', 'public_chi_map'],
            'neg_isotropic_voxel': ['public_local_field', 'public_chi_map', 'hidden_local_field', 'hidden_chi_map'],
            'neg_phase_raw_int': ['public_local_field', 'public_roi_susceptibility', 'public_chi_map', 'hidden_local_field'],
            'neg_hz_to_ppm_rad': ['public_roi_susceptibility', 'hidden_roi_susceptibility'],
            'neg_sign_flip': ['public_local_field', 'public_roi_susceptibility', 'public_chi_map', 'hidden_roi_susceptibility']}
out = []
for mode, targeted in CONTROLS.items():
    ws, g = R.run_case(mode, H.entry_from(HERE/'reference_solution.py', mode))
    s = H.summarize(mode, g, targeted if targeted else None)
    s['measurements'] = g['measurements']
    out.append(s); print(json.dumps({k: s[k] for k in s if k != 'measurements'}), flush=True)
(HERE/'validation'/'negative_controls_summary.json').write_text(json.dumps(out, indent=1))

