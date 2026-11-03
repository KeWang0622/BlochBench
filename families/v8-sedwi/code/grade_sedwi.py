#!/usr/bin/env python3
"""Grader for heldout-v8-sedwi (single-shot spin-echo EPI diffusion, ADC map)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v8common as V

TASK = HERE.parent / 'public/task.json'
PUB = HERE.parent / 'public/inputs/phantom.npz'
HID = HERE / 'hidden/phantom_hidden.npz'
REQ = ['sequence.seq', 'waveforms.png', 'simulation.npz', 'adcmap.npz', 'fit_adc.py', 'report.json', 'README.md', 'environment.txt']
TOL_ADC = 0.05
_T = json.load(open(TASK)); N = int(_T['matrix'][0]); BT = float(_T['b_target_s_per_mm2']); NADC = 4 * N
cls = lambda r: 'exc' if r['flip_deg'] < 135 else 'ref'


def expand_label(ph, lab):
    x = np.asarray(ph['x_m']); y = np.asarray(ph['y_m']); z = np.asarray(ph['z_offsets_m'])
    rho = np.where(ph['labels'] == lab, ph['density'], 0.0)
    iy, ix = np.nonzero(rho > 0); nz = len(z); rep = lambda q: np.repeat(q, nz)
    return {'x': rep(x[ix]), 'y': rep(y[iy]), 'z': np.tile(z, len(ix)), 'rho': rep(rho[iy, ix] / nz),
            'T1': rep(ph['T1_s'][iy, ix]), 'T2': rep(ph['T2_s'][iy, ix]), 'dw': rep(2 * np.pi * ph['B0_Hz'][iy, ix])}


def bmat(si, t_exc, t_refs, t_echo, dt=1e-6):
    t = np.arange(t_exc, t_echo, dt) + dt / 2
    G = np.stack([si.grad(ax, t) for ax in 'xyz'], 1)
    sign = np.ones(len(t))
    for tr in t_refs:
        sign[t > tr] *= -1
    k = np.cumsum(G * sign[:, None], 0) * dt
    return (2 * np.pi) ** 2 * (k.T @ k) * dt * 1e-6


def crossing_time(k, t):
    kx = k[:, 0]
    for i in range(len(kx) - 1):
        if (kx[i] <= 0 <= kx[i + 1]) or (kx[i] >= 0 >= kx[i + 1]):
            return float(t[i] if kx[i + 1] == kx[i] else t[i] + (0 - kx[i]) / (kx[i + 1] - kx[i]) * (t[i + 1] - t[i]))
    return None


def label_median(m, lab):
    return {int(k): float(np.median(np.asarray(m, float)[V.label_interior(lab, k)])) for k in np.unique(lab) if k > 0}


def grade(ws, ev, python=None):
    ws = Path(ws); ev = Path(ev); ev.mkdir(parents=True, exist_ok=True)
    C = V.Checks(); task = V.load_json(TASK); lim = task
    src, where = V.locate(ws)
    S = {}
    pub = V.load_npz(PUB); hid = V.load_npz(HID)
    DK = 1 / task['fov_m']

    def present():
        miss = [f for f in REQ if not (src / f).exists()]
        py = [p.name for p in src.glob('*.py')]
        return (not miss and len(py) >= 3), {'location': where, 'missing': miss, 'python_files': py}
    C.guard('deliverables_present', present)

    def readback():
        si = V.SeqInfo(src / 'sequence.seq', lim); S['si'] = si
        ns = sorted(set(a['n'] for a in si.adcs))
        return (len(si.adcs) == NADC and len(ns) == 1), {'n_rf': len(si.rfs), 'n_adc': len(si.adcs), 'samples_per_adc': ns}
    C.guard('sequence_readback', readback)
    si = S.get('si')
    C.guard('hardware_limits', lambda: V.hardware_check(si, lim))
    C.guard('raster_and_dead_times', lambda: V.timing_check(si, lim))

    def rf():
        bad = []
        for r in si.rfs:
            nom = 90 if cls(r) == 'exc' else 180
            if abs(r['flip_deg'] / nom - 1) > 0.02: bad.append('flip %.1f' % r['flip_deg'])
            gz = abs(float(si.grad('z', r['t_center']))); gxy = max(abs(float(si.grad('x', r['t_center']))), abs(float(si.grad('y', r['t_center']))))
            if gz < 0.5e-3 * lim['gamma_Hz_per_T'] or gxy > 1e-6 * lim['gamma_Hz_per_T'] or abs(r['freq_Hz']) > 1e-6: bad.append('RF %.4f s not slice-selective at z=0' % r['t_center'])
        ex = np.array([r['t_center'] for r in si.rfs if cls(r) == 'exc'])
        if len(ex) < 4 or np.abs(np.diff(ex) - task['repetition_time_s']).max() > 1e-6: bad.append('TR not constant')
        return not bad, {'violations': bad[:6], 'n_rf': len(si.rfs)}
    C.guard('rf_slice_selection_and_tr', rf)

    def contract():
        ks = si.kspace(classify=cls); S['k'] = ks; bad = []
        for n, k in enumerate(ks):
            j = n % N
            if np.abs(k[:, 1] - (j - N // 2) * DK).max() > 0.05: bad.append('adc %d ky' % n)
            if np.abs(k[:, 2]).max() > 0.05: bad.append('adc %d kz %.2f' % (n, np.abs(k[:, 2]).max()))
            kx = np.sort(k[:, 0]); lo, hi = -(N // 2) * DK, (N // 2 - 1) * DK
            if kx[0] > lo + 1e-6 or kx[-1] < hi - 1e-6: bad.append('adc %d kx coverage' % n)
            inside = kx[(kx >= lo - DK) & (kx <= hi + DK)]
            if inside.size < 2 or np.diff(inside).max() > DK * 1.0001: bad.append('adc %d kx gap' % n)
        return not bad, {'violations': bad[:6], 'n_violations': len(bad)}
    C.guard('sampling_contract', contract)

    def timing():
        ex = [r for r in si.rfs if cls(r) == 'exc']; rf_ref = [r for r in si.rfs if cls(r) == 'ref']
        ext = np.array([r['t_center'] for r in ex]); reft = np.array([r['t_center'] for r in rf_ref])
        bad = []; tes = []; info = []
        for v in range(4):
            a = si.adcs[v * N + N // 2]; tc = crossing_time(S['k'][v * N + N // 2], a['times'])
            if tc is None: bad.append('vol %d: no kx=0 crossing' % v); continue
            e = ext[ext < tc].max(); rr = reft[(reft > e) & (reft < tc)]
            te = tc - e; tes.append(te)
            if abs(te - task['echo_time_s']) > 10e-6: bad.append('vol %d TE %.3f ms' % (v, te * 1e3))
            if len(rr) != 1 or abs(rr[0] - (e + te / 2)) > 20e-6: bad.append('vol %d spin-echo condition violated' % v)
            B = bmat(si, e, list(rr), tc); info.append(B)
        S['te'] = float(np.median(tes)) if tes else None; S['B'] = info
        return not bad, {'violations': bad, 'TE_ms': [round(t * 1e3, 4) for t in tes]}
    C.guard('te_and_spin_echo_timing', timing)

    def bvals():
        B = S['B']; b = [float(np.trace(x)) for x in B]; S['b'] = b; bad = []
        if b[0] > 10: bad.append('b0 volume b = %.2f' % b[0])
        for v, ax in ((1, 0), (2, 1), (3, 2)):
            if abs(b[v] / BT - 1) > 0.01: bad.append('volume %d b = %.2f' % (v, b[v]))
            if B[v][ax, ax] < 0.95 * b[v]: bad.append('volume %d direction fraction %.3f' % (v, B[v][ax, ax] / b[v]))
        return not bad, {'violations': bad, 'b_trace_s_per_mm2': [round(x, 3) for x in b]}
    if 'B' in S and len(S['B']) == 4:
        C.guard('b_values_from_waveforms', bvals)
    else:
        C.add('b_values_from_waveforms', False, 'timing analysis failed')

    def archive_b():
        z = V.load_npz(src / 'simulation.npz'); bb = np.asarray(z['b_values_s_per_mm2'], float).ravel()
        ok = bb.shape == (4,) and abs(bb[0] - S['b'][0]) <= 1.0 and all(abs(bb[i] / S['b'][i] - 1) <= 0.01 for i in (1, 2, 3))
        return ok, {'archive_b': bb.tolist(), 'grader_b': [round(x, 3) for x in S['b']]}
    if 'b' in S:
        C.guard('archive_b_values_match', archive_b)
    else:
        C.add('archive_b_values_match', False, 'no grader b-values')

    def replay():
        lp = [k for k in np.unique(pub['labels']) if k > 0]; lh = [k for k in np.unique(hid['labels']) if k > 0]
        phs = [expand_label(pub, k) for k in lp] + [expand_label(hid, k) for k in lh]
        sigs, dt = V.koma_replay(src / 'sequence.seq', phs, ev / 'replay', timeout=1500)
        ns = si.adcs[0]['n']; vol = np.repeat(np.arange(4), N); b = np.asarray(S['b'])
        def comb(sl, ph, labs):
            out = np.zeros((NADC, ns), complex)
            for s, k in zip(sl, labs):
                D = float(np.median(ph['D_mm2_per_s'][ph['labels'] == k]))
                out += s.reshape(NADC, ns) * np.exp(-b[vol] * D)[:, None]
            return out
        S['rep_pub'] = comb(sigs[:len(lp)], pub, lp); S['rep_hid'] = comb(sigs[len(lp):], hid, lh)
        return True, {'koma_seconds': round(dt, 1)}
    if si is not None and len(si.adcs) == NADC and 'b' in S:
        C.guard('bloch_replay', replay)
    else:
        C.add('bloch_replay', False, 'skipped: ADC layout or b-values unavailable')

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

    def pubmap():
        m = np.asarray(V.load_npz(src / 'adcmap.npz')['adc_mm2_per_s'], float)
        got = label_median(m, pub['labels']); tru = label_median(pub['D_mm2_per_s'], pub['labels'])
        err = {k: got[k] / tru[k] - 1 for k in tru}
        rep = V.load_json(src / 'report.json').get('adc_by_label', {})
        rd = max(abs(float(rep.get(str(k), np.nan)) / got[k] - 1) for k in tru)
        return (all(abs(v) <= TOL_ADC for v in err.values()) and rd <= 0.01), {'relative_error_by_label': {k: round(v, 4) for k, v in err.items()}, 'report_vs_map': rd}
    C.guard('public_adc_map', pubmap)

    def hidden():
        if python is None:
            return False, 'no interpreter could run fit_adc.py on the public archive'
        z = V.load_npz(src / 'simulation.npz'); z['raw_signal'] = S['rep_hid'].reshape(np.asarray(z['raw_signal']).shape); z['phantom_sha256'] = np.array(V.sha256(HID))
        hp = ev / 'hidden_archive.npz'; np.savez(hp, **z)
        ok, out, rc, err = V.run_entry(python, src / 'fit_adc.py', hp, ev / 'hidden_run', 'simulation.npz', 'adcmap.npz')
        if not ok:
            return False, {'returncode': rc, 'stderr': err[-500:]}
        m = np.asarray(V.load_npz(out)['adc_mm2_per_s'], float)
        if m.shape != (N, N):
            return False, 'shape %s' % (m.shape,)
        got = label_median(m, hid['labels']); tru = label_median(hid['D_mm2_per_s'], hid['labels'])
        err = {k: got[k] / tru[k] - 1 for k in tru}
        return all(abs(v) <= TOL_ADC for v in err.values()), {'relative_error_by_label': {k: round(v, 4) for k, v in err.items()}}
    if 'rep_hid' in S:
        C.guard('hidden_rerun_adc', hidden)
    else:
        C.add('hidden_rerun_adc', False, 'no replay')

    def report():
        r = V.load_json(src / 'report.json')
        need = ['scope', 'bloch_simulation_performed', 'simulator', 'scanner_ready', 'realized_effective_echo_time_ms', 'realized_b_values_s_per_mm2',
                'b_value_method', 'steady_state_preparation', 'adc_by_label', 'software', 'validation_summary', 'limitations']
        miss = [k for k in need if k not in r]
        ok = not miss and r.get('bloch_simulation_performed') is True and r.get('scanner_ready') is False and isinstance(r.get('limitations'), list) and len(r['limitations']) > 0
        if ok and S.get('te') and 'b' in S:
            rb = [float(v) for v in r['realized_b_values_s_per_mm2']]
            ok = abs(float(r['realized_effective_echo_time_ms']) - S['te'] * 1e3) <= 0.01 and len(rb) == 4 and all(abs(rb[i] - S['b'][i]) <= max(1.0, 0.01 * S['b'][i]) for i in range(4))
        return ok, {'missing': miss}
    C.guard('report_fields', report)
    return C.result(task='heldout-v8-sedwi-r4', deliverable_location=where)


if __name__ == '__main__':
    print(json.dumps(grade(sys.argv[1], sys.argv[2], Path(sys.executable)), indent=1, default=str))

