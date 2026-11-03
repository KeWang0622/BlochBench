#!/usr/bin/env python3
"""Core grader for heldout-v7-fmriglm."""
from pathlib import Path
import numpy as np
import _v7common as C

HERE = Path(__file__).resolve().parent
ENTRY = 'fmri_glm.py'
OUT = 'stats.npz'
REQUIRED = [ENTRY, OUT, 'report.json', 'README.md']
REPORT_KEYS = ['scope', 'design', 'noise_model', 'n_volumes_analysed', 'software', 'validation_summary', 'limitations']
BIAS_TOL, MAE_TOL = 0.08, 0.20
FPR05, FPR01 = (0.02, 0.085), (0.002, 0.02)


def add_checks(checks, prefix, out_path, truth_path):
    t = np.load(truth_path)
    A, brain, st = t['amp_pct'], t['brain'], t['slice_times_s']
    d = C.load_npz(out_path) if out_path else None
    psc, m1 = C.get_arr(d, 'psc', A.shape)
    z, m2 = C.get_arr(d, 'z', A.shape)
    if psc is None:
        C.chk(checks, prefix + '_psc_bias', False, m1)
        C.chk(checks, prefix + '_psc_mae', False, m1)
    else:
        late = st >= np.median(st)
        det = {}
        ok = True
        for g, sel in (('early_slices', ~late), ('late_slices', late)):
            m = (A > 0) & sel[:, None, None]
            rel = (np.where(np.isfinite(psc[m]), psc[m], 0) - A[m]) / A[m]
            b = float(np.median(rel))
            det[g] = round(b, 4)
            ok &= abs(b) <= BIAS_TOL
        C.chk(checks, prefix + '_psc_bias', ok, {'median_signed_rel_err': det, 'tol': BIAS_TOL})
        m = A > 0
        mae = float(np.median(np.abs((np.where(np.isfinite(psc[m]), psc[m], 0) - A[m]) / A[m])))
        C.chk(checks, prefix + '_psc_mae', mae <= MAE_TOL, {'median_abs_rel_err': round(mae, 4), 'tol': MAE_TOL})
    if z is None:
        C.chk(checks, prefix + '_null_calibration', False, m2)
    else:
        zz = z[brain & (A == 0)]
        zz = np.where(np.isfinite(zz), zz, 0.0)
        f05, f01 = float((zz > 1.645).mean()), float((zz > 2.326).mean())
        ok = FPR05[0] <= f05 <= FPR05[1] and FPR01[0] <= f01 <= FPR01[1]
        C.chk(checks, prefix + '_null_calibration', ok, {'fraction_z_gt_1.645': round(f05, 4), 'fraction_z_gt_2.326': round(f01, 4),
                                                         'allowed': {'1.645': FPR05, '2.326': FPR01}, 'n_null_voxels': int(zz.size)})


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
                for s in ('_psc_bias', '_psc_mae', '_null_calibration'):
                    C.chk(checks, f'hidden_{case}' + s, False, {'run': rec})
                continue
        add_checks(checks, f'hidden_{case}', out, cd / 'truth.npz')
    return C.finish(checks, {'rerun_python': str(py) if py else None})

