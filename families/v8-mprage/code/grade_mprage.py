#!/usr/bin/env python3
"""Grader for heldout-v8-mprage-r4 (3D MP-RAGE with a T1 null; matrix, FOV, flip and null T1 from task.json)."""
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
NULL_T2 = [0.05, 0.07, 0.10]; SS_T1 = [1.9, 1.3, 0.45]
NULL_MAX = 0.01; SS_MAX = 0.02; IMG_NULL_MAX = 0.30; RECON_TOL = 0.03
_T = json.load(open(TASK))
NX, NY, NZ = (int(v) for v in _T['matrix'])
DKX, DKY, DKZ = (1 / float(v) for v in _T['fov_m'])
FA = float(_T['readout_flip_angle_deg']); T1NULL = float(_T['null_t1_s']); NADC = NZ * NY
SUB = np.asarray(np.load(PUB)['z_sub_offsets_m'], float); NSUB = len(SUB)


def expand3d(ph):
    rho = ph['density']; iz, iy, ix = np.nonzero(rho > 0); sub = ph['z_sub_offsets_m']; ns = len(sub); rep = lambda q: np.repeat(q, ns)
    return {'x': rep(ph['x_m'][ix]), 'y': rep(ph['y_m'][iy]), 'z': (ph['z_m'][iz][:, None] + sub[None, :]).ravel(), 'rho': rep(rho[iz, iy, ix] / ns),
            'T1': rep(ph['T1_s'][iz, iy, ix]), 'T2': rep(ph['T2_s'][iz, iy, ix]), 'dw': rep(2 * np.pi * ph['B0_Hz'][iz, iy, ix])}


def col(t1, t2):
    return {'x': np.zeros(NSUB), 'y': np.zeros(NSUB), 'z': SUB, 'rho': np.full(NSUB, 1 / NSUB), 'T1': np.full(NSUB, t1), 'T2': np.full(NSUB, t2)}


