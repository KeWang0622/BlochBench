#!/usr/bin/env python3
"""Grader for heldout-v8-tse (2D multi-shot turbo spin echo)."""
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
TEST = [(1.6, 0.28), (0.35, 0.045), (1.0, 0.14), (0.7, 0.07)]
GHOST_MAX = 0.05; RECON_TOL = 0.03; PHASE_TOL = 15.0; SHOT_TOL = 0.01
cls = lambda r: 'exc' if r['flip_deg'] < 120 else 'ref'


def expand(ph):
    x = np.asarray(ph['x_m']); y = np.asarray(ph['y_m']); z = np.asarray(ph['z_offsets_m']); rho = np.asarray(ph['density'])
    iy, ix = np.nonzero(rho > 0); nz = len(z); rep = lambda q: np.repeat(q, nz)
    return {'x': rep(x[ix]), 'y': rep(y[iy]), 'z': np.tile(z, len(ix)), 'rho': rep(rho[iy, ix] / nz),
            'T1': rep(ph['T1_s'][iy, ix]), 'T2': rep(ph['T2_s'][iy, ix]), 'dw': rep(2 * np.pi * ph['B0_Hz'][iy, ix])}


def grid_recon(raw, ks, dk, n):
    K = np.zeros((n, n), complex); cnt = np.zeros((n, n))
    for a in range(raw.shape[0]):
        iy = np.rint(ks[a][:, 1] / dk).astype(int) + n // 2; ix = np.rint(ks[a][:, 0] / dk).astype(int) + n // 2
        ok = (iy >= 0) & (iy < n) & (ix >= 0) & (ix < n)
        K[iy[ok], ix[ok]] += raw[a][ok]; cnt[iy[ok], ix[ok]] += 1
    return np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(K))) * n * n, cnt


def ghost_level(img, lab):
    far = lab == 0
    for _ in range(2):
        far = far & np.roll(far, 1, 0) & np.roll(far, -1, 0) & np.roll(far, 1, 1) & np.roll(far, -1, 1)
    return float(np.abs(img)[far].mean() / np.median(np.abs(img)[V.label_interior(lab, 1)]))


