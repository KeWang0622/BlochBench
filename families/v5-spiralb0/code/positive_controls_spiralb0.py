#!/usr/bin/env python3
"""Positive controls for heldout-v5-spiralb0: acceptable alternative methods must pass every check."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_spiralb0 import grade

CONTROLS = {
    'time_segmented': 'time-segmented NUFFT model (12 segments, least-squares temporal interpolator) solved by CG (sigpy)',
    'alt_sequence': 'different design: 2 us dwell, 85%/80% gradient/slew margins, 0.45 ms excitation',
}

def main():
    out = {}
    for name in (sys.argv[1:] or list(CONTROLS)):
        ws = HERE / 'validation' / f'pos_{name}'
        make_workspace(ws, name)
        g = grade(ws, HERE / 'validation' / f'eval_pos_{name}')
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        out[name] = dict(description=CONTROLS[name], all_pass=g['all_automated_checks_pass'], failed_checks=failed,
                         public=g['measurements'].get('public'), hidden=g['measurements'].get('hidden'))
        print(name, 'PASS' if not failed else failed, flush=True)
    p = HERE / 'validation' / 'positive_controls_result.json'
    prev = json.loads(p.read_text()) if p.exists() else {}
    prev.update(out); p.write_text(json.dumps(prev, indent=1, default=str))

if __name__ == '__main__':
    main()

