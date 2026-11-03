"""Sequence read-back helpers for grading (pypulseq). Times in s, gradients in Hz/m, B1 in uT."""
import math
import numpy as np
import pypulseq as pp

GAMMA = 42.576e6

def read(path):
    seq = pp.Sequence()
    seq.read(str(path))
    return seq

def events(seq):
    """Return dict with rf list [(t_center, flip_deg, peak_uT, t_start, t_end)], adc list [array of sample times],
    block start times, total duration."""
    t = 0.0; rfs = []; adcs = []
    for bi in seq.block_events:
        b = seq.get_block(bi)
        dur = seq.block_durations[bi]
        if b.rf is not None:
            rf = b.rf
            sig = np.asarray(rf.signal); tt = np.asarray(rf.t)
            if len(tt) > 2 and tt[0] > 0:      # raster-sampled shape (samples at (i+0.5)*raster)
                area = np.sum(sig) * np.median(np.diff(tt))
            else:                                # piecewise-linear time-shape (e.g. block pulse)
                area = np.sum((sig[1:] + sig[:-1]) / 2 * np.diff(tt)) if len(tt) > 1 else 0.0
            flip = abs(area) * 360.0
            tc = pp.calc_rf_center(rf)[0]
            rfs.append(dict(t_center=t + rf.delay + tc, flip_deg=flip, peak_uT=float(np.max(np.abs(sig))) / GAMMA * 1e6,
                            t_start=t + rf.delay, t_end=t + rf.delay + tt[-1], freq_offset=float(rf.freq_offset),
                            phase_offset=float(rf.phase_offset), block=bi))
        if b.adc is not None:
            a = b.adc
            adcs.append(dict(t=t + a.delay + (np.arange(a.num_samples) + 0.5) * a.dwell, dwell=a.dwell, block=bi,
                             phase_offset=float(a.phase_offset), freq_offset=float(a.freq_offset)))
        t += dur
    return dict(rf=rfs, adc=adcs, duration=t)

def gradient_waveforms(seq):
    """Piecewise-linear gradient waveforms [(t, g_Hz_per_m)] for x, y, z."""
    w = seq.waveforms_and_times()[0]
    out = []
    for ch in range(3):
        a = np.asarray(w[ch]) if ch < len(w) else np.zeros((2, 0))
        if a.size == 0:
            out.append((np.array([0.0]), np.array([0.0])))
        else:
            out.append((a[0].astype(float), a[1].astype(float)))
    return out

def hardware(seq):
    gw = gradient_waveforms(seq)
    gmax = 0.0; smax = 0.0
    for t, g in gw:
        if len(t) > 1:
            gmax = max(gmax, float(np.max(np.abs(g))))
            dt = np.diff(t); dg = np.diff(g)
            ok = dt > 1e-9
            if ok.any():
                smax = max(smax, float(np.max(np.abs(dg[ok] / dt[ok]))))
    ev = events(seq)
    b1 = max([r['peak_uT'] for r in ev['rf']] + [0.0])
    return dict(max_grad_mT_per_m=gmax / GAMMA * 1e3, max_slew_T_per_m_per_s=smax / GAMMA, max_b1_uT=b1)

def kspace_at(gw, t0, times):
    """Integrate gradient waveforms from t0 to each time in 'times' (cycles/m). Exact for piecewise-linear waveforms."""
    out = np.zeros((len(times), 3))
    for ch, (t, g) in enumerate(gw):
        if len(t) < 2:
            continue
        # cumulative integral at waveform points (trapezoid exact for piecewise-linear)
        cum = np.concatenate([[0.0], np.cumsum(np.diff(t) * (g[1:] + g[:-1]) / 2)])
        def F(tq):
            tq = np.asarray(tq, float)
            i = np.clip(np.searchsorted(t, tq, side='right') - 1, 0, len(t) - 2)
            dt = np.clip(tq - t[i], 0, None)
            slope = np.where(t[i + 1] > t[i], (g[i + 1] - g[i]) / np.maximum(t[i + 1] - t[i], 1e-12), 0.0)
            val = cum[i] + g[i] * dt + 0.5 * slope * dt ** 2
            val = np.where(tq < t[0], 0.0, val)
            val = np.where(tq > t[-1], cum[-1], val)
            return val
        out[:, ch] = F(times) - F(t0)
    return out

