#!/usr/bin/env python3
"""Grader for heldout-v8-spiral (interleaved spiral-out GRE, slew-limited design, known gradient delay)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v8common as V

TASK = HERE.parent / 'public/task.json'
PUB = HERE.parent / 'public/inputs/phantom.npz'
HID = HERE / 'hidden/phantom_hidden.npz'
HPAR = json.load(open(HERE / 'hidden/hidden_params.json'))
REQ = ['sequence.seq', 'waveforms.png', 'simulation.npz', 'image.npz', 'reconstruct.py', 'report.json', 'README.md', 'environment.txt']
CONSIST_MAX = 0.05; ACC_MAX = 0.25
N = int(json.load(open(TASK))['matrix'][0])


def expand(ph):
    x = np.asarray(ph['x_m']); y = np.asarray(ph['y_m']); z = np.asarray(ph['z_offsets_m']); rho = np.asarray(ph['density'])
    iy, ix = np.nonzero(rho > 0); nz = len(z); rep = lambda q: np.repeat(q, nz)
    return {'x': rep(x[ix]), 'y': rep(y[iy]), 'z': np.tile(z, len(ix)), 'rho': rep(rho[iy, ix] / nz),
            'T1': rep(ph['T1_s'][iy, ix]), 'T2': rep(ph['T2_s'][iy, ix]), 'dw': rep(2 * np.pi * ph['B0_Hz'][iy, ix])}


def ls_recon(raw, kx, ky, fov, iters=40):
    x = (np.arange(N) - N // 2) * fov / N
    X, Y = np.meshgrid(x, x); r = np.stack([X.ravel(), Y.ravel()], 1)
    def E(img):
        out = np.empty(kx.size, complex)
        for s in range(0, kx.size, 4096):
            out[s:s + 4096] = np.exp(-2j * np.pi * (np.outer(kx[s:s + 4096], r[:, 0]) + np.outer(ky[s:s + 4096], r[:, 1]))) @ img
        return out
    def EH(y):
        out = np.zeros(r.shape[0], complex)
        for s in range(0, kx.size, 4096):
            out += np.exp(2j * np.pi * (np.outer(r[:, 0], kx[s:s + 4096]) + np.outer(r[:, 1], ky[s:s + 4096]))) @ y[s:s + 4096]
        return out
    b = EH(raw); xk = np.zeros_like(b); rr = b.copy(); p = rr.copy(); rs = np.vdot(rr, rr)
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
        ok = 1 <= len(si.adcs) <= N and len(ns) == 1 and len(si.rfs) == len(si.adcs)
        return ok, {'n_rf': len(si.rfs), 'n_adc': len(si.adcs), 'samples_per_adc': ns}
    C.guard('sequence_readback', readback)
    si = S.get('si')
    C.guard('hardware_limits', lambda: V.hardware_check(si, lim))
    C.guard('raster_and_dead_times', lambda: V.timing_check(si, lim))

    def rf():
        bad = []
        for r in si.rfs:
            if abs(r['flip_deg'] / 90 - 1) > 0.02: bad.append('flip %.1f' % r['flip_deg'])
            gz = abs(float(si.grad('z', r['t_center']))); gxy = max(abs(float(si.grad('x', r['t_center']))), abs(float(si.grad('y', r['t_center']))))
            if gz < 0.5e-3 * lim['gamma_Hz_per_T'] or gxy > 1e-6 * lim['gamma_Hz_per_T'] or abs(r['freq_Hz']) > 1e-6: bad.append('RF not slice-selective at z = 0')
        ex = np.array([r['t_center'] for r in si.rfs])
        if len(ex) > 1 and np.abs(np.diff(ex) - task['repetition_time_s']).max() > 1e-6: bad.append('TR not constant')
        return not bad, {'violations': bad[:5]}
    C.guard('rf_slice_selection_and_tr', rf)

    def contract():
        ks = si.kspace(classify=lambda r: 'exc'); S['k'] = ks; bad = []
        ex = np.array([r['t_center'] for r in si.rfs])
        for i, (a, k) in enumerate(zip(si.adcs, ks)):
            e = ex[ex < a['times'][0]].max()
            te = a['times'][0] - e
            if abs(te - task['echo_time_s']) > 10e-6: bad.append('interleave %d TE %.4f ms' % (i, te * 1e3))
            if np.hypot(k[0, 0], k[0, 1]) > 1.0: bad.append('interleave %d first sample |k| = %.2f' % (i, np.hypot(k[0, 0], k[0, 1])))
            if a['times'][-1] - a['times'][0] + a['dwell'] > task['max_readout_duration_s'] + 1e-9: bad.append('interleave %d readout too long' % i)
            if np.abs(k[:, 2]).max() > 0.05: bad.append('interleave %d kz %.3f' % (i, np.abs(k[:, 2]).max()))
        from scipy.spatial import cKDTree
        pts = np.concatenate([k[:, :2] for k in ks])
        R = (N / 2) / FOV; h = 0.25
        g = np.arange(-R, R + h, h); GX, GY = np.meshgrid(g, g); m = np.hypot(GX, GY) <= R
        d, _ = cKDTree(pts).query(np.stack([GX[m], GY[m]], 1))
        fill = float(d.max())
        if fill > 0.6 / FOV: bad.append('coverage gap %.2f cycles/m > %.2f' % (fill, 0.6 / FOV))
        return not bad, {'violations': bad[:6], 'fill_distance_cycles_per_m': round(fill, 3), 'limit': round(0.6 / FOV, 3)}
    C.guard('sampling_contract_te_coverage', contract)

    def replay():
        d1, d2 = HPAR['hidden_delays_s']
        sigs, dt = V.koma_replay(src / 'sequence.seq', [expand(pub), expand(hid), expand(hid), expand(hid)], ev / 'replay', timeout=1500,
                                 adc_shifts=[0.0, 0.0, -d1, -d2])
        S['rep'] = sigs
        return True, {'koma_seconds': round(dt, 1)}
    if si is not None and len(si.adcs) >= 1 and len(set(a['n'] for a in si.adcs)) == 1:
        C.guard('bloch_replay', replay)
    else:
        C.add('bloch_replay', False, 'skipped: ADC layout differs from the contract')

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

    def refimgs():
        kx = np.concatenate([k[:, 0] for k in S['k']]); ky = np.concatenate([k[:, 1] for k in S['k']])
        S['ref_pub'] = ls_recon(S['rep'][0], kx, ky, FOV); S['ref_hid'] = ls_recon(S['rep'][1], kx, ky, FOV)

    def hidden():
        if python is None:
            return False, 'no interpreter could run reconstruct.py on the public archive'
        refimgs()
        z0 = V.load_npz(src / 'simulation.npz'); shp = np.asarray(z0['raw_signal']).shape
        imgs = {}; out = {}
        for tag, idx, d in (('delta_0', 1, 0.0), ('delta_a', 2, HPAR['hidden_delays_s'][0]), ('delta_b', 3, HPAR['hidden_delays_s'][1])):
            z = dict(z0); z['raw_signal'] = S['rep'][idx].reshape(shp); z['gradient_delay_s'] = np.array(d); z['phantom_sha256'] = np.array(V.sha256(HID))
            hp = ev / ('hidden_%s.npz' % tag); np.savez(hp, **z)
            ok, o, rc, err = V.run_entry(python, src / 'reconstruct.py', hp, ev / ('hidden_run_' + tag), 'simulation.npz', 'image.npz')
            if not ok:
                return False, {tag: {'returncode': rc, 'stderr': err[-400:]}}
            im = np.asarray(V.load_npz(o)['image'])
            if im.shape != (N, N):
                return False, {tag: 'image shape %s' % (im.shape,)}
            imgs[tag] = im
        acc = nrmse(imgs['delta_0'], S['ref_hid'])
        ca = nrmse(imgs['delta_a'], imgs['delta_0']); cb = nrmse(imgs['delta_b'], imgs['delta_0'])
        out = {'own_delta0_vs_reference_nrmse': round(acc, 4), 'delay_a_vs_own_delta0_nrmse': round(ca, 4), 'delay_b_vs_own_delta0_nrmse': round(cb, 4),
               'delays_s': HPAR['hidden_delays_s']}
        return (acc <= ACC_MAX and ca <= CONSIST_MAX and cb <= CONSIST_MAX), out
    if 'rep' in S and 'k' in S:
        C.guard('hidden_rerun_reconstruct_with_delay', hidden)
    else:
        C.add('hidden_rerun_reconstruct_with_delay', False, 'no replay')

    def pubimg():
        if 'ref_pub' not in S:
            refimgs()
        im = np.asarray(V.load_npz(src / 'image.npz')['image'])
        e = nrmse(im, S['ref_pub'])
        lab = pub['labels']; a = np.abs(im); r1 = np.median(a[V.label_interior(lab, 1)])
        ratios = {str(k): float(np.median(a[V.label_interior(lab, k)]) / r1) for k in range(2, 7)}
        rep = V.load_json(src / 'report.json').get('signal_ratio_by_label', {})
        diff = max(abs(float(rep.get(k, np.nan)) - v) for k, v in ratios.items())
        return (e <= ACC_MAX and diff <= 0.01), {'nrmse_vs_reference': round(e, 4), 'max_report_ratio_difference': diff}
    if 'rep' in S and 'k' in S:
        C.guard('public_image_and_report_ratios', pubimg)
    else:
        C.add('public_image_and_report_ratios', False, 'no replay')

    def report():
        r = V.load_json(src / 'report.json')
        need = ['scope', 'bloch_simulation_performed', 'simulator', 'scanner_ready', 'n_interleaves', 'readout_duration_ms', 'realized_echo_time_ms',
                'trajectory_design', 'delay_handling', 'signal_ratio_by_label', 'software', 'validation_summary', 'limitations']
        miss = [k for k in need if k not in r]
        ok = not miss and r.get('bloch_simulation_performed') is True and r.get('scanner_ready') is False and isinstance(r.get('limitations'), list) and len(r['limitations']) > 0
        if ok and si is not None:
            ok = int(r['n_interleaves']) == len(si.adcs) and abs(float(r['realized_echo_time_ms']) - task['echo_time_s'] * 1e3) <= 0.02
        return ok, {'missing': miss}
    C.guard('report_fields', report)
    return C.result(task='heldout-v8-spiral-r4', deliverable_location=where)


if __name__ == '__main__':
    print(json.dumps(grade(sys.argv[1], sys.argv[2], Path(sys.executable)), indent=1, default=str))

