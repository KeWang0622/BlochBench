#!/usr/bin/env python3
"""Positive controls for heldout-v4-t2epg: acceptable alternative methods must pass every check."""
import json, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build
from grade_t2epg import grade

CONTROLS = {'epg_gauss_newton': dict(method='gauss_newton'), 'epg_dictionary_noise_truncated': dict(method='dictionary_truncated')}

if __name__ == '__main__':
    base = Path(tempfile.mkdtemp(prefix='pc_t2epg_', dir=str(HERE.parents[1] / '_trash')))
    res = {}
    for name, kw in CONTROLS.items():
        ws = build(base / name, **kw)
        g = grade(ws, base / (name + '_eval'), Path(sys.executable))
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        res[name] = {'options': kw, 'pass': g['all_automated_checks_pass'], 'failed_checks': failed,
                     'public': g['measurements'].get('public'), 'hidden': g['measurements'].get('hidden')}
        print(name, res[name]['pass'], failed, flush=True)
    ok = all(v['pass'] for v in res.values())
    (HERE / 'validation/positive_controls_results.json').write_text(json.dumps({'all_positive_controls_pass': ok, 'controls': res}, indent=1, default=str))
    print('ALL_POSITIVE_CONTROLS_OK', ok)