def grid_recon(raw, ks):
    K = np.zeros((NZ, NY, NX), complex)
    for c in range(NZ):
        for j in range(NY):
            k = ks[c * NY + j]
            iz = int(np.clip(np.rint(np.median(k[:, 2]) / DKZ) + NZ // 2, 0, NZ - 1)); iy = int(np.clip(np.rint(np.median(k[:, 1]) / DKY) + NY // 2, 0, NY - 1))
            ix = np.clip(np.rint(k[:, 0] / DKX).astype(int) + NX // 2, 0, NX - 1)
            K[iz, iy, ix] = raw[c, j]
    return np.fft.fftshift(np.fft.ifftn(np.fft.ifftshift(K))) * K.size


def interior3(lab, k):
    m = lab == k
    for ax in range(3):
        for s in (1, -1):
            m = m & (np.roll(lab, s, ax) == k)
    return m


def grade(ws, ev, python=None):
    ws = Path(ws); ev = Path(ev); ev.mkdir(parents=True, exist_ok=True)
    C = V.Checks(); task = V.load_json(TASK); lim = task
    src, where = V.locate(ws)
    S = {}
    pub = V.load_npz(PUB); hid = V.load_npz(HID)

    def present():
        miss = [f for f in REQ if not (src / f).exists()]
        py = [p.name for p in src.glob('*.py')]
        return (not miss and len(py) >= 3), {'location': where, 'missing': miss, 'python_files': py}
    C.guard('deliverables_present', present)

    def readback():
        si = V.SeqInfo(src / 'sequence.seq', lim); S['si'] = si
        ok = len(si.adcs) == NADC and all(a['n'] == NX for a in si.adcs)
        return ok, {'n_rf': len(si.rfs), 'n_adc': len(si.adcs), 'duration_s': round(si.total, 3)}
    C.guard('sequence_readback', readback)
    si = S.get('si')
    C.guard('hardware_limits', lambda: V.hardware_check(si, lim))
    C.guard('raster_and_dead_times', lambda: V.timing_check(si, lim))

    def nonsel():
        worst = 0.0
        for r in si.rfs:
            tt = np.linspace(r['t_start'], r['t_start'] + r['dur'], 9)
            for ax in 'xyz':
                worst = max(worst, float(np.abs(si.grad(ax, tt)).max()))
        return worst <= 1e-3 * lim['max_gradient_mT_per_m'] * 1e-3 * lim['gamma_Hz_per_T'], {'max_gradient_during_rf_mT_per_m': worst / lim['gamma_Hz_per_T'] * 1e3}
    C.guard('nonselective_rf', nonsel)

    def timing():
        bad = []
        inv = [r for r in si.rfs if r['flip_deg'] > 90]; ro = [r for r in si.rfs if r['flip_deg'] <= 90]
        it = np.array([r['t_center'] for r in inv]); rt = np.array([r['t_center'] for r in ro])
        if any(abs(r['flip_deg'] / 180 - 1) > 0.02 for r in inv): bad.append('inversion flip')
        if any(abs(r['flip_deg'] / FA - 1) > 0.01 for r in ro): bad.append('readout flip')
        if len(it) < NZ or np.abs(np.diff(it) - task['cycle_period_s']).max() > 1e-6: bad.append('cycle period')
        tis = []
        for c, t0 in enumerate(it):
            mine = rt[(rt > t0) & (rt < t0 + task['cycle_period_s'] - 1e-9)]
            if len(mine) != NY or np.abs(np.diff(mine) - task['readout_tr_s']).max() > 1e-6:
                bad.append('cycle %d train' % c); break
            tis.append(mine[NY // 2] - t0)
        if tis and np.ptp(tis) > 1e-6: bad.append('TI differs between cycles')
        te = []
        for a in si.adcs:
            j = np.searchsorted(rt, a['times'][0]) - 1; te.append(a['times'][NX // 2] - rt[j])
        te = np.array(te)
        if np.abs(te - task['echo_time_s']).max() > 5e-6: bad.append('TE')
        acq = sorted(set(int(np.searchsorted(it, a['times'][0]) - 1) for a in si.adcs))
        if acq != list(range(len(it) - NZ, len(it))): bad.append('acquired cycles %s' % acq)
        S['ti'] = float(np.median(tis)) if tis else None; S['te'] = float(np.median(te))
        return not bad, {'violations': bad[:6], 'TI_ms': S['ti'] * 1e3 if S['ti'] else None, 'n_cycles': len(it)}
    C.guard('flips_and_timing', timing)

    def contract():
        ks = si.kspace(classify=lambda r: 'exc' if r['flip_deg'] <= 90 else 'inv'); S['k'] = ks
        dev = 0.0; ms = []; bad = []
        for c in range(NZ):
            kz = np.median(ks[c * NY][:, 2]); m = int(np.rint(kz / DKZ)) + NZ // 2; ms.append(m)
            for j in range(NY):
                k = ks[c * NY + j]
                ex = np.stack([(np.arange(NX) - NX // 2) * DKX, np.full(NX, (j - NY // 2) * DKY), np.full(NX, (m - NZ // 2) * DKZ)], 1)
                dev = max(dev, float(np.abs(k - ex).max()))
        if sorted(ms) != list(range(NZ)): bad.append('partitions %s' % ms)
        if dev > task['sampling_contract']['tolerance_cycles_per_m']: bad.append('k deviation %.3f' % dev)
        S['ms'] = ms
        return not bad, {'violations': bad, 'max_k_deviation_cycles_per_m': dev, 'partition_order': ms}
    C.guard('sampling_contract', contract)

    def replay():
        phs = [expand3d(pub), expand3d(hid)] + [col(T1NULL, t2) for t2 in NULL_T2] + [col(t1, 0.07) for t1 in SS_T1]
        sigs, dt = V.koma_replay(src / 'sequence.seq', phs, ev / 'replay', timeout=1500)
        S['rep_pub'], S['rep_hid'] = sigs[0].reshape(NZ, NY, NX), sigs[1].reshape(NZ, NY, NX)
        S['null_cols'] = [s.reshape(NZ, NY, NX) for s in sigs[2:5]]; S['ss_cols'] = [s.reshape(NZ, NY, NX) for s in sigs[5:]]
        return True, {'koma_seconds': round(dt, 1)}
    if si is not None and len(si.adcs) == NADC and all(a['n'] == NX for a in si.adcs):
        C.guard('bloch_replay', replay)
    else:
        C.add('bloch_replay', False, 'skipped: ADC layout differs from the contract')

    def null():
        c0 = S['ms'].index(NZ // 2) if NZ // 2 in S['ms'] else None
        if c0 is None:
            return False, 'no kz = 0 cycle'
        vals = []
        for t2, s in zip(NULL_T2, S['null_cols']):
            ref = np.sin(np.deg2rad(FA)) * np.exp(-S['te'] / t2)
            vals.append(float(abs(s[c0, NY // 2, NX // 2]) / ref))
        return max(vals) <= NULL_MAX, {'null_metric_by_T2': [round(v, 5) for v in vals], 'limit': NULL_MAX}
    def steady():
        out = []
        for t1, s in zip(SS_T1, S['ss_cols']):
            v = []
            for c in range(NZ):
                kz = (S['ms'][c] - NZ // 2) * DKZ; F = abs(np.mean(np.exp(-2j * np.pi * kz * SUB)))
                v.append(abs(s[c, 0, NX // 2]) / F)
            v = np.array(v); out.append(float((v.max() - v.min()) / v.max()))
        return max(out) <= SS_MAX, {'spread_by_T1': dict(zip([str(x) for x in SS_T1], [round(x, 5) for x in out]))}
    if 'null_cols' in S and 'ms' in S:
        C.guard('t1_null_at_kspace_centre', null); C.guard('cycle_steady_state', steady)
    else:
        C.add('t1_null_at_kspace_centre', False, 'no replay'); C.add('cycle_steady_state', False, 'no replay')

    def simmatch():
        z = V.load_npz(src / 'simulation.npz'); raw = np.asarray(z['raw_signal'], complex).reshape(-1); rep = S['rep_pub'].reshape(-1)
        if raw.shape != rep.shape:
            return False, 'raw_signal shape mismatch'
        c = np.vdot(raw, rep); ph = c / abs(c) if abs(c) > 0 else 1
        rel = float(np.linalg.norm(raw * ph - rep) / np.linalg.norm(rep))
        sha_ok = str(z.get('sequence_sha256', '')) == V.sha256(src / 'sequence.seq')
        return (rel <= 0.08 and sha_ok), {'relative_difference_after_global_phase': rel, 'sequence_sha256_matches_delivered_file': sha_ok}
    if 'rep_pub' in S:
        C.guard('simulation_matches_replay', simmatch)
    else:
        C.add('simulation_matches_replay', False, 'no replay')

    def hidden():
        if python is None:
            return False, 'no interpreter could run reconstruct.py on the public archive'
        ref = grid_recon(S['rep_hid'], S['k'])
        z = V.load_npz(src / 'simulation.npz'); z['raw_signal'] = S['rep_hid']; z['phantom_sha256'] = np.array(V.sha256(HID))
        hp = ev / 'hidden_archive.npz'; np.savez(hp, **z)
        ok, out, rc, err = V.run_entry(python, src / 'reconstruct.py', hp, ev / 'hidden_run', 'simulation.npz', 'image.npz')
        if not ok:
            return False, {'returncode': rc, 'stderr': err[-500:]}
        im = np.abs(np.asarray(V.load_npz(out)['image']))
        if im.shape != (NZ, NY, NX):
            return False, 'image shape %s' % (im.shape,)
        r = np.abs(ref); sc = float(np.vdot(im.ravel(), r.ravel()).real / max(np.vdot(im.ravel(), im.ravel()).real, 1e-30))
        e = float(np.linalg.norm(sc * im - r) / np.linalg.norm(r))
        lab = hid['labels']; kn = [k for k in np.unique(lab) if k > 1 and abs(np.median(hid['T1_s'][lab == k]) - T1NULL) < 1e-6][0]
        ratio = float(np.median(im[interior3(lab, kn)]) / np.median(im[interior3(lab, 1)]))
        return (e <= RECON_TOL and ratio <= IMG_NULL_MAX), {'nrmse_vs_reference_recon': round(e, 5), 'nulled_vial_ratio': round(ratio, 4)}
    if 'rep_hid' in S and 'k' in S:
        C.guard('hidden_rerun_reconstruct', hidden)
    else:
        C.add('hidden_rerun_reconstruct', False, 'no replay')

    def pubimg():
        im = np.abs(np.asarray(V.load_npz(src / 'image.npz')['image'])); lab = pub['labels']
        r1 = np.median(im[interior3(lab, 1)])
        ratios = {str(k): float(np.median(im[interior3(lab, k)]) / r1) for k in np.unique(lab) if k > 1}
        rep = V.load_json(src / 'report.json').get('signal_ratio_by_label', {})
        diff = max(abs(float(rep.get(k, np.nan)) - v) for k, v in ratios.items())
        return diff <= 0.01, {'ratios_from_image': {k: round(v, 4) for k, v in ratios.items()}, 'max_report_difference': diff}
    C.guard('public_image_and_report_ratios', pubimg)

    def report():
        r = V.load_json(src / 'report.json')
        need = ['scope', 'bloch_simulation_performed', 'simulator', 'scanner_ready', 'realized_inversion_time_ms', 'realized_echo_time_ms', 'realized_readout_tr_ms',
                'realized_cycle_period_ms', 'ti_derivation', 'steady_state_preparation', 'signal_ratio_by_label', 'software', 'validation_summary', 'limitations']
        miss = [k for k in need if k not in r]
        ok = not miss and r.get('bloch_simulation_performed') is True and r.get('scanner_ready') is False and isinstance(r.get('limitations'), list) and len(r['limitations']) > 0
        if ok and S.get('ti'):
            ok = abs(float(r['realized_inversion_time_ms']) - S['ti'] * 1e3) <= 0.01
        return ok, {'missing': miss}
    C.guard('report_fields', report)
    return C.result(task='heldout-v8-mprage-r4', deliverable_location=where)


if __name__ == '__main__':
    print(json.dumps(grade(sys.argv[1], sys.argv[2], Path(sys.executable)), indent=1, default=str))

