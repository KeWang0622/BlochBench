#!/usr/bin/env python3
"""Positive controls for heldout-v5-learnrecon: acceptable alternative methods that must pass."""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build_workspace, GPY, ENV
MODEL = HERE / 'validation' / 'reference_model'
CONTROLS = [
 ('P1_single_cascade_wider_unet_with_dc', dict(train_opts={'iters': 1, 'base': 32, 'epochs': 30})),
 ('P2_per_echo_l1_wavelet_classical', dict(reuse_model=MODEL, classical_opt={'mode': 'perecho'})),
]
if __name__ == '__main__':
    out = {}; only = sys.argv[1:]
    sp = HERE / 'validation' / 'positive_controls_summary.json'
    if only and sp.exists():
        out = {k: v for k, v in json.loads(sp.read_text()).items() if any(k == n for n, _ in CONTROLS)}
    for name, kw in CONTROLS:
        if only and name not in only:
            continue
        ws = build_workspace(HERE / 'validation' / 'controls' / name, **kw)
        ev = HERE / 'validation' / 'controls' / ('eval_' + name)
        subprocess.run([GPY, str(HERE / 'grade_learnrecon_arm.py'), str(ws), str(ev)], capture_output=True, text=True, env=ENV)
        g = json.loads((ev / 'grade.json').read_text())
        out[name] = {'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']], 'measurements': g['measurements']}
        print(name, out[name]['pass'], out[name]['failed'], flush=True)
    (HERE / 'validation' / 'positive_controls_summary.json').write_text(json.dumps(out, indent=1, default=str))

