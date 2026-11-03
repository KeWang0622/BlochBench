#!/usr/bin/env python3
"""Grader for heldout-v4-qsm (multi-echo GRE -> local field -> susceptibility map and deep grey-matter values).
Usage: python grade_qsm.py <workspace> <eval_dir> [python]"""
# ---- shared locate / rerun helpers (copied verbatim into each held-out v4 grader) ----
import json, hashlib, shutil, subprocess, sys, os
from pathlib import Path
SKIP_DIRS = {'.venv', 'venv', '.git', '__pycache__', 'node_modules', '.cache'}

def _cands(ws, rel):
    hits = []
    p = ws/rel
    if p.exists():
        hits.append(p)
    for sub in sorted(q for q in ws.iterdir() if q.is_dir() and q.name not in SKIP_DIRS and not (q/'bin/python').exists()):
        p = sub/rel
        if p.exists():
            hits.append(p)
    return hits

def find_file(ws, names):
    """First match for any of the names at the workspace root, else in one subfolder."""
    for n in names:
        h = _cands(ws, n)
        if h:
            return h[0]
    return None

def find_glob(ws, patterns):
    dirs = [ws] + sorted(q for q in ws.iterdir() if q.is_dir() and q.name not in SKIP_DIRS and not (q/'bin/python').exists())
    for d in dirs:
        for pat in patterns:
            m = sorted(p for p in d.glob(pat) if p.is_file())
            if m:
                return m[0]
    return None

ENV_PATTERNS = ['environment*', 'env*.txt', 'env*.json', 'env*.md', 'requirements*.txt', '*freeze*', 'versions*',
                'software_versions*', 'pip_list*', 'pip-list*', 'ENVIRONMENT*']

def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def candidate_pythons(ws):
    c = [ws/'.venv/bin/python']
    for pat in ['*/bin/python', '*/*/bin/python']:
        for p in sorted(ws.glob(pat)):
            if p.parts[len(ws.parts)] != '.venv':
                c.append(p)
    return [p for p in c if p.exists()]

