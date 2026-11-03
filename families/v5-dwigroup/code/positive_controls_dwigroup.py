#!/usr/bin/env python3
"""Positive controls for heldout-v5-dwigroup: acceptable alternative methods that must pass."""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build_workspace, GPY
CONTROLS = [
 ('P1_ols_fit_b0_interpolated_drift', {'drift': 'interp', 'fit': 'OLS'}),
 ('P2_nlls_fit_linear_drift', {'drift': 'linear', 'fit': 'NLLS'}),
 ('P3_fit_in_voxel_frame_rotated_back', {'frame': 'voxel_proper'}),
]
if __name__ == '__main__':
    out = {}
    for name, opt in CONTROLS:
        ws = build_workspace(HERE / 'validation' / 'controls' / name, opt=opt)
        ev = HERE / 'validation' / 'controls' / ('eval_' + name)
        subprocess.run([GPY, str(HERE / 'grade_dwigroup_arm.py'), str(ws), str(ev)], capture_output=True, text=True)
        g = json.loads((ev / 'grade.json').read_text())
        out[name] = {'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']], 'measurements': g['measurements']}
        print(name, out[name]['pass'], out[name]['failed'])
    (HERE / 'validation' / 'positive_controls_summary.json').write_text(json.dumps(out, indent=1, default=str))

