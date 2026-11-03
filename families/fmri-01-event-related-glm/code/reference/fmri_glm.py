#!/usr/bin/env python3
"""Event-related fMRI GLM with slice timing, dummy-scan handling, motion regressors, high-pass and AR(1) prewhitening
(reference solution, heldout-v7-fmriglm).

Usage: python fmri_glm.py --input-dir <dir with bold.npz events.json motion.txt acq.json> --output stats.npz
"""
import argparse, json
from pathlib import Path
import numpy as np
from scipy.stats import gamma, t as tdist, norm

SLICE_TIMING = True
SLICE_TIMING_MODE = 'model'
DROP_DUMMIES = True
DUMMY_SPIKES = False
DRIFT_BASIS = 'dct'
SHIFT_ONSETS = True
MOTION_REGRESSORS = True
HIGHPASS = True
PREWHITEN = True
AR_POOLED = False
TEMPORAL_DERIVATIVE = False


def event_response(dt=0.02):
    t = np.arange(0, 32, dt)
    h = gamma.pdf(t, 6) - gamma.pdf(t, 16) / 6.0
    g = np.convolve(h, np.ones(int(round(1 / dt))))[:len(t)] * dt
    return t, g / g.max()


def regressor(times, onsets, shift=0.0):
    t, g = event_response()
    r = np.zeros(len(times))
    for o in onsets:
        r += np.interp(times - o - shift, t, g, left=0.0, right=0.0)
    return r


def stc_interp(Y, st, tr):
    """Sinc (FFT phase-shift) interpolation of every slice to the acquisition time of slice time 0."""
    nv = Y.shape[0]
    x = np.arange(nv)
    out = np.empty_like(Y)
    for z in range(Y.shape[1]):
        y = Y[:, z].reshape(nv, -1)
        A = np.stack([np.ones(nv), x], 1)
        c = np.linalg.lstsq(A, y, rcond=None)[0]
        r = y - A @ c
        rp = np.concatenate([r, r[::-1]], 0)
        f = np.fft.rfftfreq(2 * nv, d=tr)
        R = np.fft.rfft(rp, axis=0) * np.exp(-2j * np.pi * f * st[z])[:, None]
        rs = np.fft.irfft(R, n=2 * nv, axis=0)[:nv]
        out[:, z] = (rs + A @ c).reshape(Y[:, z].shape)
    return out


def dct_basis(n, tr, cutoff=128.0):
    k = int(np.floor(2 * n * tr / cutoff))
    x = np.arange(n)
    return np.stack([np.cos(np.pi * (x + 0.5) * j / n) for j in range(1, k + 1)], 1) if k > 0 else np.zeros((n, 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    d = Path(a.input_dir)
    acq = json.loads((d / 'acq.json').read_text())
    ev = json.loads((d / 'events.json').read_text())
    Y = np.load(d / 'bold.npz')['data'].astype(np.float64)
    mot = np.loadtxt(d / 'motion.txt')
    TR, nd = acq['tr_s'], acq['n_dummy_volumes']
    st = np.array(acq['slice_times_s'])
    onsets = np.array(ev['onsets_s'], float)
    if DROP_DUMMIES:
        Y, mot = Y[nd:], mot[nd:]
        if SHIFT_ONSETS:
            onsets = onsets - nd * TR
    nv, nz, ny, nx = Y.shape
    mean = Y[nd:].mean(0) if not DROP_DUMMIES else Y.mean(0)
    mask = mean > 0.2 * np.percentile(mean, 98)
    psc = np.zeros((nz, ny, nx))
    zmap = np.zeros((nz, ny, nx))
    rho_map = np.zeros((nz, ny, nx))
    nuis = [np.ones((nv, 1))]
    if MOTION_REGRESSORS:
        m = mot - mot.mean(0)
        nuis.append(m / (m.std(0) + 1e-12))
    if HIGHPASS:
        if DRIFT_BASIS == 'dct':
            nuis.append(dct_basis(nv, TR))
        else:
            x = np.linspace(-1, 1, nv)
            nuis.append(np.stack([np.polynomial.legendre.Legendre.basis(k)(x) for k in range(1, 6)], 1))
    if DUMMY_SPIKES and not DROP_DUMMIES:
        sp = np.zeros((nv, nd))
        sp[np.arange(nd), np.arange(nd)] = 1
        nuis.append(sp)
    N = np.hstack(nuis)
    if SLICE_TIMING and SLICE_TIMING_MODE == 'interp':
        Y = stc_interp(Y, st, TR)
    for z in range(nz):
        times = np.arange(nv) * TR + (st[z] if (SLICE_TIMING and SLICE_TIMING_MODE == 'model') else 0.0)
        r = regressor(times, onsets)
        cols = [r[:, None]]
        if TEMPORAL_DERIVATIVE:
            rd = (regressor(times, onsets, -0.25) - regressor(times, onsets, 0.25)) / 0.5
            rd = rd - r * (rd @ r) / (r @ r)
            cols.append(rd[:, None])
        X = np.hstack(cols + [N])
        vox = np.where(mask[z].ravel())[0]
        y = Y[:, z].reshape(nv, -1)[:, vox]
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        res = y - X @ b
        if PREWHITEN:
            rho = np.sum(res[1:] * res[:-1], 0) / np.sum(res * res, 0)
            p = X.shape[1]
            rho = np.clip(rho * (1 + p / nv) + 1.0 / nv, -0.2, 0.9)  # small-sample bias adjustment
            if AR_POOLED:
                rho = np.full_like(rho, np.median(rho))
            beta = np.zeros((X.shape[1], len(vox)))
            se = np.zeros(len(vox))
            for j in range(len(vox)):
                rr = rho[j]
                s = np.sqrt(1 - rr ** 2)
                Xw = np.vstack([X[:1] * s, X[1:] - rr * X[:-1]])
                yw = np.r_[y[0, j] * s, y[1:, j] - rr * y[:-1, j]]
                bw, _, _, _ = np.linalg.lstsq(Xw, yw, rcond=None)
                e = yw - Xw @ bw
                dof = nv - Xw.shape[1]
                cov = np.linalg.pinv(Xw.T @ Xw) * (e @ e) / dof
                beta[:, j] = bw
                se[j] = np.sqrt(cov[0, 0])
            dof = nv - X.shape[1]
        else:
            rho = np.zeros(len(vox))
            beta = b
            dof = nv - X.shape[1]
            cov = np.linalg.pinv(X.T @ X)
            se = np.sqrt(cov[0, 0] * np.sum(res * res, 0) / dof)
        icol = 1 + (1 if TEMPORAL_DERIVATIVE else 0)
        amp = beta[0]
        if TEMPORAL_DERIVATIVE:
            amp = np.sign(beta[0]) * np.sqrt(beta[0] ** 2 + beta[1] ** 2)
        base = beta[icol]
        tval = beta[0] / se
        zz = norm.isf(tdist.sf(tval, dof))
        out = np.zeros(ny * nx); out[vox] = 100 * amp / base; psc[z] = out.reshape(ny, nx)
        out = np.zeros(ny * nx); out[vox] = zz; zmap[z] = out.reshape(ny, nx)
        out = np.zeros(ny * nx); out[vox] = rho; rho_map[z] = out.reshape(ny, nx)
    np.savez_compressed(a.output, psc=psc.astype(np.float32), z=zmap.astype(np.float32), ar1=rho_map.astype(np.float32))


if __name__ == '__main__':
    main()

