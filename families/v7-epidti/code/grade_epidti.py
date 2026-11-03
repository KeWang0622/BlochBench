#!/usr/bin/env python3
"""Core grader for heldout-v7-epidti."""
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_erosion
import _v7common as C

HERE = Path(__file__).resolve().parent
ENTRY = 'epi_dti.py'
OUT = 'dti.npz'
REQUIRED = [ENTRY, OUT, 'report.json', 'README.md']
REPORT_KEYS = ['scope', 'ghost_correction', 'distortion_correction', 'gradient_nonlinearity', 'tensor_fit', 'software', 'validation_summary', 'limitations']
GEOM_TOL, GHOST_TOL, FAVOX_TOL = 0.13, 0.05, 0.05
FA_TOL, MD_TOL, ANG_TOL = 0.04, 0.06, 8.0
NAMES = {1: 'gm', 2: 'csf', 3: 'fibre_a', 4: 'fibre_b', 5: 'fibre_c', 6: 'fibre_d'}


def erode2d(m):
    return np.array([binary_erosion(q) for q in m])


def add_checks(checks, prefix, out_path, truth_path):
    t = np.load(truth_path)
    lab, s0 = t['labels'], t['s0']
    d = C.load_npz(out_path) if out_path else None
    sh = lab.shape
    b0, mb = C.get_arr(d, 'mean_b0', sh)
    fa, mf = C.get_arr(d, 'fa', sh)
    md, mm = C.get_arr(d, 'md_mm2_per_s', sh)
    v1, mv = C.get_arr(d, 'v1', sh + (3,))
    if b0 is None:
        C.chk(checks, prefix + '_geometry', False, mb)
        C.chk(checks, prefix + '_nyquist_ghost', False, mb)
    else:
        b0 = np.where(np.isfinite(b0), np.abs(b0), 0)
        sc = (b0 * s0).sum() / max((b0 * b0).sum(), 1e-30)
        nr = float(np.linalg.norm(sc * b0 - s0) / np.linalg.norm(s0))
        C.chk(checks, prefix + '_geometry', nr <= GEOM_TOL, {'nrmse_mean_b0_vs_undistorted_truth': round(nr, 4), 'tol': GEOM_TOL})
        bg = np.array([binary_erosion(q == 0, iterations=2) for q in s0])
        gh = float(b0[bg].mean() / max(b0[s0 > 0].mean(), 1e-30))
        C.chk(checks, prefix + '_nyquist_ghost', gh <= GHOST_TOL, {'background_to_object_mean_ratio': round(gh, 4), 'tol': GHOST_TOL})
    if fa is None or md is None:
        C.chk(checks, prefix + '_fa_md_rois', False, mf if fa is None else mm)
        C.chk(checks, prefix + '_fa_voxelwise', False, mf if fa is None else mm)
    else:
        fa = np.where(np.isfinite(fa), fa, 0); md = np.where(np.isfinite(md), md, 0)
        res, ok = {}, True
        for l, n in NAMES.items():
            m = erode2d(lab == l)
            ef = float(np.median(fa[m]) - np.median(t['fa'][m]))
            em = float(np.median(md[m]) / np.median(t['md'][m]) - 1)
            res[n] = {'fa_err': round(ef, 4), 'md_rel_err': round(em, 4)}
            ok &= abs(em) <= MD_TOL and (l == 2 or abs(ef) <= FA_TOL)
        C.chk(checks, prefix + '_fa_md_rois', ok, {'rois': res, 'fa_tol': FA_TOL, 'md_rel_tol': MD_TOL, 'note': 'FA not scored in CSF'})
        br = erode2d(lab > 0)
        fv = float((np.abs(fa - t['fa'])[br] > 0.15).mean())
        C.chk(checks, prefix + '_fa_voxelwise', fv <= FAVOX_TOL, {'fraction_brain_voxels_abs_fa_err_gt_0.15': round(fv, 4), 'tol': FAVOX_TOL})
    if v1 is None:
        C.chk(checks, prefix + '_v1_direction', False, mv)
    else:
        res, ok = {}, True
        for l in (3, 4, 5, 6):
            m = erode2d(lab == l)
            a = v1[m]; b = t['v1'][m]
            nrm = np.linalg.norm(a, axis=1) + 1e-12
            dots = np.abs((a * b).sum(1)) / nrm
            ang = float(np.degrees(np.arccos(np.clip(np.median(dots), 0, 1))))
            res[NAMES[l]] = round(ang, 2)
            ok &= ang <= ANG_TOL
        C.chk(checks, prefix + '_v1_direction', ok, {'median_angle_deg': res, 'tol_deg': ANG_TOL})


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
                for s in ('_geometry', '_nyquist_ghost', '_fa_md_rois', '_fa_voxelwise', '_v1_direction'):
                    C.chk(checks, f'hidden_{case}' + s, False, {'run': rec})
                continue
        add_checks(checks, f'hidden_{case}', out, cd / 'truth.npz')
    return C.finish(checks, {'rerun_python': str(py) if py else None})

