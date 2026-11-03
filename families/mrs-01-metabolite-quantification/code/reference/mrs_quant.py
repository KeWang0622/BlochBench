#!/usr/bin/env python3
"""Water-referenced single-voxel MRS quantification from multi-coil raw transients (reference solution, heldout-v7-mrsquant).

Usage: python mrs_quant.py --input-dir <dir with metab.npz water.npz params.json> --output conc.json
"""
import argparse, json
from pathlib import Path
import numpy as np

COIL_COMBINE = 'water_weighted'   # 'water_weighted' | 'plain_sum'
ECC = True
ALIGN = True
RELAXATION = True
PARTIAL_VOLUME = True
WATER_CONTENT = True
PROTONS = {'NAA': 3, 'Cr': 3, 'Cho': 9}
FIT_DOMAIN = 'frequency'


def lor_atoms(freqs, lw, t):
    return np.exp(np.outer(2j * np.pi * np.asarray(freqs), t) - np.pi * lw * t)


def varpro_fit(fid, t, freqs, extra_baseline, ppm_axis, sel, f0, dgrid, lgrid):
    """Fit sum of Lorentzians (shared shift and linewidth, complex amplitudes) in the frequency domain over sel."""
    n = len(t)
    Y = np.fft.fftshift(np.fft.fft(fid))[sel]
    best = (np.inf, None)
    fsel = ppm_axis[sel]
    for dlt in dgrid:
        for lw in lgrid:
            A = np.fft.fftshift(np.fft.fft(lor_atoms(np.asarray(freqs) + dlt, lw, t), axis=1), axes=1)[:, sel].T
            if extra_baseline:
                A = np.hstack([A, np.ones((len(fsel), 1)), (fsel - fsel.mean())[:, None]])
            c, *_ = np.linalg.lstsq(A, Y, rcond=None)
            r = np.linalg.norm(Y - A @ c)
            if r < best[0]:
                best = (r, c, dlt, lw)
    return best


def td_fit(fid, t, freqs, nfit=1024, water=True):
    """Time-domain VARPRO: metabolite singlets share shift and linewidth; residual water has its own."""
    from scipy.optimize import least_squares
    tt = t[:nfit]
    y = fid[:nfit]

    def design(p):
        A = lor_atoms(np.asarray(freqs) + p[0], p[1], tt).T
        if water:
            A = np.hstack([A, lor_atoms([p[2]], p[3], tt).T])
        return A

    def res(p):
        A = design(p)
        c, *_ = np.linalg.lstsq(A, y, rcond=None)
        r = y - A @ c
        return np.r_[r.real, r.imag]
    best = None
    for d0 in np.arange(-6, 6.1, 2.0):
        p0 = [d0, 5.0, 0.0, 10.0] if water else [d0, 5.0]
        lb = [-15, 0.5, -30, 0.5] if water else [-15, 0.5]
        ub = [15, 30, 30, 60] if water else [15, 30]
        s_ = least_squares(res, p0, bounds=(lb, ub))
        if best is None or s_.cost < best.cost:
            best = s_
    A = design(best.x)
    c, *_ = np.linalg.lstsq(A, y, rcond=None)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    d = Path(a.input_dir)
    p = json.loads((d / 'params.json').read_text())
    M = np.load(d / 'metab.npz')['fids'].astype(complex)   # [transient, coil, point]
    Wt = np.load(d / 'water.npz')['fids'].astype(complex)
    f0, dt, n = p['spectrometer_frequency_MHz'], p['dwell_time_s'], p['n_points']
    t = np.arange(n) * dt
    wavg = Wt.mean(0)                                       # [coil, point]
    if COIL_COMBINE == 'water_weighted':
        noise_var = np.var(M[:, :, -300:], axis=(0, 2))
        w = np.conj(wavg[:, 0]) / noise_var
        w = w / np.abs(np.sum(w * wavg[:, 0]))
    else:
        w = np.ones(M.shape[1])
    m = np.einsum('c,kcn->kn', w, M)
    wat = np.einsum('c,cn->n', w, wavg)
    if ECC:
        ph = np.exp(-1j * np.unwrap(np.angle(wat)))
        m = m * ph[None]
        wat = wat * ph
    if ALIGN:
        ref = m.mean(0)
        win = (t > 0.0) & (t < 0.2)
        for it in range(2):
            out = []
            for k in range(m.shape[0]):
                bestc, bp = -1, (0, 0)
                for df in np.arange(-10, 10.01, 0.1):
                    z = np.sum(np.conj(ref[win]) * m[k, win] * np.exp(-2j * np.pi * df * t[win]))
                    if abs(z) > bestc:
                        bestc, bp = abs(z), (df, np.angle(z))
                out.append(m[k] * np.exp(-1j * (2 * np.pi * bp[0] * t + bp[1])))
            m = np.array(out)
            ref = m.mean(0)
    fid = m.mean(0)
    ppm = 4.70 + np.fft.fftshift(np.fft.fftfreq(n, dt)) / f0
    names = ['NAA', 'Cr', 'Cho']
    peak_ppm = [2.008, 3.027, 3.185, 2.35, 3.522, 3.614, 3.75, 3.913]   # quantified peaks first, then nuisance singlets
    freqs = [(x - 4.70) * f0 for x in peak_ppm]
    sel = (ppm > 1.8) & (ppm < 3.4)
    if FIT_DOMAIN == 'frequency':
        r, c, dlt, lw = varpro_fit(fid, t, freqs, True, ppm, sel, f0, np.arange(-12, 12.01, 0.5), np.arange(1.0, 16.01, 0.5))
        _, c, dlt, lw = varpro_fit(fid, t, freqs, True, ppm, sel, f0, np.arange(dlt - 0.5, dlt + 0.51, 0.05), np.arange(max(lw - 0.5, 0.2), lw + 0.51, 0.05))
        amps = np.abs(c[:3])
        wsel = (ppm > 3.9) & (ppm < 5.5)
        _, cw, dw, lww = varpro_fit(wat, t, [0.0], True, ppm, wsel, f0, np.arange(-12, 12.01, 0.25), np.arange(1.0, 16.01, 0.25))
        aw = abs(cw[0])
    else:
        amps = np.abs(td_fit(fid, t, freqs))[:3]
        aw = abs(td_fit(wat, t, [0.0], water=False)[0])
    fr = p['tissue_volume_fractions']
    TE, TR = p['te_s'], p['tr_s']
    if not PARTIAL_VOLUME:
        s = fr['gm'] + fr['wm']
        fr = {'gm': fr['gm'] / s, 'wm': fr['wm'] / s, 'csf': 0.0}
    wsum = 0.0
    for comp in ('gm', 'wm', 'csf'):
        wp = p['water'][comp]
        R = np.exp(-TE / wp['T2']) * (1 - np.exp(-TR / wp['T1'])) if RELAXATION else 1.0
        wsum += fr[comp] * (wp['content'] if WATER_CONTENT else 1.0) * R
    out = {}
    for name, amp in zip(names, amps):
        mr = p['metabolite_relaxation_s'][name]
        Rm = np.exp(-TE / mr['T2']) * (1 - np.exp(-TR / mr['T1'])) if RELAXATION else 1.0
        out[name] = float(amp / aw * 2 * p['pure_water_concentration_mM'] * wsum / (PROTONS[name] * (fr['gm'] + fr['wm']) * Rm))
    out['units'] = 'mM (mmol per litre of non-CSF tissue volume)'
    Path(a.output).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()

