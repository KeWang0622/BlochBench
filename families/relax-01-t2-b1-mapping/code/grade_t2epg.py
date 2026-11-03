#!/usr/bin/env python3
"""Grader for heldout-v4-t2epg.  Usage: python grade_t2epg.py <workspace_dir> <eval_dir> [python_for_reruns]"""
import json, os, shutil, subprocess, sys
from pathlib import Path
import numpy as np
import nibabel as nib

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
CASES = {'public': (TASK / 'public/inputs', HERE / 'truth_public.npz'), 'hidden': (HERE / 'hidden/inputs', HERE / 'hidden/truth_hidden.npz')}
SCHEMA = 'heldout-v4-t2epg-r4-grade-1'
TOL_T2_MED_ABS = 0.03    # median |relative T2 error| over labelled voxels
TOL_T2_LABEL_BIAS = 0.03 # |median relative T2 error| within each label
TOL_T2_LOWB1 = 0.03      # |median relative T2 error| in the lowest-B1 quartile of labelled voxels
TOL_B1 = 0.03            # median |B1 error|
TOL_ROI = 0.03           # |relative error| of every label-mean T2
SKIP_DIRS = {'.venv', 'venv', '.git', '__pycache__', 'node_modules', '.cache', 'site-packages', '.ipynb_checkpoints'}
REQ = ['fit_t2.py', 't2_map.nii.gz', 'b1_map.nii.gz', 'roi_t2.json', 'report.json', 'README.md']


def _subdirs(ws):
    return [d for d in sorted(Path(ws).iterdir()) if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith('.')]


def find_file(ws, name):
    ws = Path(ws)
    if (ws / name).is_file():
        return ws / name
    hits = [d / name for d in _subdirs(ws) if (d / name).is_file()]
    return hits[0] if hits else None


def env_record(ws, report):
    if isinstance(report, dict) and report.get('software'):
        return True
    pats = ['environment*.txt', 'requirements*.txt', 'environment*.yml', 'environment*.yaml', 'environment*.json', 'pip-freeze*.txt', 'pip_freeze*.txt', 'uv.lock', 'pyproject.toml']
    return any(list(d.glob(p)) for d in [Path(ws)] + _subdirs(ws) for p in pats)


def python_candidates(ws):
    ws = Path(ws)
    c = [ws / '.venv/bin/python'] + sorted(p for pat in ['*/bin/python', '*/*/bin/python'] for p in ws.glob(pat) if p.parts[len(ws.parts)] != '.venv')
    return [p for p in c if p.exists()]


