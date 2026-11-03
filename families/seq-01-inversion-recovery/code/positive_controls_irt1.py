#!/usr/bin/env python3
"""Positive controls for heldout-v5-irt1: acceptable alternative methods must pass every check."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_irt1 import grade

CONTROLS = {
    'magnitude_fit': 'polarity-free magnitude fit |A - B exp(-TI/T1)| with null-position search',
    'direct_recon': 'explicit non-uniform DFT encoding matrix with Tikhonov-regularised normal equations',
    'alt_sequence': 'different design: 2.4 ms inversion, 1.3 ms excitation, 16 us readout dwell',
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

