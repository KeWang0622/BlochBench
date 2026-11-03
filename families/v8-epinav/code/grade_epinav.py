#!/usr/bin/env python3
"""Grader for heldout-v8-epinav (single-shot ramp-sampled GE-EPI with hidden gradient delay)."""
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
GHOST_MAX = 0.08; CONSIST_MAX = 0.12; ACC_MAX = 0.25
N = int(json.load(open(TASK))['matrix'][0])


def expand(ph):
    x = np.asarray(ph['x_m']); y = np.asarray(ph['y_m']); z = np.asarray(ph['z_offsets_m']); rho = np.asarray(ph['density'])
    iy, ix = np.nonzero(rho > 0); nz = len(z); rep = lambda q: np.repeat(q, nz)
    return {'x': rep(x[ix]), 'y': rep(y[iy]), 'z': np.tile(z, len(ix)), 'rho': rep(rho[iy, ix] / nz),
            'T1': rep(ph['T1_s'][iy, ix]), 'T2': rep(ph['T2_s'][iy, ix]), 'dw': rep(2 * np.pi * ph['B0_Hz'][iy, ix])}


def ref_recon(raw_img, k_img, fov):
    x = (np.arange(N) - N // 2) * fov / N
    P = []
    for s, k in zip(raw_img, k_img):
        E = np.exp(-2j * np.pi * np.outer(k[:, 0], x))
        P.append(np.linalg.lstsq(E, s, rcond=None)[0])
    ky = np.array([np.median(k[:, 1]) for k in k_img])
    return np.exp(2j * np.pi * np.outer(x, ky)) @ np.array(P)


def ghost_level(img, lab):
    far = lab == 0
    for _ in range(2):
        far = far & np.roll(far, 1, 0) & np.roll(far, -1, 0) & np.roll(far, 1, 1) & np.roll(far, -1, 1)
    return float(np.abs(img)[far].mean() / np.median(np.abs(img)[V.label_interior(lab, 1)]))


def nrmse(a, b):
    a = np.abs(a).ravel(); b = np.abs(b).ravel()
    sc = float(np.vdot(a, b).real / max(np.vdot(a, a).real, 1e-30))
    return float(np.linalg.norm(sc * a - b) / np.linalg.norm(b))


def crossing_time(k, t):
    kx = k[:, 0]
    for i in range(len(kx) - 1):
        if (kx[i] <= 0 <= kx[i + 1]) or (kx[i] >= 0 >= kx[i + 1]):
            if kx[i + 1] == kx[i]:
                return float(t[i])
            return float(t[i] + (0 - kx[i]) / (kx[i + 1] - kx[i]) * (t[i + 1] - t[i]))
    return None


def grade(ws, ev, python=None):
    ws = Path(ws); ev = Path(ev); ev.mkdir(parents=True, exist_ok=True)
    C = V.Checks(); task = V.load_json(TASK); lim = task
    src, where = V.locate(ws)
    S = {}
    pub = V.load_npz(PUB); hid = V.load_npz(HID)
    FOV = task['fov_m']; DK = 1 / FOV

    def present():
        miss = [f for f in REQ if not (src / f).exists()]
        py = [p.name for p in src.glob('*.py')]
        return (not miss and len(py) >= 3), {'location': where, 'missing': miss, 'python_files': py}
    C.guard('deliverables_present', present)

    def readback():
        si = V.SeqInfo(src / 'sequence.seq', lim); S['si'] = si
        ns = sorted(set(a['n'] for a in si.adcs))
        ok = len(si.adcs) >= N and len(ns) == 1
        return ok, {'n_rf': len(si.rfs), 'n_adc': len(si.adcs), 'samples_per_adc': ns}
    C.guard('sequence_readback', readback)
    si = S.get('si')
    C.guard('hardware_limits', lambda: V.hardware_check(si, lim))
    C.guard('raster_and_dead_times', lambda: V.timing_check(si, lim))

    def excitation():
        if len(si.rfs) != 1:
            return False, '%d RF pulses (exactly one required)' % len(si.rfs)
        r = si.rfs[0]
        gz = abs(float(si.grad('z', r['t_center']))); gxy = max(abs(float(si.grad('x', r['t_center']))), abs(float(si.grad('y', r['t_center']))))
        ok = abs(r['flip_deg'] / 90 - 1) <= 0.02 and gz > 0.5e-3 * lim['gamma_Hz_per_T'] and gxy < 1e-6 * lim['gamma_Hz_per_T'] and abs(r['freq_Hz']) < 1e-6
        return ok, {'flip_deg': r['flip_deg'], 'gz_mT_per_m': gz / lim['gamma_Hz_per_T'] * 1e3}
    C.guard('single_slice_selective_excitation', excitation)

    def contract():
        ks = si.kspace(classify=lambda r: 'exc'); S['k'] = ks
        img = ks[-N:]; bad = []
        for j, k in enumerate(img):
            if np.abs(k[:, 1] - (j - N // 2) * DK).max() > 0.05: bad.append('echo %d: ky deviates by %.3f' % (j, np.abs(k[:, 1] - (j - N // 2) * DK).max()))
            if np.abs(k[:, 2]).max() > 0.05: bad.append('echo %d: kz up to %.3f' % (j, np.abs(k[:, 2]).max()))
            kx = np.sort(k[:, 0]); lo, hi = -(N // 2) * DK, (N // 2 - 1) * DK
            if kx[0] > lo + 1e-6 or kx[-1] < hi - 1e-6: bad.append('echo %d: kx coverage [%.1f, %.1f]' % (j, kx[0], kx[-1]))
            inside = kx[(kx >= lo - DK) & (kx <= hi + DK)]
            if inside.size < 2 or np.diff(inside).max() > DK * 1.0001: bad.append('echo %d: kx gap %.2f' % (j, np.diff(inside).max() if inside.size > 1 else np.inf))
        return not bad, {'violations': bad[:6], 'n_violations': len(bad)}
    C.guard('sampling_contract', contract)

    def timing():
        img = S['k'][-N:]; tim = [a['times'] for a in si.adcs[-N:]]
        cr = [crossing_time(k, t) for k, t in zip(img, tim)]
        if any(c is None for c in cr):
            return False, 'an imaging echo never crosses kx = 0'
        cr = np.array(cr); d = np.diff(cr)
        te = cr[N // 2] - si.rfs[0]['t_center']
        S['te'] = te; S['esp'] = float(np.median(d))
        ok = abs(te - task['effective_echo_time_s']) <= 10e-6 and np.abs(d - d.mean()).max() <= 1e-6 and d.max() <= task['echo_spacing_max_s'] + 1e-9
        return ok, {'TE_ms': te * 1e3, 'ESP_ms': [float(d.min() * 1e3), float(d.max() * 1e3)]}
    C.guard('te_and_echo_spacing', timing)

    def replay():
        d1, d2 = HPAR['hidden_delays_s']
        sigs, dt = V.koma_replay(src / 'sequence.seq', [expand(pub), expand(hid), expand(hid), expand(hid)], ev / 'replay', timeout=1500,
                                 adc_shifts=[0.0, 0.0, -d1, -d2])
        S['rep_pub'], S['rep_hid0'], S['rep_hid1'], S['rep_hid2'] = sigs
        return True, {'koma_seconds': round(dt, 1)}
    if si is not None and len(si.adcs) >= N and len(set(a['n'] for a in si.adcs)) == 1:
        C.guard('bloch_replay', replay)
    else:
        C.add('bloch_replay', False, 'skipped: ADC layout differs from the contract')

    def simmatch():
        z = V.load_npz(src / 'simulation.npz'); raw = np.asarray(z['raw_signal'], complex).reshape(-1); rep = S['rep_pub']
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
        na = len(si.adcs); ns = si.adcs[0]['n']
        refimg = ref_recon(S['rep_hid0'].reshape(na, ns)[-N:], S['k'][-N:], FOV)
        out = {'reference_background_level': round(ghost_level(refimg, hid['labels']), 4)}; ok_all = True; imgs = {}
        z0 = V.load_npz(src / 'simulation.npz')
        for tag, key in (('delta_0', 'rep_hid0'), ('delay_a', 'rep_hid1'), ('delay_b', 'rep_hid2')):
            z = dict(z0); z['raw_signal'] = S[key].reshape(np.asarray(z0['raw_signal']).shape); z['phantom_sha256'] = np.array(V.sha256(HID))
            hp = ev / ('hidden_%s.npz' % tag); np.savez(hp, **z)
            ok, o, rc, err = V.run_entry(python, src / 'reconstruct.py', hp, ev / ('hidden_run_' + tag), 'simulation.npz', 'image.npz')
            if not ok:
                return False, {tag: {'returncode': rc, 'stderr': err[-400:]}}
            im = np.asarray(V.load_npz(o)['image'])
            if im.shape != (N, N):
                return False, {tag: 'image shape %s' % (im.shape,)}
            imgs[tag] = im
        acc = nrmse(imgs['delta_0'], refimg); out['own_delta0_vs_reference_nrmse'] = round(acc, 4); ok_all = acc <= ACC_MAX
        for tag in ('delay_a', 'delay_b'):
            gl = ghost_level(imgs[tag], hid['labels']); e = nrmse(imgs[tag], imgs['delta_0'])
            out[tag] = {'background_level': round(gl, 4), 'nrmse_vs_own_delta0': round(e, 4)}
            ok_all = ok_all and gl <= GHOST_MAX and e <= CONSIST_MAX
        return ok_all, out
    if 'rep_hid0' in S and 'k' in S:
        C.guard('hidden_delayed_rerun_reconstruct', hidden)
    else:
        C.add('hidden_delayed_rerun_reconstruct', False, 'no replay')

    def pubimg():
        im = np.asarray(V.load_npz(src / 'image.npz')['image'])
        na = len(si.adcs); ns = si.adcs[0]['n']
        refimg = ref_recon(S['rep_pub'].reshape(na, ns)[-N:], S['k'][-N:], FOV)
        e = nrmse(im, refimg)
        lab = pub['labels']; a = np.abs(im); r1 = np.median(a[V.label_interior(lab, 1)])
        ratios = {str(k): float(np.median(a[V.label_interior(lab, k)]) / r1) for k in range(2, 7)}
        rep = V.load_json(src / 'report.json').get('signal_ratio_by_label', {})
        diff = max(abs(float(rep.get(k, np.nan)) - v) for k, v in ratios.items())
        return (e <= ACC_MAX and diff <= 0.01), {'nrmse_vs_reference': round(e, 4), 'max_report_ratio_difference': diff}
    if 'rep_pub' in S and 'k' in S:
        C.guard('public_image_and_report_ratios', pubimg)
    else:
        C.add('public_image_and_report_ratios', False, 'no replay')

    def report():
        r = V.load_json(src / 'report.json')
        need = ['scope', 'bloch_simulation_performed', 'simulator', 'scanner_ready', 'realized_effective_echo_time_ms', 'realized_echo_spacing_ms',
                'readout_design', 'ghost_correction', 'signal_ratio_by_label', 'software', 'validation_summary', 'limitations']
        miss = [k for k in need if k not in r]
        ok = not miss and r.get('bloch_simulation_performed') is True and r.get('scanner_ready') is False and isinstance(r.get('limitations'), list) and len(r['limitations']) > 0
        if ok and S.get('te'):
            ok = abs(float(r['realized_effective_echo_time_ms']) - S['te'] * 1e3) <= 0.01 and abs(float(r['realized_echo_spacing_ms']) - S['esp'] * 1e3) <= 0.01
        return ok, {'missing': miss}
    C.guard('report_fields', report)
    return C.result(task='heldout-v8-epinav-r4', deliverable_location=where)


if __name__ == '__main__':
    print(json.dumps(grade(sys.argv[1], sys.argv[2], Path(sys.executable)), indent=1, default=str))

