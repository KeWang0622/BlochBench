#!/usr/bin/env python3
"""Core grader for heldout-v7-cestapt."""
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_erosion
import _v7common as C

HERE = Path(__file__).resolve().parent
ENTRY = 'cest_apt.py'
OUT = 'apt.npz'
REQUIRED = [ENTRY, OUT, 'report.json', 'README.md']
REPORT_KEYS = ['scope', 'b0_method', 'normalisation', 'roi_mtrasym_percent', 'software', 'validation_summary', 'limitations']
ROI_TOL, VOX_TOL, B0_TOL = 0.30, 0.45, 0.03
NAMES = {2: 'gm', 3: 'wm', 4: 'lesion_a', 5: 'lesion_b'}


def add_checks(checks, prefix, out_path, truth_path):
    t = np.load(truth_path)
    lab, mt, b0t = t['labels'], t['mtrasym_percent'], t['b0_ppm']
    d = C.load_npz(out_path) if out_path else None
    m, msg1 = C.get_arr(d, 'mtr_asym_3p5_percent', lab.shape)
    b, msg2 = C.get_arr(d, 'b0_ppm', lab.shape)
    if m is None:
        C.chk(checks, prefix + '_mtrasym_rois', False, msg1)
        C.chk(checks, prefix + '_mtrasym_voxelwise', False, msg1)
    else:
        roi = {}
        ok = True
        for l, n in NAMES.items():
            r = binary_erosion(lab == l)
            if r.sum() < 5:
                r = lab == l
            v = m[r]
            v = v[np.isfinite(v)]
            e = float(np.median(v) - mt[r][0]) if v.size else 99.0
            roi[n] = {'median': round(float(np.median(v)) if v.size else -99, 3), 'truth': round(float(mt[r][0]), 3), 'err': round(e, 3)}
            ok &= abs(e) <= ROI_TOL
        C.chk(checks, prefix + '_mtrasym_rois', ok, {'tol_abs_percent': ROI_TOL, 'rois': roi})
        brain = binary_erosion(lab > 0)
        err = np.abs(np.where(np.isfinite(m), m, 99) - mt)[brain]
        med = float(np.median(err))
        C.chk(checks, prefix + '_mtrasym_voxelwise', med <= VOX_TOL, {'median_abs_err_percent': round(med, 3), 'tol': VOX_TOL})
    if b is None:
        C.chk(checks, prefix + '_b0_map', False, msg2)
    else:
        brain = binary_erosion(lab > 0)
        med = float(np.median(np.abs(np.where(np.isfinite(b), b, 99) - b0t)[brain]))
        C.chk(checks, prefix + '_b0_map', med <= B0_TOL, {'median_abs_err_ppm': round(med, 4), 'tol_ppm': B0_TOL})


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
                for s in ('_mtrasym_rois', '_mtrasym_voxelwise', '_b0_map'):
                    C.chk(checks, f'hidden_{case}' + s, False, {'run': rec})
                continue
        add_checks(checks, f'hidden_{case}', out, cd / 'truth.npz')
    return C.finish(checks, {'rerun_python': str(py) if py else None})

