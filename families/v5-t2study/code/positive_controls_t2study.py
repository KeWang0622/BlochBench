#!/usr/bin/env python3
"""Positive controls for heldout-v5-t2study: acceptable alternative methods must pass every check."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_t2study import grade

CONTROLS = {
    'lowres_sens': 'SENSE with low-resolution ACS sensitivities (no ESPIRiT), same fit',
    'grappa_rss': 'GRAPPA (2x3 kernel, own implementation) + root-sum-of-squares magnitude + weighted log-linear fit',
}

def main():
    out = {}
    for name in (sys.argv[1:] or list(CONTROLS)):
        ws = HERE / 'validation' / f'pos_{name}'
        make_workspace(ws, name)
        g = grade(ws, HERE / 'validation' / f'eval_pos_{name}')
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        out[name] = dict(description=CONTROLS[name], all_pass=g['all_automated_checks_pass'], failed_checks=failed,
                         per_scan=g['checks']['per_scan_roi_accuracy']['detail'], maps=g['checks']['t2map_files_consistent']['detail'])
        print(name, 'PASS' if not failed else failed, json.dumps(out[name]['per_scan']), flush=True)
    p = HERE / 'validation' / 'positive_controls_result.json'
    prev = json.loads(p.read_text()) if p.exists() else {}
    prev.update(out); p.write_text(json.dumps(prev, indent=1, default=str))

if __name__ == '__main__':
    main()