def run_entry(py, entry, inputs, args, workdir, timeout=1200):
    """Copy the entrypoint and its inputs into a clean directory and run it there."""
    workdir = Path(workdir)
    if workdir.exists():
        shutil.move(str(workdir), str(workdir) + '.old%d' % len(list(workdir.parent.glob(workdir.name + '.old*'))))
    workdir.mkdir(parents=True)
    shutil.copy2(entry, workdir/Path(entry).name)
    for name, src in inputs.items():
        dst = workdir/name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if Path(src).is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    env = dict(os.environ)
    env.setdefault('TMPDIR', '/private/tmp')
    try:
        r = subprocess.run([str(py), Path(entry).name] + list(args), cwd=workdir, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return r.returncode, r.stderr[-1500:], workdir
    except subprocess.TimeoutExpired:
        return -9, 'timeout', workdir

def chk(checks, name, ok, detail):
    checks[name] = {'pass': bool(ok), 'detail': detail}

def choose_python(ws, ev, entry, inputs, args):
    trials = []
    if entry is None:
        return None, trials
    for py in candidate_pythons(ws):
        rc, err, wd = run_entry(py, entry, inputs, args, Path(ev)/('probe-%d' % len(trials)), timeout=1200)
        trials.append({'python': str(py), 'returncode': rc, 'stderr': err[-800:]})
        if rc == 0:
            return py, trials
    return None, trials
# ---- end shared helpers ----

import numpy as np, nibabel as nib
from scipy import ndimage
HERE = Path(__file__).resolve().parent
TASK = HERE.parent
SCHEMA = 'heldout-v4-qsm-r4-grade-1'
PUB = {'inputs': TASK/'public/inputs'}
HID = {'inputs': HERE/'hidden/inputs'}
ARGS = ['--input-dir', 'inputs', '--out-dir', 'results']
OUT_FILES = ['chi_ppm.nii.gz', 'local_field_hz.nii.gz', 'roi_results.json']
DOC_KEYS = ['method', 'software', 'validation_summary', 'limitations']
INNER_MM = 12.0; NEAR_MM = 7.5; SMOOTH_SIGMA_VOX = 1.0
LOCAL_R_MIN = 0.85; LOCAL_SLOPE = (0.75, 1.25)
ROI_SLOPE = (0.65, 1.35); ROI_R_MIN = 0.95
CHI_R_MIN = 0.80
ROI_LABELS = [1, 2, 3, 4, 5, 6, 8]; CSF = 7
TAGS = ['_schema', '_local_field', '_roi_susceptibility', '_chi_map']

def locate(ws):
    ws = Path(ws)
    loc = {'entry': find_file(ws, ['qsm.py'])}
    for f in OUT_FILES:
        loc[f] = find_file(ws, [f])
    loc.update({'figure': find_glob(ws, ['*.png']), 'report': find_file(ws, ['report.json']),
                'readme': find_file(ws, ['README.md', 'README.txt', 'README']), 'env': find_glob(ws, ENV_PATTERNS)})
    return loc

def rs(x, y, m):
    a = x[m] - x[m].mean(); b = y[m] - y[m].mean()
    den = np.sqrt((a*a).sum()*(b*b).sum())
    return (float((a*b).sum()/den) if den > 0 else 0.0), float((a*b).sum()/max((b*b).sum(), 1e-30))

def evaluate(files, truth_path, acq_path, tag, checks, meas):
    T = np.load(truth_path); vox = json.loads(Path(acq_path).read_text())['voxel_size_mm']
    brain = T['brain']; roi = T['roi']; chi_t = T['chi_ppm'].astype(float); lt = T['local_hz'].astype(float)
    inner = ndimage.distance_transform_edt(brain, sampling=vox) > INNER_MM
    near = ndimage.distance_transform_edt(~np.isin(roi, ROI_LABELS[:-1] + [CSF]), sampling=vox) <= NEAR_MM
    deep = inner & near
    names = [tag + s for s in TAGS]
    try:
        c = np.squeeze(np.asarray(nib.load(files['chi_ppm.nii.gz']).get_fdata(), float))
        f = np.squeeze(np.asarray(nib.load(files['local_field_hz.nii.gz']).get_fdata(), float))
        rr = json.loads(Path(files['roi_results.json']).read_text())
        ok = c.shape == brain.shape and f.shape == brain.shape and bool(np.all(np.isfinite(c[deep]))) and bool(np.all(np.isfinite(f[deep])))
        ok = ok and isinstance(rr, dict) and 'rois' in rr
        chk(checks, names[0], ok, {'chi_shape': list(c.shape), 'field_shape': list(f.shape), 'expected': list(brain.shape)})
    except Exception as e:
        for n in names:
            chk(checks, n, False, 'cannot read outputs: %r' % (e,))
        return
    if not ok:
        for n in names[1:]:
            chk(checks, n, False, 'schema failure')
        return
    sm = lambda x: ndimage.gaussian_filter(x, SMOOTH_SIGMA_VOX)
    r, s = rs(sm(f), sm(lt), deep)
    meas[tag + '_local_field_r'] = r; meas[tag + '_local_field_slope'] = s
    chk(checks, names[1], r >= LOCAL_R_MIN and LOCAL_SLOPE[0] <= s <= LOCAL_SLOPE[1],
        {'pearson_r_smoothed': r, 'min_r': LOCAL_R_MIN, 'slope_vs_true': s, 'slope_range': LOCAL_SLOPE, 'n_voxels': int(deep.sum())})
    cs = c[roi == CSF].mean(); ct = chi_t[roi == CSF].mean()
    sv = np.array([c[roi == k].mean() - cs for k in ROI_LABELS]); tv = np.array([chi_t[roi == k].mean() - ct for k in ROI_LABELS])
    slope = float((sv*tv).sum()/(tv*tv).sum()); rr_ = float(np.corrcoef(sv, tv)[0, 1]) if np.std(sv) > 0 else 0.0
    meas[tag + '_roi_values'] = sv.round(4).tolist(); meas[tag + '_roi_values_true'] = tv.round(4).tolist()
    meas[tag + '_roi_slope'] = slope; meas[tag + '_roi_r'] = rr_
    chk(checks, names[2], ROI_SLOPE[0] <= slope <= ROI_SLOPE[1] and rr_ >= ROI_R_MIN,
        {'roi_minus_csf_submitted': sv.round(4).tolist(), 'roi_minus_csf_true': tv.round(4).tolist(), 'labels': ROI_LABELS,
         'slope_through_origin': slope, 'slope_range': ROI_SLOPE, 'pearson_r': rr_, 'min_r': ROI_R_MIN})
    r2, s2 = rs(sm(c), sm(chi_t), deep)
    meas[tag + '_chi_map_r'] = r2
    chk(checks, names[3], r2 >= CHI_R_MIN, {'pearson_r_smoothed': r2, 'min_r': CHI_R_MIN})

def safe_evaluate(files, truth_path, acq_path, tag, checks, meas):
    try:
        evaluate(files, truth_path, acq_path, tag, checks, meas)
    except Exception as e:
        for n in TAGS:
            if tag + n not in checks or checks[tag + n]['pass']:
                chk(checks, tag + n, False, 'evaluation error: %r' % (e,))

def grade(ws, ev, python):
    ws = Path(ws); ev = Path(ev); ev.mkdir(parents=True, exist_ok=True)
    checks = {}; meas = {}
    loc = locate(ws)
    chk(checks, 'deliverables_present', all(loc[k] is not None for k in loc), {k: (str(v) if v else None) for k, v in loc.items()})
    if all(loc[f] is not None for f in OUT_FILES):
        safe_evaluate({f: loc[f] for f in OUT_FILES}, HERE/'truth_public.npz', TASK/'public/inputs/acquisition.json', 'public', checks, meas)
    else:
        for n in TAGS:
            chk(checks, 'public' + n, False, 'output files not found')
    if python is not None and loc['entry'] is not None:
        rc, err, wd = run_entry(python, loc['entry'], HID, ARGS, ev/'hidden_rerun')
        files = {f: wd/'results'/f for f in OUT_FILES}
        ok = rc == 0 and all(p.exists() for p in files.values())
        chk(checks, 'hidden_rerun_runs', ok, {'returncode': rc, 'stderr': err[-600:]})
        if ok:
            safe_evaluate(files, HERE/'hidden/truth_hidden.npz', HERE/'hidden/inputs/acquisition.json', 'hidden', checks, meas)
    else:
        chk(checks, 'hidden_rerun_runs', False, 'no working interpreter or no qsm.py')
    for n in TAGS:
        if 'hidden' + n not in checks:
            chk(checks, 'hidden' + n, False, 'hidden rerun unavailable')
    try:
        rep = json.loads(Path(loc['report']).read_text()) if loc['report'] else {}
    except Exception as e:
        rep = {'_error': repr(e)}
    miss = [k for k in DOC_KEYS if k not in rep]
    lim = rep.get('limitations')
    chk(checks, 'report_schema', not miss and isinstance(lim, list) and len(lim) > 0, {'missing': miss})
    return {'schema': SCHEMA, 'all_automated_checks_pass': all(v['pass'] for v in checks.values()), 'checks': checks, 'measurements': meas}

if __name__ == '__main__':
    ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve()
    py = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    g = grade(ws, ev, py)
    (ev/'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

