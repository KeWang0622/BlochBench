#!/usr/bin/env python3
"""Grader for heldout-v8-ute (2D UTE with half-pulse excitation pairs and centre-out radial readout)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v8common as V

TASK = HERE.parent / 'public/task.json'
PUB = HERE.parent / 'public/inputs/phantom.npz'
HID = HERE / 'hidden/phantom_hidden.npz'
REQ = ['sequence.seq', 'waveforms.png', 'simulation.npz', 'image.npz', 'reconstruct.py', 'report.json', 'README.md', 'environment.txt']
ACC_MAX = 0.25; RATIO_TOL = 0.15; RETAIN_MIN = 0.5; SS_MAX = 0.02
_T = json.load(open(TASK)); N = int(_T['matrix'][0]); FA = float(_T['flip_angle_deg']); ZOUT = float(_T['slice_profile_requirement_out_of_slice_abs_z_m'])
ZP = np.round(np.arange(-30, 31) * 0.55, 6) * 1e-3


def expand(ph):
    x = np.asarray(ph['x_m']); y = np.asarray(ph['y_m']); z = np.asarray(ph['z_offsets_m']); rho = np.asarray(ph['density'])
    iy, ix = np.nonzero(rho > 0); nz = len(z); rep = lambda q: np.repeat(q, nz)
    return {'x': rep(x[ix]), 'y': rep(y[iy]), 'z': np.tile(z, len(ix)), 'rho': rep(rho[iy, ix] / nz),
            'T1': rep(ph['T1_s'][iy, ix]), 'T2': rep(ph['T2_s'][iy, ix]), 'dw': rep(2 * np.pi * ph['B0_Hz'][iy, ix])}


def ls_recon(y, kx, ky, fov, iters=40):
    x = (np.arange(N) - N // 2) * fov / N
    X, Y = np.meshgrid(x, x); r = np.stack([X.ravel(), Y.ravel()], 1)
    def E(img):
        out = np.empty(kx.size, complex)
        for s in range(0, kx.size, 4096):
            out[s:s + 4096] = np.exp(-2j * np.pi * (np.outer(kx[s:s + 4096], r[:, 0]) + np.outer(ky[s:s + 4096], r[:, 1]))) @ img
        return out
    def EH(v):
        out = np.zeros(r.shape[0], complex)
        for s in range(0, kx.size, 4096):
            out += np.exp(2j * np.pi * (np.outer(r[:, 0], kx[s:s + 4096]) + np.outer(r[:, 1], ky[s:s + 4096]))) @ v[s:s + 4096]
        return out
    b = EH(y); xk = np.zeros_like(b); rr = b.copy(); p = rr.copy(); rs = np.vdot(rr, rr)
    for _ in range(iters):
        Ap = EH(E(p)); al = rs / np.vdot(p, Ap); xk = xk + al * p; rr = rr - al * Ap
        rn = np.vdot(rr, rr)
        if abs(rn) < 1e-12 * abs(np.vdot(b, b)): break
        p = rr + rn / rs * p; rs = rn
    return xk.reshape(N, N)


def nrmse(a, b):
    a = np.abs(a).ravel(); b = np.abs(b).ravel()
    sc = float(np.vdot(a, b).real / max(np.vdot(a, a).real, 1e-30))
    return float(np.linalg.norm(sc * a - b) / np.linalg.norm(b))


def fwhm(p):
    h = p.max() / 2; i0 = int(np.argmax(p))
    l = i0
    while l > 0 and p[l - 1] >= h: l -= 1
    r = i0
    while r < len(p) - 1 and p[r + 1] >= h: r += 1
    zl = ZP[l] if l == 0 else ZP[l - 1] + (h - p[l - 1]) / (p[l] - p[l - 1]) * (ZP[l] - ZP[l - 1])
    zr = ZP[r] if r == len(p) - 1 else ZP[r] + (p[r] - h) / (p[r] - p[r + 1]) * (ZP[r + 1] - ZP[r])
    return float(zr - zl)


def ratios(img, ph):
    lab = ph['labels']; a = np.abs(img); r1 = np.median(a[V.label_interior(lab, 1)])
    return {int(k): float(np.median(a[V.label_interior(lab, k)]) / r1) for k in np.unique(lab) if k > 1}


def grade(ws, ev, python=None):
    ws = Path(ws); ev = Path(ev); ev.mkdir(parents=True, exist_ok=True)
    C = V.Checks(); task = V.load_json(TASK); lim = task
    src, where = V.locate(ws)
    S = {}
    pub = V.load_npz(PUB); hid = V.load_npz(HID)
    FOV = task['fov_m']

    def present():
        miss = [f for f in REQ if not (src / f).exists()]
        py = [p.name for p in src.glob('*.py')]
        return (not miss and len(py) >= 3), {'location': where, 'missing': miss, 'python_files': py}
    C.guard('deliverables_present', present)

    def readback():
        si = V.SeqInfo(src / 'sequence.seq', lim); S['si'] = si
        ns = sorted(set(a['n'] for a in si.adcs))
        ok = len(si.adcs) >= 2 and len(si.adcs) % 2 == 0 and len(ns) == 1
        return ok, {'n_rf': len(si.rfs), 'n_adc': len(si.adcs), 'samples_per_adc': ns}
    C.guard('sequence_readback', readback)
    si = S.get('si')
    C.guard('hardware_limits', lambda: V.hardware_check(si, lim))
    C.guard('raster_and_dead_times', lambda: V.timing_check(si, lim))

    def rf():
        bad = []
        for r in si.rfs:
            if abs(r['flip_deg'] / FA - 1) > 0.02: bad.append('flip %.2f' % r['flip_deg'])
            gz = abs(float(si.grad('z', r['t_center']))); gxy = max(abs(float(si.grad('x', r['t_center']))), abs(float(si.grad('y', r['t_center']))))
            if gz < 0.5e-3 * lim['gamma_Hz_per_T'] or gxy > 1e-6 * lim['gamma_Hz_per_T'] or abs(r['freq_Hz']) > 1e-6: bad.append('RF not slice-selective at z = 0')
        rc = np.array([r['t_center'] for r in si.rfs])
        if len(rc) > 1 and np.abs(np.diff(rc) - task['repetition_time_s']).max() > 1e-6: bad.append('TR not constant')
        return not bad, {'violations': sorted(set(bad))[:5], 'n_rf': len(si.rfs)}
    C.guard('rf_flip_slice_selection_tr', rf)

    def contract():
        ks = si.kspace(classify=lambda r: 'exc'); S['k'] = ks; bad = []
        ends = np.array([r['t_start'] + r['dur'] for r in si.rfs]); tes = []
        for i, (a, k) in enumerate(zip(si.adcs, ks)):
            te = a['times'][0] - ends[ends < a['times'][0]].max(); tes.append(te)
            if np.hypot(k[0, 0], k[0, 1]) > 1.0: bad.append('adc %d first sample |k| = %.2f' % (i, np.hypot(k[0, 0], k[0, 1])))
            if np.abs(k[:, 2]).max() > 0.05: bad.append('adc %d kz %.3f' % (i, np.abs(k[:, 2]).max()))
        for p in range(len(ks) // 2):
            if np.abs(ks[2 * p][:, :2] - ks[2 * p + 1][:, :2]).max() > 0.05: bad.append('pair %d trajectories differ' % p); break
        tes = np.array(tes)
        if tes.max() > task['max_ute_echo_time_s'] + 1e-9: bad.append('UTE echo time %.3f ms' % (tes.max() * 1e3))
        from scipy.spatial import cKDTree
        pts = np.concatenate([k[:, :2] for k in ks[0::2]])
        R = (N / 2) / FOV; h = 0.25
        gg = np.arange(-R, R + h, h); GX, GY = np.meshgrid(gg, gg); m = np.hypot(GX, GY) <= R
        d, _ = cKDTree(pts).query(np.stack([GX[m], GY[m]], 1)); fill = float(d.max())
        if fill > 0.6 / FOV: bad.append('coverage gap %.2f cycles/m' % fill)
        S['te'] = float(tes.max())
        return not bad, {'violations': bad[:6], 'ute_echo_time_ms': round(S['te'] * 1e3, 4), 'fill_distance_cycles_per_m': round(fill, 3)}
    C.guard('sampling_contract_te_coverage', contract)

    def profile():
        b_adc = [b['index'] for b in si.blocks if b['adc'] is not None][:2]
        b_rf = [b['index'] for b in si.blocks if b['rf'] is not None and b['index'] < b_adc[0]][-1]
        phs = [{'x': np.zeros(1), 'y': np.zeros(1), 'z': np.array([z]), 'rho': np.ones(1), 'T1': np.full(1, 100.0), 'T2': np.full(1, 0.002)} for z in ZP]
        sigs, dt = V.koma_replay(src / 'sequence.seq', phs, ev / 'profile', timeout=900, block_range=[int(b_rf), int(b_adc[1])])
        ns = si.adcs[0]['n']
        prof = np.array([abs(s.reshape(2, ns)[0, 0] + s.reshape(2, ns)[1, 0]) for s in sigs])
        w = fwhm(prof); out = float(prof[np.abs(ZP) > ZOUT + 1e-9].sum() / prof.sum())
        lo, hi = task['slice_profile_requirement_fwhm_range_m']
        return (lo <= w <= hi and out <= task['slice_profile_requirement_max_out_of_slice_fraction']), {'pair_fwhm_mm': round(w * 1e3, 3), 'out_of_slice_fraction': round(out, 4)}
    if si is not None and len(si.adcs) >= 2:
        C.guard('half_pulse_pair_slice_profile', profile)
    else:
        C.add('half_pulse_pair_slice_profile', False, 'no ADC pairs')

    def replay():
        sigs, dt = V.koma_replay(src / 'sequence.seq', [expand(pub), expand(hid)], ev / 'replay', timeout=1500)
        S['rep'] = sigs
        return True, {'koma_seconds': round(dt, 1)}
    if si is not None and len(si.adcs) >= 2 and len(set(a['n'] for a in si.adcs)) == 1:
        C.guard('bloch_replay', replay)
    else:
        C.add('bloch_replay', False, 'skipped')

    def simmatch():
        z = V.load_npz(src / 'simulation.npz'); raw = np.asarray(z['raw_signal'], complex).reshape(-1); rep = S['rep'][0]
        if raw.shape != rep.shape:
            return False, 'raw_signal shape mismatch'
        c = np.vdot(raw, rep); ph = c / abs(c) if abs(c) > 0 else 1
        rel = float(np.linalg.norm(raw * ph - rep) / np.linalg.norm(rep))
        sha_ok = str(z.get('sequence_sha256', '')) == V.sha256(src / 'sequence.seq')
        return (rel <= 0.08 and sha_ok), {'relative_difference_after_global_phase': rel, 'sequence_sha256_matches_delivered_file': sha_ok}
    if 'rep' in S:
        C.guard('simulation_matches_replay', simmatch)
    else:
        C.add('simulation_matches_replay', False, 'no replay')

    def refimg(sig):
        ns = si.adcs[0]['n']; s = sig.reshape(-1, ns); y = (s[0::2] + s[1::2]).ravel()
        kk = np.array(S['k'][0::2]); return ls_recon(y, kk[:, :, 0].ravel(), kk[:, :, 1].ravel(), FOV)

    def hidden():
        if python is None:
            return False, 'no interpreter could run reconstruct.py on the public archive'
        ref = refimg(S['rep'][1])
        z = V.load_npz(src / 'simulation.npz'); z['raw_signal'] = S['rep'][1].reshape(np.asarray(z['raw_signal']).shape); z['phantom_sha256'] = np.array(V.sha256(HID))
        hp = ev / 'hidden_archive.npz'; np.savez(hp, **z)
        ok, out, rc, err = V.run_entry(python, src / 'reconstruct.py', hp, ev / 'hidden_run', 'simulation.npz', 'image.npz')
        if not ok:
            return False, {'returncode': rc, 'stderr': err[-500:]}
        im = np.asarray(V.load_npz(out)['image'])
        if im.shape != (N, N):
            return False, 'image shape %s' % (im.shape,)
        e = nrmse(im, ref); rg = ratios(ref, hid); rp = ratios(im, hid)
        short = [k for k in rg if np.median(hid['T2_s'][hid['labels'] == k]) <= 0.002]
        rho = lambda k: float(np.median(hid['density'][hid['labels'] == k]))
        retain = {k: rg[k] * rho(1) / rho(k) for k in short}
        rdev = {k: rp[k] / rg[k] - 1 for k in short}
        ok = e <= ACC_MAX and all(abs(v) <= RATIO_TOL for v in rdev.values()) and all(v >= RETAIN_MIN for v in retain.values())
        return ok, {'nrmse_vs_reference': round(e, 4), 'short_t2_retention_reference_recon': {k: round(v, 3) for k, v in retain.items()},
                    'short_t2_ratio_deviation_your_recon': {k: round(v, 4) for k, v in rdev.items()}}
    if 'rep' in S and 'k' in S:
        C.guard('hidden_rerun_reconstruct_short_t2', hidden)
    else:
        C.add('hidden_rerun_reconstruct_short_t2', False, 'no replay')

    def pubimg():
        im = np.asarray(V.load_npz(src / 'image.npz')['image'])
        ref = refimg(S['rep'][0]); e = nrmse(im, ref)
        rp = ratios(im, pub)
        rep = V.load_json(src / 'report.json').get('signal_ratio_by_label', {})
        diff = max(abs(float(rep.get(str(k), np.nan)) - v) for k, v in rp.items())
        return (e <= ACC_MAX and diff <= 0.01), {'nrmse_vs_reference': round(e, 4), 'max_report_ratio_difference': diff}
    if 'rep' in S and 'k' in S:
        C.guard('public_image_and_report_ratios', pubimg)
    else:
        C.add('public_image_and_report_ratios', False, 'no replay')

    def report():
        r = V.load_json(src / 'report.json')
        need = ['scope', 'bloch_simulation_performed', 'simulator', 'scanner_ready', 'n_spokes', 'realized_ute_echo_time_ms', 'excitation_design',
                'readout_design', 'steady_state_preparation', 'signal_ratio_by_label', 'software', 'validation_summary', 'limitations']
        miss = [k for k in need if k not in r]
        ok = not miss and r.get('bloch_simulation_performed') is True and r.get('scanner_ready') is False and isinstance(r.get('limitations'), list) and len(r['limitations']) > 0
        if ok and 'te' in S:
            ok = int(r['n_spokes']) == len(si.adcs) // 2 and abs(float(r['realized_ute_echo_time_ms']) - S['te'] * 1e3) <= 0.005
        return ok, {'missing': miss}
    C.guard('report_fields', report)
    return C.result(task='heldout-v8-ute-r4', deliverable_location=where)


if __name__ == '__main__':
    print(json.dumps(grade(sys.argv[1], sys.argv[2], Path(sys.executable)), indent=1, default=str))

