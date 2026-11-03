#!/usr/bin/env python3
"""Core grader for heldout-v7-mrsquant."""
import json
from pathlib import Path
import numpy as np
import _v7common as C

HERE = Path(__file__).resolve().parent
ENTRY = 'mrs_quant.py'
OUT = 'conc.json'
REQUIRED = [ENTRY, OUT, 'report.json', 'README.md']
REPORT_KEYS = ['scope', 'preprocessing', 'fitting', 'quantification_model', 'software', 'validation_summary', 'limitations']
TOL = 0.05


def add_checks(checks, prefix, out_path, truth_path):
    t = json.loads(Path(truth_path).read_text())
    d = C.load_json(out_path) if out_path else None
    if not isinstance(d, dict):
        C.chk(checks, prefix + '_concentrations', False, 'output JSON missing or invalid')
        return
    errs = {}
    for k, v in t.items():
        try:
            x = float(d[k])
            errs[k] = round(x / v - 1, 4) if np.isfinite(x) else 9.9
        except Exception:
            errs[k] = 9.9
    mx = max(abs(e) for e in errs.values())
    C.chk(checks, prefix + '_concentrations', mx <= TOL, {'rel_err': errs, 'max_abs_rel_err': round(mx, 4), 'tol': TOL})


def grade(ws, ev):
    checks = {}
    src = C.locate(ws, ENTRY)
    C.docs_checks(checks, src, REQUIRED, REPORT_KEYS)
    add_checks(checks, 'public', src / OUT if (src / OUT).exists() else None, HERE / 'truth' / 'public_truth.json')
    entry = src / ENTRY
    py, probe, trials = C.pick_python(ws, entry if entry.exists() else None, HERE.parent / 'public' / 'inputs', ev, OUT)
    C.chk(checks, 'entrypoint_runs_on_public_inputs', py is not None, {'trials': [{k: v for k, v in t.items() if k != 'workdir'} for t in trials]} if trials else ENTRY + ' not found')
    for case in ('case1', 'case2'):
        cd = HERE / 'hidden' / case
        out = None
        if py is not None:
            rec = C.run_entry(py, entry, cd / 'inputs', ev / f'hidden-{case}', OUT)
            out = rec['output']
            if out is None:
                C.chk(checks, f'hidden_{case}_concentrations', False, {'run': rec})
                continue
        add_checks(checks, f'hidden_{case}', out, cd / 'truth.json')
    return C.finish(checks, {'rerun_python': str(py) if py else None})

