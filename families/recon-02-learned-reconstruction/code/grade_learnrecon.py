#!/usr/bin/env python3
"""Grader for heldout-v5-learnrecon. grade(ws, ev, python) -> dict."""
import json, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_erosion
HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'
TOL = {'r2s_med': 0.035, 'r2s_p90': 0.11, 'b0_med': 0.5, 'b0_p90': 1.5, 'dc_rel': 0.35, 'rep_r2s_rel': 0.02, 'rep_b0_abs': 0.3, 'rep_frac': 0.95}
SKIP = {'.venv', 'venv', '.git', '__pycache__', 'site-packages', 'node_modules', '_trash'}

def dirs(ws):
    return [ws] + [d for d in sorted(ws.iterdir()) if d.is_dir() and d.name not in SKIP and not d.name.startswith('.')]

def find(ws, pats):
    for d in dirs(ws):
        for p in pats:
            h = sorted(d.glob(p))
            if h:
                return h[0]
    return None

def locate(ws):
    ws = Path(ws); return find(ws, ['predict.py']), find(ws, ['classical_recon.py'])

def fft2c(x):
    return np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(x, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))

def maps(img, te):
    te = np.asarray(te, float); mag = np.abs(img).astype(float); w = mag ** 2; lm = np.log(np.maximum(mag, 1e-12))
    t = te.reshape((-1, 1, 1))
    sw = w.sum(-3); st = (w * t).sum(-3); stt = (w * t * t).sum(-3); sy = (w * lm).sum(-3); sty = (w * t * lm).sum(-3)
    den = sw * stt - st ** 2
    r2s = -np.where(den > 0, (sw * sty - st * sy) / np.where(den > 0, den, 1), 0.0)
    z = (img[..., 1:, :, :] * np.conj(img[..., :-1, :, :])).sum(-3)
    return r2s, np.angle(z) / (2 * np.pi * np.diff(te).mean())

def masks_er(labels):
    return [[(k, binary_erosion(labels[i] == k)) for k in range(1, 5)] for i in range(len(labels))]

def roi_vals(r2s, b0, ME):
    out = []
    for i, ms in enumerate(ME):
        d = {}
        for k, m in ms:
            if m.sum() >= 10:
                d[str(k)] = {'r2s_per_s': float(r2s[i][m].mean()), 'b0_hz': float(b0[i][m].mean())}
        out.append(d)
    return out

def downstream(recon, data, truth):
    te = data['te_s']; ME = masks_er(data['labels'])
    r2s, b0 = maps(recon, te); est = roi_vals(r2s, b0, ME); tru = roi_vals(truth['r2s'], truth['b0'], ME)
    er, eb = [], []
    for e, t in zip(est, tru):
        for k, v in t.items():
            er.append(abs(e[k]['r2s_per_s'] / v['r2s_per_s'] - 1) if k in e else np.inf); eb.append(abs(e[k]['b0_hz'] - v['b0_hz']) if k in e else np.inf)
    er, eb = np.nan_to_num(np.array(er), nan=np.inf), np.nan_to_num(np.array(eb), nan=np.inf)
    s = {'r2s_rel_err_median': float(np.median(er)), 'r2s_rel_err_p90': float(np.percentile(er, 90)), 'b0_abs_err_median_hz': float(np.median(eb)), 'b0_abs_err_p90_hz': float(np.percentile(eb, 90))}
    s['pass'] = bool(s['r2s_rel_err_median'] <= TOL['r2s_med'] and s['r2s_rel_err_p90'] <= TOL['r2s_p90'] and s['b0_abs_err_median_hz'] <= TOL['b0_med'] and s['b0_abs_err_p90_hz'] <= TOL['b0_p90'])
    return s, est

def dc_rel(recon, data):
    k = fft2c(recon) * data['mask']
    return float(np.linalg.norm(k - data['kspace']) / np.linalg.norm(data['kspace']))

def load_recon(p, shape):
    r = np.load(p, allow_pickle=True)['recon']
    if r.shape != shape or not np.iscomplexobj(r) or not np.all(np.isfinite(r)):
        raise ValueError('recon shape/type %s %s' % (r.shape, r.dtype))
    return r

def chk(C, n, ok, d):
    C[n] = {'pass': bool(ok), 'detail': d}