def grade(ws, ev, python=None):
    ws = Path(ws); ev = Path(ev); ev.mkdir(parents=True, exist_ok=True)
    C = V.Checks(); task = V.load_json(TASK); lim = task
    src, where = V.locate(ws)
    S = {}
    pub = V.load_npz(PUB); hid = V.load_npz(HID)
    DK = 1 / task['fov_m']
    N = int(task['matrix'][0]); H = N // 2; ETL = int(task['echo_train_length']); NSH = int(task['acquired_shots'])
    RFL = float(task['refocusing_flip_angle_deg']); ESPMAX = float(task['echo_spacing_max_s'])

    def present():
        miss = [f for f in REQ if not (src / f).exists()]
        py = [p.name for p in src.glob('*.py')]
        return (not miss and len(py) >= 3), {'location': where, 'missing': miss, 'python_files': py}
    C.guard('deliverables_present', present)

    def readback():
        si = V.SeqInfo(src / 'sequence.seq', lim); S['si'] = si
        ok = len(si.adcs) == N and all(a['n'] == N for a in si.adcs)
        return ok, {'n_rf': len(si.rfs), 'n_adc': len(si.adcs), 'duration_s': round(si.total, 4)}
    C.guard('sequence_readback', readback)
    si = S.get('si')
    C.guard('hardware_limits', lambda: V.hardware_check(si, lim))
    C.guard('raster_and_dead_times', lambda: V.timing_check(si, lim))

    def flips():
        bad = []
        exc = [r for r in si.rfs if cls(r) == 'exc']; ref = [r for r in si.rfs if cls(r) == 'ref']
        for r in exc:
            if abs(r['flip_deg'] / 90 - 1) > 0.02: bad.append('excitation %.1f deg' % r['flip_deg'])
        for r in ref:
            if abs(r['flip_deg'] / RFL - 1) > 0.02: bad.append('refocusing %.1f deg' % r['flip_deg'])
        for r in si.rfs:
            gz = abs(float(si.grad('z', r['t_center']))); gxy = max(abs(float(si.grad('x', r['t_center']))), abs(float(si.grad('y', r['t_center']))))
            if gz < 0.5e-3 * lim['gamma_Hz_per_T'] or gxy > 1e-6 * lim['gamma_Hz_per_T'] or abs(r['freq_Hz']) > 1e-6:
                bad.append('RF at %.4f s not slice-selective on z at z=0' % r['t_center'])
        S['exc'] = exc; S['ref'] = ref
        return not bad, {'violations': bad[:6], 'n_excitations': len(exc), 'n_refocusing': len(ref),
                         'excitation_flip_deg': float(np.median([r['flip_deg'] for r in exc])) if exc else None,
                         'refocusing_flip_deg': float(np.median([r['flip_deg'] for r in ref])) if ref else None}
    C.guard('flip_angles_and_slice_selection', flips)

    def contract():
        ks = si.kspace(classify=cls); S['k'] = ks
        rows = np.array([float(np.median(k[:, 1])) for k in ks])
        dev = 0.0; js = []
        for k in ks:
            j = int(np.rint(np.median(k[:, 1]) / DK)) + H; js.append(j)
            ex = np.stack([(np.arange(N) - H) * DK, np.full(N, (j - H) * DK), np.zeros(N)], 1)
            dev = max(dev, float(np.abs(k - ex).max()))
        complete = sorted(js) == list(range(N))
        return (dev <= task['sampling_contract']['tolerance_cycles_per_m'] and complete), {'max_k_deviation_cycles_per_m': dev, 'all_lines_once': complete}
    C.guard('sampling_contract', contract)

    def timing():
        ex_t = np.array([r['t_center'] for r in S['exc']]); rf_t = np.array([r['t_center'] for r in S['ref']])
        bad = []
        dtr = np.diff(ex_t)
        if len(dtr) == 0 or np.abs(dtr - task['repetition_time_s']).max() > 1e-6: bad.append('TR not constant')
        acq = sorted(set(int(np.searchsorted(ex_t, a['times'][0]) - 1) for a in si.adcs))
        esps = []
        for e in acq:
            tr_end = ex_t[e + 1] if e + 1 < len(ex_t) else np.inf
            rr = rf_t[(rf_t > ex_t[e]) & (rf_t < tr_end)]
            na = sum(1 for a in si.adcs if ex_t[e] < a['times'][0] < tr_end)
            if len(rr) != ETL or na != ETL: bad.append('shot %d: %d refocusing pulses, %d ADCs' % (e, len(rr), na)); continue
            d = np.diff(rr); esps += list(d)
            if np.abs(d - d.mean()).max() > 1e-6: bad.append('echo spacing not constant')
            if d.mean() > ESPMAX + 1e-9: bad.append('echo spacing too long')
        if len(acq) != NSH: bad.append('%d acquired shots' % len(acq))
        j0 = [n for n, k in enumerate(S['k']) if abs(np.median(k[:, 1])) < 0.5 * DK]
        teff = None
        if len(j0) == 1:
            a = si.adcs[j0[0]]; e = int(np.searchsorted(ex_t, a['times'][0]) - 1)
            teff = float(a['times'][H] - ex_t[e])
            if abs(teff - task['effective_echo_time_s']) > 20e-6: bad.append('TEeff %.3f ms' % (teff * 1e3))
        else:
            bad.append('ky=0 line not unique')
        S['teff'] = teff; S['esp'] = float(np.median(esps)) if esps else None
        return not bad, {'violations': bad[:6], 'TEeff_ms': teff * 1e3 if teff else None, 'ESP_ms': S['esp'] * 1e3 if S['esp'] else None, 'acquired_shots': len(acq)}
    C.guard('timing_te_esp_tr', timing)

    def replay():
        nz = len(pub['z_offsets_m']); z = pub['z_offsets_m']
        cols = [{'x': np.zeros(nz), 'y': np.zeros(nz), 'z': z, 'rho': np.full(nz, 1 / nz), 'T1': np.full(nz, t1), 'T2': np.full(nz, t2)} for t1, t2 in TEST]
        sigs, dt = V.koma_replay(src / 'sequence.seq', [expand(pub), expand(hid)] + cols, ev / 'replay', timeout=1500)
        S['rep_pub'], S['rep_hid'], S['rep_cols'] = sigs[0], sigs[1], sigs[2:]
        return True, {'koma_seconds': round(dt, 1)}
    if si is not None and len(si.adcs) == N and all(a['n'] == N for a in si.adcs):
        C.guard('bloch_replay', replay)
    else:
        C.add('bloch_replay', False, 'skipped: ADC layout differs from the contract')

    def train():
        ex_t = np.array([r['t_center'] for r in S['exc']])
        shot = np.array([int(np.searchsorted(ex_t, a['times'][0]) - 1) for a in si.adcs])
        worst = 0.0; spread = 0.0
        for s in S['rep_cols']:
            c = s.reshape(N, N)[:, H]
            firsts = []
            for e in sorted(set(shot)):
                cc = c[shot == e]
                m = np.angle(np.sum(cc / np.abs(cc)))
                worst = max(worst, float(np.degrees(np.abs(np.angle(cc * np.exp(-1j * m)))).max()))
                firsts.append(abs(cc[0]))
            firsts = np.array(firsts); spread = max(spread, float((firsts.max() - firsts.min()) / firsts.max()))
        S['train'] = (worst, spread)
        return worst <= PHASE_TOL, {'max_echo_phase_deviation_deg': round(worst, 2)}
    def shots():
        worst, spread = S['train']
        return spread <= SHOT_TOL, {'max_first_echo_spread_across_shots': round(spread, 4)}
    if 'rep_cols' in S:
        C.guard('echo_train_phase_coherence', train); C.guard('shot_steady_state', shots)
    else:
        C.add('echo_train_phase_coherence', False, 'no replay'); C.add('shot_steady_state', False, 'no replay')

    def quality():
        img, cnt = grid_recon(S['rep_hid'].reshape(N, N), S['k'], DK, N); S['ref_img_hid'] = img
        imgp, _ = grid_recon(S['rep_pub'].reshape(N, N), S['k'], DK, N)
        gh = ghost_level(img, hid['labels']); ghp = ghost_level(imgp, pub['labels'])
        return (gh <= GHOST_MAX and ghp <= GHOST_MAX), {'hidden_background_level': round(gh, 4), 'public_background_level': round(ghp, 4)}
    if 'rep_hid' in S and 'k' in S:
        C.guard('image_quality', quality)
    else:
        C.add('image_quality', False, 'no replay or trajectory')

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
        z = V.load_npz(src / 'simulation.npz'); z['raw_signal'] = S['rep_hid'].reshape(N, N); z['phantom_sha256'] = np.array(V.sha256(HID))
        hp = ev / 'hidden_archive.npz'; np.savez(hp, **z)
        ok, out, rc, err = V.run_entry(python, src / 'reconstruct.py', hp, ev / 'hidden_run', 'simulation.npz', 'image.npz')
        if not ok:
            return False, {'returncode': rc, 'stderr': err[-500:]}
        im = np.abs(np.asarray(V.load_npz(out)['image']))
        if im.shape != (N, N):
            return False, 'image shape %s' % (im.shape,)
        ref = np.abs(S['ref_img_hid'])
        sc = float(np.vdot(im.ravel(), ref.ravel()).real / max(np.vdot(im.ravel(), im.ravel()).real, 1e-30))
        nrmse = float(np.linalg.norm(sc * im - ref) / np.linalg.norm(ref))
        return nrmse <= RECON_TOL, {'nrmse_vs_reference_recon': round(nrmse, 5)}
    if 'ref_img_hid' in S:
        C.guard('hidden_rerun_reconstruct', hidden)
    else:
        C.add('hidden_rerun_reconstruct', False, 'no replay')

    def pubimg():
        im = np.abs(np.asarray(V.load_npz(src / 'image.npz')['image']))
        lab = pub['labels']; r1 = np.median(im[V.label_interior(lab, 1)])
        ratios = {str(k): float(np.median(im[V.label_interior(lab, k)]) / r1) for k in np.unique(lab) if k > 1}
        rep = V.load_json(src / 'report.json').get('signal_ratio_by_label', {})
        diff = max(abs(float(rep.get(k, np.nan)) - v) for k, v in ratios.items())
        return diff <= 0.01, {'ratios_from_image': {k: round(v, 4) for k, v in ratios.items()}, 'max_report_difference': diff}
    C.guard('public_image_and_report_ratios', pubimg)

    def report():
        r = V.load_json(src / 'report.json')
        need = ['scope', 'bloch_simulation_performed', 'simulator', 'scanner_ready', 'realized_effective_echo_time_ms', 'realized_echo_spacing_ms',
                'realized_flip_angles_deg', 'echo_ordering', 'echo_train_design', 'steady_state_preparation', 'signal_ratio_by_label', 'software', 'validation_summary', 'limitations']
        miss = [k for k in need if k not in r]
        ok = not miss and r.get('bloch_simulation_performed') is True and r.get('scanner_ready') is False and isinstance(r.get('limitations'), list) and len(r['limitations']) > 0
        if ok and S.get('teff'):
            ok = abs(float(r['realized_effective_echo_time_ms']) - S['teff'] * 1e3) <= 0.02 and abs(float(r['realized_echo_spacing_ms']) - S['esp'] * 1e3) <= 0.02
        return ok, {'missing': miss}
    C.guard('report_fields', report)
    return C.result(task='heldout-v8-tse-r4', deliverable_location=where)


if __name__ == '__main__':
    print(json.dumps(grade(sys.argv[1], sys.argv[2], Path(sys.executable)), indent=1, default=str))

