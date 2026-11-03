"""Sequence analysis for heldout-v5-safecpmg: timing, RF, gradients, safety metrics (grader side)."""
import numpy as np, pypulseq as pp
GAMMA = 42.576e6
LIM = {'max_grad_mT_per_m': 38.0, 'max_slew_T_per_m_per_s': 150.0, 'b1_peak_uT': 12.0, 'b1_rms_uT': 0.55,
       'pns_fraction': 0.80, 'gz_rms_mT_per_m': 7.0, 'tr_s': 1.0, 'esp_s': 0.012, 'n_echo_min': 26, 'n_echo_max': 40,
       'crusher_min': 800.0, 'crusher_max': 2000.0, 'pns_rheobase_slew': 52.0, 'pns_chronaxie_s': 0.34e-3}

def _gpoints(g, t0):
    if g is None:
        return []
    if g.type == 'trap':
        d = t0 + g.delay
        return [(d, 0.0), (d + g.rise_time, g.amplitude), (d + g.rise_time + g.flat_time, g.amplitude), (d + g.rise_time + g.flat_time + g.fall_time, 0.0)]
    d = t0 + g.delay
    pts = [(d + float(t), float(w)) for t, w in zip(g.tt, g.waveform)]
    first = float(getattr(g, 'first', pts[0][1] if pts else 0.0)); last = float(getattr(g, 'last', pts[-1][1] if pts else 0.0))
    dur = float(getattr(g, 'shape_dur', pts[-1][0] - d if pts else 0.0))
    return [(d, first)] + pts + [(d + dur, last)]

