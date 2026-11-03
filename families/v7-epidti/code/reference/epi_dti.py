#!/usr/bin/env python3
"""Raw EPI diffusion k-space -> ghost- and distortion-corrected DTI with gradient-nonlinearity correction
(reference solution, heldout-v7-epidti).

Usage: python epi_dti.py --input-dir <dir with epi_raw.npz fieldmap.npz grad_nonlin.npz bvals.txt bvecs.txt params.json> --output dti.npz
"""
import argparse, json
from pathlib import Path
import numpy as np

REVERSE_NEGATIVE_READOUTS = True
GHOST_CORRECTION = True
GHOST_LINEAR = True
GHOST_POOL = False
PE_SIGN_OVERRIDE = None
FIT = 'wls'
DISTORTION_CORRECTION = True
DISTORTION_SIGN = 1.0
JACOBIAN = True
GNL_CORRECTION = 'full'      # 'full' | 'none' | 'bscale_only'
UNWARP = 'pixel_shift'       # 'pixel_shift' | 'model'


def cifft(x, axis):
    return np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(x, axes=axis), axis=axis), axes=axis)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    d = Path(a.input_dir)
    p = json.loads((d / 'params.json').read_text())
    z = np.load(d / 'epi_raw.npz')
    raw, pol, kyl = z['raw'].astype(complex), z['readout_polarity'], z['ky_index_of_imaging_line']
    fmap = np.load(d / 'fieldmap.npz')['fieldmap_hz'].astype(float)
    L = np.load(d / 'grad_nonlin.npz')['L'].astype(float)
    bvals = np.loadtxt(d / 'bvals.txt').ravel()
    bvecs = np.loadtxt(d / 'bvecs.txt').reshape(3, -1).T
    nv, nz, nr, nx = raw.shape
    ny = p['matrix'][0]
    nn = p['n_navigators']
    esp = p['echo_spacing_ms'] * 1e-3
    pe = p['pe_direction_sign'] if PE_SIGN_OVERRIDE is None else PE_SIGN_OVERRIDE
    k = raw.copy()
    if REVERSE_NEGATIVE_READOUTS:
        k[:, :, pol < 0, :] = k[:, :, pol < 0, ::-1]
    h = cifft(k, axis=3)                       # hybrid space: [vol, slice, readout, x]
    xs = np.arange(nx) - nx // 2
    if GHOST_CORRECTION:
        n0, n1, n2 = h[:, :, 0], h[:, :, 1], h[:, :, 2]
        pr = n1 * np.conj(0.5 * (n0 + n2))       # phase of negative-polarity readouts relative to positive ones
        if GHOST_POOL:
            pr = np.repeat(pr.sum(0, keepdims=True), nv, 0)
        for v in range(nv):
            for s in range(nz):
                w = np.abs(pr[v, s])
                ph = np.unwrap(np.angle(pr[v, s]))
                A = np.stack([np.ones(nx), xs], 1) * np.sqrt(w)[:, None]
                c, *_ = np.linalg.lstsq(A, ph * np.sqrt(w), rcond=None)
                if not GHOST_LINEAR:
                    c = [np.angle(np.sum(pr[v, s])), 0.0]
                corr = np.exp(-1j * (c[0] + c[1] * xs))
                neg = np.where(pol < 0)[0]
                h[v, s, neg] *= corr[None, :]
    lines = h[:, :, nn:]
    hk = np.zeros((nv, nz, ny, nx), complex)
    hk[:, :, kyl + ny // 2] = lines
    img = cifft(hk, axis=2)                    # distorted complex images [vol, slice, y, x]
    mag = np.abs(img)
    if DISTORTION_CORRECTION and UNWARP == 'model':
        tl = np.arange(len(kyl)) * esp           # acquisition time of each imaging line (common offsets do not matter)
        yv = np.arange(ny) - ny // 2
        out = np.zeros_like(mag)
        for s in range(nz):
            for x in range(nx):
                E = np.exp(-2j * np.pi * np.outer(kyl, yv) / ny + 2j * np.pi * np.outer(tl, fmap[s, :, x]))
                rhs = lines[:, s, :, x].T * ny     # [line, vol]
                EhE = E.conj().T @ E
                m = np.linalg.solve(EhE + 0.02 * ny * np.eye(ny), E.conj().T @ rhs)   # Tikhonov-regularised model inversion
                out[:, s, :, x] = np.abs(m.T)
        mag = out
    elif DISTORTION_CORRECTION:
        yy = np.arange(ny, dtype=float)
        out = np.zeros_like(mag)
        for s in range(nz):
            shift = -DISTORTION_SIGN * pe * fmap[s] * ny * esp       # displacement (pixels along y) of each true location
            for x in range(nx):
                ypos = yy + shift[:, x]
                jac = np.gradient(ypos) if JACOBIAN else np.ones(ny)
                for v in range(nv):
                    out[v, s, :, x] = np.interp(ypos, yy, mag[v, s, :, x], left=0, right=0) * jac
        mag = out
    b0 = mag[bvals < 50].mean(0)
    mask = b0 > 0.15 * np.percentile(b0, 99)
    S = np.maximum(mag, 1e-3)
    nvox = mask.sum()
    Y = np.log(S[:, mask])                       # [vol, vox]
    Lm = L[mask]                                 # [vox,3,3]
    if GNL_CORRECTION == 'full':
        ge = bvecs[None, :, :] + np.einsum('nij,vj->nvi', Lm, bvecs)            # [vox, vol, 3]
    elif GNL_CORRECTION == 'bscale_only':
        ge0 = bvecs[None, :, :] + np.einsum('nij,vj->nvi', Lm, bvecs)
        ge = bvecs[None, :, :] * np.linalg.norm(ge0, axis=2, keepdims=True)
    else:
        ge = np.repeat(bvecs[None], nvox, 0)
    bx, by, bz = ge[..., 0], ge[..., 1], ge[..., 2]
    B = -bvals[None, :, None] * np.stack([bx * bx, by * by, bz * bz, 2 * bx * by, 2 * bx * bz, 2 * by * bz], 2)   # [vox, vol, 6]
    X = np.concatenate([np.ones((nvox, nv, 1)), B], 2)
    W = S[:, mask].T ** 2 if FIT == 'wls' else np.ones((nvox, nv))             # WLS weights
    XtW = np.einsum('nvi,nv->niv', X, W)
    beta = np.linalg.solve(np.einsum('niv,nvj->nij', XtW, X), np.einsum('niv,vn->ni', XtW, Y)[..., None])[..., 0]
    dxx, dyy, dzz, dxy, dxz, dyz = beta[:, 1:].T
    Dt = np.stack([np.stack([dxx, dxy, dxz], -1), np.stack([dxy, dyy, dyz], -1), np.stack([dxz, dyz, dzz], -1)], -2)
    ev, evec = np.linalg.eigh(Dt)
    md = ev.mean(1)
    fa = np.sqrt(1.5 * ((ev - md[:, None]) ** 2).sum(1) / np.maximum((ev ** 2).sum(1), 1e-30))
    FA = np.zeros(mask.shape); MD = np.zeros(mask.shape); V1 = np.zeros(mask.shape + (3,))
    FA[mask], MD[mask], V1[mask] = fa, md, evec[:, :, 2]
    np.savez_compressed(a.output, fa=FA.astype(np.float32), md_mm2_per_s=MD.astype(np.float32), v1=V1.astype(np.float32), mean_b0=b0.astype(np.float32))


if __name__ == '__main__':
    main()

