#!/usr/bin/env python3
"""Core grader for heldout-v7-pcasl."""
from pathlib import Path
import numpy as np
import _v7common as C

HERE = Path(__file__).resolve().parent
ENTRY = 'asl_cbf.py'
REQUIRED = ['asl_cbf.py', 'cbf.npz', 'report.json', 'README.md']
REPORT_KEYS = ['scope', 'model', 'effective_labeling_efficiency', 'pld_by_slice_s', 'gm_cbf_by_slice', 'software', 'validation_summary', 'limitations']
GM_TOL, WM_TOL = 0.06, 0.10


def score(out_path, truth_path):
    t = np.load(truth_path)
    cbf_t, lab = t['cbf'], t['labels']
    d = C.load_npz(out_path) if out_path else None
    cbf, msg = C.get_arr(d, 'cbf', cbf_t.shape)
    if cbf is None:
        return None, None, msg
    res = {}
    for name, l in (('gm', 1), ('wm', 2)):
        errs = []
        for z in range(cbf_t.shape[0]):
            m = lab[z] == l
            if m.sum() < 20:
                continue
            mt = cbf_t[z][m].mean()
            mm = np.nanmean(np.where(np.isfinite(cbf[z][m]), cbf[z][m], np.nan))
            errs.append(float((mm - mt) / mt) if np.isfinite(mm) else 9.9)
        res[name] = errs
    return res['gm'], res['wm'], 'ok'


def add_checks(checks, prefix, out_path, truth_path):
    gm, wm, msg = score(out_path, truth_path)
    if gm is None:
        C.chk(checks, prefix + '_gm_cbf', False, msg)
        C.chk(checks, prefix + '_wm_cbf', False, msg)
        return
    C.chk(checks, prefix + '_gm_cbf', max(abs(e) for e in gm) <= GM_TOL,
          {'max_abs_rel_err_over_slices': round(max(abs(e) for e in gm), 4), 'tol': GM_TOL, 'rel_err_by_slice': [round(e, 4) for e in gm]})
    C.chk(checks, prefix + '_wm_cbf', max(abs(e) for e in wm) <= WM_TOL,
          {'max_abs_rel_err_over_slices': round(max(abs(e) for e in wm), 4), 'tol': WM_TOL, 'rel_err_by_slice': [round(e, 4) for e in wm]})


def grade(ws, ev):
    checks = {}
    src = C.locate(ws, ENTRY)
    C.docs_checks(checks, src, REQUIRED, REPORT_KEYS)
    add_checks(checks, 'public', src / 'cbf.npz' if (src / 'cbf.npz').exists() else None, HERE / 'truth' / 'public_truth.npz')
    entry = src / ENTRY
    py, probe, trials = C.pick_python(ws, entry if entry.exists() else None, HERE.parent / 'public' / 'inputs', ev, 'cbf.npz')
    C.chk(checks, 'entrypoint_runs_on_public_inputs', py is not None, {'trials': [{k: v for k, v in t.items() if k != 'workdir'} for t in trials]} if trials else 'asl_cbf.py not found')
    for case in ('case1', 'case2'):
        cd = HERE / 'hidden' / case
        out = None
        if py is not None:
            rec = C.run_entry(py, entry, cd / 'inputs', ev / f'hidden-{case}', 'cbf.npz')
            out = rec['output']
            if out is None:
                C.chk(checks, f'hidden_{case}_gm_cbf', False, {'run': rec})
                C.chk(checks, f'hidden_{case}_wm_cbf', False, {'run': rec})
                continue
        add_checks(checks, f'hidden_{case}', out, cd / 'truth.npz')
    return C.finish(checks, {'rerun_python': str(py) if py else None})