def analyze(path):
    seq = pp.Sequence(); seq.read(str(path))
    t0 = 0.0; rfs = []; adcs = []; gp = {'x': [], 'y': [], 'z': []}
    for bid in seq.block_events:
        b = seq.get_block(bid)
        if getattr(b, 'rf', None) is not None:
            rf = b.rf; sd = float(rf.shape_dur)
            n = max(int(round(sd / 1e-6)), 1); tt = (np.arange(n) + 0.5) * sd / n
            s = np.interp(tt, rf.t, np.real(rf.signal)) + 1j * np.interp(tt, rf.t, np.imag(rf.signal))
            dt = sd / n
            cen = float(getattr(rf, 'center', sd / 2) or sd / 2)
            rfs.append({'start': t0 + rf.delay, 'end': t0 + rf.delay + sd, 'center': t0 + rf.delay + cen,
                        'flip_deg': float(np.degrees(2 * np.pi * abs(np.sum(s) * dt))),
                        'phase_deg': float(np.degrees(np.angle(np.sum(s)) + rf.phase_offset)),
                        'energy_uT2s': float(np.sum(np.abs(s / GAMMA * 1e6) ** 2) * dt),
                        'peak_uT': float(np.abs(s).max() / GAMMA * 1e6), 'freq_offset': float(rf.freq_offset), 'dur': sd})
        if getattr(b, 'adc', None) is not None:
            a = b.adc; ns = int(a.num_samples)
            adcs.append({'start': t0 + a.delay, 'n': ns, 'dwell': float(a.dwell),
                         'mid_time': t0 + a.delay + (ns // 2 + 0.5) * a.dwell, 'end': t0 + a.delay + ns * a.dwell})
        for ax in 'xyz':
            gp[ax] += _gpoints(getattr(b, 'g' + ax, None), t0)
        t0 += float(b.block_duration)
    T = t0
    out = {'duration_s': T, 'rf': rfs, 'adc': adcs}
    dtf = 1e-6; tf = (np.arange(int(np.ceil(T / dtf))) + 0.5) * dtf
    wave = {}; maxg = 0.0; maxs = 0.0; pns = 0.0; pnsd = None
    for ax in 'xyz':
        pts = sorted(gp[ax], key=lambda p: p[0])
        if not pts:
            wave[ax] = np.zeros_like(tf); continue
        tp = np.array([p[0] for p in pts]); vp = np.array([p[1] for p in pts])
        wave[ax] = np.interp(tf, tp, vp, left=0.0, right=0.0)
        maxg = max(maxg, np.abs(vp).max() / GAMMA)
        dtp = np.diff(tp); dv = np.diff(vp)
        with np.errstate(divide='ignore', invalid='ignore'):
            sl = np.where(dtp > 1e-9, dv / np.maximum(dtp, 1e-12), np.where(np.abs(dv) > 1e-6, np.inf, 0.0))
        maxs = max(maxs, float(np.nanmax(np.abs(sl))) / GAMMA if len(sl) else 0.0)
        # ramps: maximal runs of segments with the same non-zero slope sign
        i = 0
        while i < len(sl):
            sg = np.sign(sl[i]) if abs(sl[i]) > 1e-3 * GAMMA else 0
            if sg == 0:
                i += 1; continue
            j = i; dG = 0.0; tau = 0.0
            while j < len(sl) and (np.sign(sl[j]) == sg and abs(sl[j]) > 1e-3 * GAMMA or (dtp[j] <= 1e-9 and abs(dv[j]) <= 1e-6)):
                dG += dv[j]; tau += dtp[j]; j += 1
            P = abs(dG) / GAMMA / (LIM['pns_rheobase_slew'] * (tau + LIM['pns_chronaxie_s']))
            if P > pns:
                pns = P; pnsd = {'axis': ax, 'dG_mT_per_m': abs(dG) / GAMMA * 1e3, 'ramp_s': tau, 'start_s': float(tp[i])}
            i = j
    out['max_grad_mT_per_m'] = maxg * 1e3; out['max_slew_T_per_m_per_s'] = maxs
    out['pns_max_fraction'] = pns; out['pns_worst_ramp'] = pnsd
    out['gz_rms_mT_per_m'] = float(np.sqrt(np.mean((wave['z'] / GAMMA) ** 2)) * 1e3)
    out['xy_max_abs_Hz_per_m'] = float(max(np.abs(wave['x']).max(), np.abs(wave['y']).max()))
    E = sum(r['energy_uT2s'] for r in rfs)
    out['b1_rms_uT'] = float(np.sqrt(E / T)); out['b1_peak_uT'] = max([r['peak_uT'] for r in rfs] or [0])
    cm = np.concatenate([[0.0], np.cumsum(wave['z']) * dtf])  # cycles/m at grid edges
    te = np.concatenate([[0.0], tf + dtf / 2])
    M = lambda t: float(np.interp(t, te, cm))
    out['_M'] = M; out['_wave'] = wave; out['_tf'] = tf
    # gradient during RF / ADC
    def gmax_in(a, b):
        m = (tf >= a) & (tf <= b)
        return float(max(np.abs(wave[ax][m]).max() if m.any() else 0.0 for ax in 'xyz'))
    out['grad_during_rf_Hz_per_m'] = max([gmax_in(r['start'], r['end']) for r in rfs] or [0])
    out['grad_during_adc_Hz_per_m'] = max([gmax_in(a['start'], a['end']) for a in adcs] or [0])
    # CPMG structure
    st = {}
    if len(rfs) >= 3:
        exc = rfs[0]; refs = rfs[1:]; te0 = exc['center']
        esp = refs[1]['center'] - refs[0]['center']
        st['esp_s'] = esp; st['n_echo'] = len(refs); st['exc_flip_deg'] = exc['flip_deg']
        st['ref_flip_deg'] = [r['flip_deg'] for r in refs]
        st['ref_timing_err_s'] = max(abs(r['center'] - te0 - (esp / 2 + k * esp)) for k, r in enumerate(refs))
        dph = [((r['phase_deg'] - exc['phase_deg'] + 180) % 360) - 180 for r in refs]
        st['cpmg_phase_err_deg'] = max(abs(abs(d) - 90) for d in dph)
        st['ref_phase_consistent'] = (max(dph) - min(dph)) < 2.0
        st['n_adc'] = len(adcs)
        echoes = [te0 + (k + 1) * esp for k in range(len(refs))]
        st['echo_times_s'] = [(k + 1) * esp for k in range(len(refs))]
        if len(adcs) == len(refs):
            st['adc_timing_err_s'] = max(abs(a['mid_time'] - e) - (a['dwell'] / 2 if a['n'] % 2 == 0 else 0) for a, e in zip(adcs, echoes))
        pre, post = [], []
        prev = te0
        for k, r in enumerate(refs):
            pre.append(M(r['center']) - M(prev)); post.append(M(echoes[k]) - M(r['center'])); prev = echoes[k]
        st['crusher_pre_cyc_per_m'] = pre; st['crusher_post_cyc_per_m'] = post
        st['freq_offsets'] = max(abs(r['freq_offset']) for r in rfs)
    out['cpmg'] = st
    return out

def public_summary(a):
    return {k: v for k, v in a.items() if not k.startswith('_') and k not in ('rf', 'adc')}

