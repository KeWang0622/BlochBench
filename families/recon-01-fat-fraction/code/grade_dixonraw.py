#!/usr/bin/env python3
"""Core grader for heldout-v7-dixonraw."""
from pathlib import Path
import numpy as np
import _v7common as C

HERE = Path(__file__).resolve().parent
ENTRY = 'dixon_pdff.py'
OUT = 'pdff.npz'
REQUIRED = [ENTRY, OUT, 'report.json', 'README.md']
REPORT_KEYS = ['scope', 'reconstruction', 'coil_combination', 'signal_model', 't1_correction', 'software', 'validation_summary', 'limitations']
PDFF_TOL = 1.5


def add_checks(checks, prefix, out_path, truth_path):
    t = np.load(truth_path)
    lab, ff, r2 = t['labels'], t['pdff_percent'], t['r2s_per_s']
    d = C.load_npz(out_path) if out_path else None
    p, m1 = C.get_arr(d, 'pdff_percent', lab.shape)
    r, m2 = C.get_arr(d, 'r2s_per_s', lab.shape)
    if p is None:
        C.chk(checks, prefix + '_pdff_vials', False, m1)
    else:
        e = {}
        for k in range(1, lab.max() + 1):
            v = p[lab == k]; v = v[np.isfinite(v)]
            e[str(k)] = round(float(np.median(v) - ff[lab == k][0]), 3) if v.size else 999.0
        mx = max(abs(x) for x in e.values())
        C.chk(checks, prefix + '_pdff_vials', mx <= PDFF_TOL, {'max_abs_err_pp': round(mx, 3), 'tol_pp': PDFF_TOL, 'err_by_vial_pp': e})
    if r is None:
        C.chk(checks, prefix + '_r2s_vials', False, m2)
    else:
        e, ok = {}, True
        for k in range(1, lab.max() + 1):
            v = r[lab == k]; v = v[np.isfinite(v)]
            tv = r2[lab == k][0]
            err = float(np.median(v) - tv) if v.size else 999.0
            e[str(k)] = round(err, 2)
            ok &= abs(err) <= max(6.0, 0.1 * tv)
        C.chk(checks, prefix + '_r2s_vials', ok, {'err_by_vial_per_s': e, 'tol': 'max(6 s^-1, 10%)'})


def grade(ws, ev):
    checks = {}
    src = C.locate(ws, ENTRY)
    C.docs_checks(checks, src, REQUIRED, REPORT_KEYS)
    add_checks(checks, 'public', src / OUT if (src / OUT).exists() else None, HERE / 'truth' / 'public_truth.npz')
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
                for s in ('_pdff_vials', '_r2s_vials'):
                    C.chk(checks, f'hidden_{case}' + s, False, {'run': rec})
                continue
        add_checks(checks, f'hidden_{case}', out, cd / 'truth.npz')
    return C.finish(checks, {'rerun_python': str(py) if py else None})

