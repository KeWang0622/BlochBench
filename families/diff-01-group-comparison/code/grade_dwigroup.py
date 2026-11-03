#!/usr/bin/env python3
"""Grader for heldout-v5-dwigroup. grade(ws, ev, python) -> dict."""
import json, shutil, subprocess, sys
from pathlib import Path
import numpy as np, nibabel as nib
from scipy import stats

HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'
HID = HERE / 'hidden'
TOL = {'fa_abs': 0.03, 'md_rel': 0.03, 'v1_deg': 5.0, 'grp_fa': 0.010, 'grp_md': 0.012,
       'map_fa_med': 0.04, 'map_md_med': 0.04, 'map_v1_med_deg': 8.0}
SKIP = {'.venv', 'venv', '.git', '__pycache__', 'site-packages', 'node_modules', '_trash'}

def find_once(ws, name):
    c = []
    if (ws / name).exists():
        c.append(ws / name)
    for d in sorted(ws.iterdir()):
        if d.is_dir() and d.name not in SKIP and not d.name.startswith('.') and (d / name).exists():
            c.append(d / name)
    return c[0] if c else None

def find_glob(ws, pats):
    for base in [ws] + [d for d in sorted(ws.iterdir()) if d.is_dir() and d.name not in SKIP and not d.name.startswith('.')]:
        for p in pats:
            hits = sorted(base.glob(p))
            if hits:
                return hits[0]
    return None

def locate(ws):
    ws = Path(ws)
    p = find_once(ws, 'process_subject.py')
    return (p.parent if p else ws), p