def run_entry(py, script, args, cwd, timeout=1200):
    env = {**os.environ, 'MPLBACKEND': 'Agg', 'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'VECLIB_MAXIMUM_THREADS': '2'}
    try:
        r = subprocess.run([str(py), script] + list(args), cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout[-1500:], r.stderr[-1500:]
    except Exception as e:
        return -1, '', repr(e)[-1500:]


def load_json(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def chk(checks, name, ok, detail):
    checks[name] = {'pass': bool(ok), 'detail': detail}


def load_map(p, shape):
    img = nib.load(str(p)); a = np.asarray(img.dataobj, float)
    while a.ndim > 3 and a.shape[-1] == 1:
        a = a[..., 0]
    return a, img.affine


def roi_values(roi):
    if not isinstance(roi, dict):
        return None
    d = roi.get('label_mean_T2_s', roi)
    try:
        return {str(k): float(v) for k, v in d.items()}
    except Exception:
        return None


def evaluate(case, t2p, b1p, roi):
    t = np.load(CASES[case][1]); lab = t['labels']; aff = t['affine']; m = lab > 0
    T2t = t['T2']; B1t = t['B1']; out = {}
    out['grid_ok'] = False
    try:
        T2, a = load_map(t2p, lab.shape)
        out['t2_shape'] = list(T2.shape)
        out['grid_ok'] = T2.shape == lab.shape and np.allclose(a, aff, atol=1e-2)
        if T2.shape == lab.shape:
            e = T2[m] / T2t[m] - 1; e = np.where(np.isfinite(e), e, 1e3)
            out['t2_median_abs_rel_err'] = float(np.median(np.abs(e)))
            out['t2_p90_abs_rel_err'] = float(np.percentile(np.abs(e), 90))
            out['t2_label_median_rel_err'] = {str(k): float(np.median(e[lab[m] == k])) for k in np.unique(lab[m])}
            q = B1t[m] <= np.percentile(B1t[m], 25)
            out['t2_lowb1_median_rel_err'] = float(np.median(e[q])); out['lowb1_max_B1'] = float(B1t[m][q].max())
    except Exception as ex:
        out['t2_error'] = repr(ex)
    try:
        B1, a = load_map(b1p, lab.shape)
        if B1.shape == lab.shape:
            d = B1[m] - B1t[m]; d = np.where(np.isfinite(d), d, 1e3)
            out['b1_median_abs_err'] = float(np.median(np.abs(d)))
    except Exception as ex:
        out['b1_error'] = repr(ex)
    true_roi = {str(k): float(T2t[lab == k].mean()) for k in np.unique(lab) if k > 0}
    out['true_roi_T2_s'] = true_roi
    rv = roi_values(roi)
    if rv is not None:
        out['roi_T2_s'] = rv
        try:
            out['roi_rel_err'] = {k: rv[k] / v - 1 for k, v in true_roi.items()}
        except Exception as ex:
            out['roi_error'] = repr(ex)
    return out


def case_checks(checks, p, m):
    chk(checks, p + 't2_grid', m.get('grid_ok', False), {'shape': m.get('t2_shape')})
    chk(checks, p + 't2_voxel_accuracy', m.get('t2_median_abs_rel_err', 9) <= TOL_T2_MED_ABS, {'median_abs_rel_err': m.get('t2_median_abs_rel_err'), 'tol': TOL_T2_MED_ABS})
    lb = m.get('t2_label_median_rel_err')
    chk(checks, p + 't2_label_bias', lb is not None and all(abs(v) <= TOL_T2_LABEL_BIAS for v in lb.values()), {'label_median_rel_err': lb, 'tol': TOL_T2_LABEL_BIAS})
    chk(checks, p + 't2_low_b1_bias', abs(m.get('t2_lowb1_median_rel_err', 9)) <= TOL_T2_LOWB1, {'lowb1_median_rel_err': m.get('t2_lowb1_median_rel_err'), 'lowb1_max_B1': m.get('lowb1_max_B1'), 'tol': TOL_T2_LOWB1})
    chk(checks, p + 'b1_accuracy', m.get('b1_median_abs_err', 9) <= TOL_B1, {'median_abs_err': m.get('b1_median_abs_err'), 'tol': TOL_B1})
    re = m.get('roi_rel_err')
    chk(checks, p + 'roi_t2_endpoint', re is not None and all(abs(v) <= TOL_ROI for v in re.values()), {'roi_rel_err': re, 'tol': TOL_ROI})


def grade(ws, ev, py=None):
    ws = Path(ws); ev = Path(ev); ev.mkdir(parents=True, exist_ok=True)
    checks, meas = {}, {}
    files = {n: find_file(ws, n) for n in REQ}
    chk(checks, 'deliverables_present', all(files.values()), {k: (str(v) if v else None) for k, v in files.items()})
    rep = load_json(files['report.json']) if files['report.json'] else None
    chk(checks, 'environment_record', rep is not None and env_record(ws, rep), 'report.software or environment file')
    roi = load_json(files['roi_t2.json']) if files['roi_t2.json'] else None
    m = evaluate('public', files['t2_map.nii.gz'], files['b1_map.nii.gz'], roi) if files['t2_map.nii.gz'] else {}
    meas['public'] = m
    case_checks(checks, 'public_', m)
    ok = False
    try:
        rr = {str(k): float(v) for k, v in rep['roi_mean_T2_s'].items()}
        ok = all(abs(rr[k] - v) <= 1e-3 * max(abs(v), 1e-3) + 1e-6 for k, v in roi_values(roi).items()) and isinstance(rep.get('limitations'), list) and len(rep['limitations']) > 0
    except Exception:
        pass
    chk(checks, 'report_consistent', ok, 'report.roi_mean_T2_s equals roi_t2.json; limitations listed')
    script = files['fit_t2.py']
    for tag, case in [('rerun_public_', 'public'), ('hidden_', 'hidden')]:
        d = ev / (tag + 'run'); d.mkdir(exist_ok=True)
        ok_run, det, m2 = False, {'python': str(py) if py else None}, None
        if script is not None and py is not None:
            shutil.copy2(script, d / 'fit_t2.py')
            if (d / 'in').exists():
                shutil.rmtree(d / 'in')
            shutil.copytree(CASES[case][0], d / 'in')
            rc, so, se = run_entry(py, 'fit_t2.py', ['--input-dir', 'in', '--output-dir', 'out'], d)
            det.update(returncode=rc, stderr=se[-600:])
            if rc == 0 and (d / 'out/t2_map.nii.gz').exists():
                ok_run = True
                m2 = evaluate(case, d / 'out/t2_map.nii.gz', d / 'out/b1_map.nii.gz', load_json(d / 'out/roi_t2.json'))
        chk(checks, tag + 'runs', ok_run, det)
        if case == 'public':
            ok = False
            try:
                a = roi_values(roi); b = m2['roi_T2_s']
                ok = all(abs(b[k] / a[k] - 1) <= 0.01 for k in a)
            except Exception:
                pass
            chk(checks, 'rerun_public_reproduces_submitted', ok, {'rerun_roi_T2_s': (m2 or {}).get('roi_T2_s')})
        else:
            meas['hidden'] = m2 or {}
            case_checks(checks, 'hidden_', m2 or {})
    allp = all(v['pass'] for v in checks.values())
    return {'schema': SCHEMA, 'all_automated_checks_pass': allp, 'checks': checks, 'measurements': meas}


def locate(ws):
    s = find_file(ws, 'fit_t2.py')
    return (s.parent if s else Path(ws)), s


if __name__ == '__main__':
    ws, ev = Path(sys.argv[1]), Path(sys.argv[2])
    py = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(sys.executable)
    g = grade(ws, ev, py)
    (ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