def grade(ws, ev, python):
    ws = Path(ws).resolve(); ev = Path(ev).resolve(); ev.mkdir(parents=True, exist_ok=True)
    C, meas = {}, {}
    pred, clas = locate(ws)
    F = {'predict.py': pred, 'classical_recon.py': clas, 'test_recon_learned.npz': find(ws, ['test_recon_learned.npz']),
         'test_recon_classical.npz': find(ws, ['test_recon_classical.npz']), 'downstream_results.json': find(ws, ['downstream_results.json']),
         'split.json': find(ws, ['split.json']), 'README.md': find(ws, ['README.md']), 'figure': find(ws, ['*.png', 'figures/*.png']),
         'environment record': find(ws, ['environment*.txt', 'environment*.json', 'environment*.yml', 'requirements*.txt', 'env*.txt', 'pip-freeze*.txt', 'environment*.md'])}
    miss = [k for k, v in F.items() if v is None]
    chk(C, 'deliverables_present', not miss, {'missing': miss})
    tr = np.load(PUB / 'train.npz'); trsub = set(tr['subject_id'].tolist())
    pub = dict(np.load(PUB / 'test.npz')); pt = dict(np.load(HERE / 'test_truth.npz'))
    hid = dict(np.load(HERE / 'hidden' / 'hidden_test.npz')); ht = dict(np.load(HERE / 'hidden_test_truth.npz'))
    try:
        sp = json.loads(F['split.json'].read_text()); a = set(sp['train_subjects']); b = set(sp['validation_subjects'])
        ok = len(a) >= 10 and len(b) >= 3 and not (a & b) and a <= trsub and b <= trsub
        chk(C, 'split_by_subject', ok, {'n_train': len(a), 'n_val': len(b), 'overlap': sorted(a & b)[:10], 'unknown': sorted((a | b) - trsub)[:10]})
    except Exception as e:
        chk(C, 'split_by_subject', False, {'error': repr(e)[:300]})
    shape = pub['kspace'].shape
    R = {}
    for meth in ['learned', 'classical']:
        try:
            R[meth] = load_recon(F['test_recon_' + meth + '.npz'], shape)
        except Exception as e:
            meas['load_error_' + meth] = repr(e)[:300]
    chk(C, 'public_recon_schema', len(R) == 2, {'loaded': sorted(R)})
    dcs = {m: dc_rel(R[m], pub) for m in R}; meas['public_dc_rel'] = dcs
    chk(C, 'public_data_consistency', len(dcs) == 2 and all(v <= TOL['dc_rel'] for v in dcs.values()), {'dc_rel': dcs, 'tol': TOL['dc_rel']})
    est = {}
    for m in ['learned', 'classical']:
        if m in R:
            s, est[m] = downstream(R[m], pub, pt); meas['public_' + m] = s
            chk(C, 'public_' + m + '_downstream', s['pass'], {**s, 'tol': {k: TOL[k] for k in ('r2s_med', 'r2s_p90', 'b0_med', 'b0_p90')}})
        else:
            chk(C, 'public_' + m + '_downstream', False, {'error': 'no recon'})
    zf = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(pub['kspace'], axes=(-2, -1)), norm='ortho'), axes=(-2, -1))
    meas['public_zero_filled'], _ = downstream(zf, pub, pt)
    # reported downstream values vs grader recomputation from the submitted recon
    try:
        dr = json.loads(F['downstream_results.json'].read_text()); det = {}
        for m in ['learned', 'classical']:
            rep = dr['test'][m]; n = ok = 0
            for e, r in zip(est[m], rep):
                for k, v in e.items():
                    n += 1
                    if k in r and abs(float(r[k]['r2s_per_s']) / v['r2s_per_s'] - 1) <= TOL['rep_r2s_rel'] and abs(float(r[k]['b0_hz']) - v['b0_hz']) <= TOL['rep_b0_abs']:
                        ok += 1
            det[m] = {'n': n, 'n_match': ok, 'n_slices_reported': len(rep)}
        chk(C, 'reported_downstream_matches_recon', all(v['n'] > 0 and v['n_slices_reported'] == shape[0] and v['n_match'] >= TOL['rep_frac'] * v['n'] for v in det.values()), det)
        val = dr['validation']; tun = dr['classical_tuning']
        keys = ['r2s_rel_err_median', 'r2s_rel_err_p90', 'b0_abs_err_median_hz', 'b0_abs_err_p90_hz']
        okc = (all(all(np.isfinite(float(val[m][k])) for k in keys) for m in ['learned', 'classical', 'zero_filled'])
               and len(tun['values']) >= 2 and tun['selected'] in tun['values'] and dr['preferred_method'] in ('learned', 'classical')
               and set(val.get('subjects', [])) <= set(sp['validation_subjects']) and len(val.get('subjects', [])) >= 1)
        chk(C, 'validation_comparison_reported', okc, {'preferred': dr.get('preferred_method')})
    except Exception as e:
        chk(C, 'reported_downstream_matches_recon', False, {'error': repr(e)[:300]})
        chk(C, 'validation_comparison_reported', False, {'error': repr(e)[:300]})
    # hidden reruns
    for m, script in [('learned', pred), ('classical', clas)]:
        out = ev / ('hidden_' + m + '.npz'); res = None; run = {}
        if out.exists():
            shutil.move(str(out), str(ev / ('_old_' + out.name + '_%d' % len(list(ev.glob('_old_*'))))))
        if script is not None and python is not None:
            try:
                r = subprocess.run([str(python), str(script), '--input', str(HERE / 'hidden' / 'hidden_test.npz'), '--output', str(out)], cwd=str(script.parent), capture_output=True, text=True, timeout=1800)
                run = {'returncode': r.returncode, 'stderr': r.stderr[-800:]}
                res = load_recon(out, hid['kspace'].shape) if r.returncode == 0 else None
            except Exception as e:
                run = {'returncode': -1, 'stderr': repr(e)[:300]}
        chk(C, 'hidden_' + m + '_runs', res is not None, run)
        if res is not None:
            s, _ = downstream(res, hid, ht); s['dc_rel'] = dc_rel(res, hid); meas['hidden_' + m] = s
            chk(C, 'hidden_' + m + '_downstream', s['pass'] and s['dc_rel'] <= TOL['dc_rel'], s)
        else:
            chk(C, 'hidden_' + m + '_downstream', False, {'error': 'no hidden recon'})
    rd = F['README.md'].read_text(errors='ignore') if F['README.md'] else ''
    chk(C, 'readme_validation_limitations', len(rd) >= 200 and 'limitation' in rd.lower(), {'chars': len(rd)})
    return {'schema': 'heldout-v5-learnrecon-grade-1', 'all_automated_checks_pass': all(v['pass'] for v in C.values()), 'checks': C, 'measurements': meas,
            'located': {k: str(v) if v else None for k, v in F.items()}}

if __name__ == '__main__':
    ws, ev = Path(sys.argv[1]), Path(sys.argv[2]); py = sys.argv[3] if len(sys.argv) > 3 else sys.executable
    g = grade(ws, ev, py); (ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