def ang(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    return float(np.degrees(np.arccos(min(1.0, abs(float(a @ b))))))

def cmp_labels(res, truth):
    """Return (fa_err_max, md_rel_max, v1_max, details) over labels."""
    fe, me, ae, det = [], [], [], {}
    for k in ['1', '2', '3', '4']:
        t = truth[k]; r = res[k]
        if k != '4':
            fe.append(abs(float(r['fa']) - t['fa']))
        me.append(abs(float(r['md_um2_per_ms']) / t['md_um2_per_ms'] - 1))
        if k in ('1', '2'):
            ae.append(ang(r['v1_ras'], t['v1_ras']))
    return max(fe), max(me), max(ae)

def welch(c, p):
    c, p = np.asarray(c, float), np.asarray(p, float)
    d = p.mean() - c.mean(); vc, vp = c.var(ddof=1) / len(c), p.var(ddof=1) / len(p)
    se = np.sqrt(vc + vp); df = (vc + vp) ** 2 / (vc ** 2 / (len(c) - 1) + vp ** 2 / (len(p) - 1))
    q = stats.t.ppf(0.975, df)
    return d, (d - q * se, d + q * se), 2 * stats.t.sf(abs(d / se), df)

def chk(checks, name, ok, detail):
    checks[name] = {'pass': bool(ok), 'detail': detail}

def grade(ws, ev, python):
    ws = Path(ws).resolve(); ev = Path(ev).resolve(); ev.mkdir(parents=True, exist_ok=True)
    checks, meas = {}, {}
    src, entry = locate(ws)
    tp = json.loads((HERE / 'truth_public.json').read_text())
    th = json.loads((HID / 'truth_hidden.json').read_text())
    files = {'process_subject.py': entry, 'subject_results.json': find_once(ws, 'subject_results.json'),
             'group_results.json': find_once(ws, 'group_results.json'), 'README.md': find_once(ws, 'README.md'),
             'qc figure': find_glob(ws, ['qc*.png', 'figures/qc*.png', '*qc*.png']),
             'environment record': find_glob(ws, ['environment*.txt', 'environment*.json', 'environment*.yml', 'requirements*.txt', 'env*.txt', 'pip-freeze*.txt', 'environment*.md'])}
    missing = [k for k, v in files.items() if v is None]
    chk(checks, 'deliverables_present', not missing, {'missing': missing})
    # ---- public subject results
    sr = None
    try:
        sr = json.loads(files['subject_results.json'].read_text())
        ok = all(s in sr and all(k in sr[s]['labels'] for k in '1234') and all('v1_ras' in sr[s]['labels'][k] for k in '12') for s in tp['subjects'])
        chk(checks, 'subject_results_schema', ok, {'n_subjects': len(sr)})
    except Exception as e:
        chk(checks, 'subject_results_schema', False, {'error': repr(e)[:300]})
    fe = me = ae = None
    if checks['subject_results_schema']['pass']:
        F, M, A = [], [], []
        for s, t in tp['subjects'].items():
            f, m, a = cmp_labels(sr[s]['labels'], t['labels']); F.append(f); M.append(m); A.append(a)
        fe, me, ae = max(F), max(M), max(A)
        meas.update({'public_fa_abs_err_max': fe, 'public_md_rel_err_max': me, 'public_v1_err_deg_max': ae})
    chk(checks, 'public_fa_accuracy', fe is not None and fe <= TOL['fa_abs'], {'max_abs_err': fe, 'tol': TOL['fa_abs'], 'labels': '1-3'})
    chk(checks, 'public_md_accuracy', me is not None and me <= TOL['md_rel'], {'max_rel_err': me, 'tol': TOL['md_rel'], 'labels': '1-4'})
    chk(checks, 'public_v1_accuracy', ae is not None and ae <= TOL['v1_deg'], {'max_angle_deg': ae, 'tol': TOL['v1_deg'], 'labels': '1-2'})
    # ---- group statistics
    gd = {}
    try:
        gr = json.loads(files['group_results.json'].read_text())
        for key, name, tkey, tol in [('fa', 'fa_label1', 'fa_label1_patient_minus_control', TOL['grp_fa']),
                                     ('md_um2_per_ms', 'md_label1', 'md_label1_patient_minus_control', TOL['grp_md'])]:
            g = gr[name]; d = float(g['difference_patient_minus_control'])
            err = abs(d - tp['group'][tkey])
            cons = None
            if sr is not None:
                c = [sr[s]['labels']['1'][key] for s in tp['subjects'] if tp['subjects'][s]['group'] == 'control']
                p = [sr[s]['labels']['1'][key] for s in tp['subjects'] if tp['subjects'][s]['group'] == 'patient']
                dd, ci, pv = welch(c, p)
                scale = 1.0 if key == 'fa' else 1.0
                cons = (abs(dd - d) <= 1e-3 * scale and abs(ci[0] - float(g['ci95'][0])) <= 2e-3 and abs(ci[1] - float(g['ci95'][1])) <= 2e-3
                        and abs(pv - float(g['p_value'])) <= max(0.005, 0.1 * pv))
                gd[name] = {'reported': d, 'truth': tp['group'][tkey], 'abs_err': err, 'tol': tol, 'welch_recomputed': [dd, list(ci), pv],
                            'reported_ci': g['ci95'], 'reported_p': g['p_value'], 'consistent': cons}
            meas['group_' + name + '_err'] = err
        okd = all(v['abs_err'] <= v['tol'] for v in gd.values()) and len(gd) == 2
        chk(checks, 'group_difference_accuracy', okd, gd)
        chk(checks, 'group_welch_consistency', len(gd) == 2 and all(v['consistent'] for v in gd.values()), {k: v['consistent'] for k, v in gd.items()})
    except Exception as e:
        chk(checks, 'group_difference_accuracy', False, {'error': repr(e)[:300]})
        chk(checks, 'group_welch_consistency', False, {'error': repr(e)[:300]})
    # ---- hidden reruns
    runs, H = {}, {}
    if entry is not None and python is not None:
        for sid in sorted(th):
            od = ev / 'hidden_out' / sid
            if od.exists():
                shutil.move(str(od), str(ev / ('_old_' + sid + '_%d' % len(list(ev.glob('_old_*'))))))
            hd = HID / sid
            cmd = [str(python), str(entry), '--dwi', str(hd / 'dwi.nii.gz'), '--sidecar', str(hd / 'dwi.json'),
                   '--labels', str(hd / 'labels.nii.gz'), '--outdir', str(od)]
            try:
                r = subprocess.run(cmd, cwd=str(entry.parent), capture_output=True, text=True, timeout=900)
                runs[sid] = {'returncode': r.returncode, 'stderr': r.stderr[-600:]}
            except Exception as e:
                runs[sid] = {'returncode': -1, 'stderr': repr(e)[:300]}
    okrun = len(runs) == len(th) and all(v['returncode'] == 0 and (ev / 'hidden_out' / s / 'results.json').exists() for s, v in runs.items())
    chk(checks, 'hidden_rerun_runs', okrun, runs)
    hf = hm = ha = None; mapdet = {}; mapok = okrun
    if okrun:
        F, M, A = [], [], []
        for sid in sorted(th):
            od = ev / 'hidden_out' / sid
            try:
                res = json.loads((od / 'results.json').read_text())['labels']
                f, m, a = cmp_labels(res, th[sid]['labels']); F.append(f); M.append(m); A.append(a)
            except Exception as e:
                F.append(9); M.append(9); A.append(90); mapdet[sid + '_results_error'] = repr(e)[:200]
            try:
                lab_img = nib.load(str(HID / sid / 'labels.nii.gz')); lab = np.asarray(lab_img.dataobj).astype(int)
                tm = np.load(HID / sid / 'truth_maps.npz')
                fi = nib.load(str(od / 'fa.nii.gz')); mi = nib.load(str(od / 'md.nii.gz')); vi = nib.load(str(od / 'v1_ras.nii.gz'))
                geo = all(im.shape[:3] == lab.shape and np.allclose(im.affine, lab_img.affine, atol=1e-3) for im in (fi, mi, vi))
                fa = np.asarray(fi.dataobj, float); md = np.asarray(mi.dataobj, float); v1 = np.asarray(vi.dataobj, float).reshape(lab.shape + (3,))
                wm = np.isin(lab, [1, 2, 3, 5])
                fmed = float(np.median(np.abs(fa[wm] - tm['fa'][wm])))
                mmed = float(np.median(np.abs(md[wm] / tm['md'][wm] - 1)))
                tv = tm['v1']; m12 = np.isin(lab, [1, 2])
                cosv = np.abs((v1[m12] * tv[m12]).sum(-1)) / (np.linalg.norm(v1[m12], axis=-1) * np.linalg.norm(tv[m12], axis=-1) + 1e-12)
                vmed = float(np.median(np.degrees(np.arccos(np.clip(cosv, 0, 1)))))
                ok = geo and fmed <= TOL['map_fa_med'] and mmed <= TOL['map_md_med'] and vmed <= TOL['map_v1_med_deg']
                mapdet[sid] = {'geometry_ok': geo, 'fa_med_abs_err': fmed, 'md_med_rel_err': mmed, 'v1_med_deg': vmed, 'pass': ok}
                mapok = mapok and ok
            except Exception as e:
                mapdet[sid] = {'error': repr(e)[:300]}; mapok = False
        hf, hm, ha = max(F), max(M), max(A)
        meas.update({'hidden_fa_abs_err_max': hf, 'hidden_md_rel_err_max': hm, 'hidden_v1_err_deg_max': ha})
    chk(checks, 'hidden_fa_accuracy', hf is not None and hf <= TOL['fa_abs'], {'max_abs_err': hf, 'tol': TOL['fa_abs']})
    chk(checks, 'hidden_md_accuracy', hm is not None and hm <= TOL['md_rel'], {'max_rel_err': hm, 'tol': TOL['md_rel']})
    chk(checks, 'hidden_v1_accuracy', ha is not None and ha <= TOL['v1_deg'], {'max_angle_deg': ha, 'tol': TOL['v1_deg']})
    chk(checks, 'hidden_maps', okrun and mapok, mapdet)
    rd = files['README.md'].read_text(errors='ignore') if files['README.md'] else ''
    chk(checks, 'readme_validation_limitations', len(rd) >= 200 and 'limitation' in rd.lower(), {'chars': len(rd)})
    return {'schema': 'heldout-v5-dwigroup-grade-1', 'all_automated_checks_pass': all(v['pass'] for v in checks.values()),
            'checks': checks, 'measurements': meas, 'located': {k: str(v) if v else None for k, v in files.items()}}

if __name__ == '__main__':
    ws, ev = Path(sys.argv[1]), Path(sys.argv[2])
    py = sys.argv[3] if len(sys.argv) > 3 else sys.executable
    g = grade(ws, ev, py); (Path(ev) / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

