#!/usr/bin/env python3
"""Raw multi-coil multi-echo k-space -> PDFF and R2* maps (reference solution, heldout-v7-dixonraw).

Usage: python dixon_pdff.py --input-dir <dir with kspace.npz noise.npz b1.npz params.json> --output pdff.npz
"""
import argparse, json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter

REVERSE_EVEN_ECHOES = True
OVERSAMPLING = 'image_crop'      # 'image_crop' | 'kspace_crop'
PREWHITEN = True
COMBINE = 'echo1_reference'       # 'echo1_reference' | 'refcoil_smooth' | 'rss'
FAT_MODEL = 'multipeak'           # 'multipeak' | 'single'
CS_SIGN = 1.0
T1_CORRECTION = True
USE_B1 = True
SMOOTH_SIGMA = 4.0


def icfft2(k):
    return np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k, axes=(-2, -1))), axes=(-2, -1))


def icfft1(k, axis):
    return np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(k, axes=axis), axis=axis), axes=axis)


def spgr(t1, a, tr):
    e1 = np.exp(-tr / t1)
    return np.sin(a) * (1 - e1) / (1 - np.cos(a) * e1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    d = Path(a.input_dir)
    p = json.loads((d / 'params.json').read_text())
    K = np.load(d / 'kspace.npz')['kspace'].astype(complex)      # [echo, coil, ky, kx]
    noise = np.load(d / 'noise.npz')['noise'].astype(complex)
    b1 = np.load(d / 'b1.npz')['b1_rel'].astype(float)
    ne, nc, ny, nxo = K.shape
    N = p['matrix'][1]
    if REVERSE_EVEN_ECHOES:
        K[1::2] = K[1::2, :, :, ::-1]
    if PREWHITEN:
        psi = noise @ noise.conj().T / noise.shape[1]
        Linv = np.linalg.inv(np.linalg.cholesky(psi))
        K = np.einsum('ij,ejyx->eiyx', Linv, K)
    if OVERSAMPLING == 'image_crop':
        img = icfft2(K)[..., nxo // 2 - N // 2: nxo // 2 + N // 2]
    else:
        img = icfft2(K[..., nxo // 2 - N // 2: nxo // 2 + N // 2])
    rss1 = np.sqrt((np.abs(img[0]) ** 2).sum(0)) + 1e-12
    if COMBINE == 'echo1_reference':
        w = np.conj(img[0]) / rss1                      # echo-1 coil images as sensitivities: phase of echo 1 is the common reference
        comb = np.einsum('cyx,ecyx->eyx', w, img)
    elif COMBINE == 'refcoil_smooth':
        ref = img[0, 0] / (np.abs(img[0, 0]) + 1e-9)
        rel = img[0] * np.conj(ref)[None]
        sm = np.array([gaussian_filter(r.real, 3) + 1j * gaussian_filter(r.imag, 3) for r in rel])
        s = sm / (np.sqrt((np.abs(sm) ** 2).sum(0)) + 1e-12)
        comb = np.einsum('cyx,ecyx->eyx', np.conj(s), img)
    else:
        comb = np.sqrt((np.abs(img) ** 2).sum(1)).astype(complex)
    te = np.array(p['echo_times_ms']) * 1e-3
    f0 = p['gamma_MHz_per_T'] * p['field_strength_T']
    if FAT_MODEL == 'multipeak':
        fhz = CS_SIGN * (np.array(p['fat_spectrum']['ppm']) - p['water_ppm']) * f0
        amp = np.array(p['fat_spectrum']['relative_amplitude'])
    else:
        fhz = CS_SIGN * np.array([(1.30 - p['water_ppm']) * f0])
        amp = np.array([1.0])
    cfat = (amp[None, :] * np.exp(2j * np.pi * te[:, None] * fhz[None, :])).sum(1)
    mag = np.abs(comb).sum(0)
    mask = mag > 0.15 * np.percentile(mag, 99)
    Y = comb.reshape(ne, -1)[:, mask.ravel()]
    nv = Y.shape[1]
    span = 1.0 / (te[1] - te[0])
    psis = np.arange(-span / 2, span / 2, 4.0)
    r2s = np.arange(0, 301, 10.0)
    best_r = np.full((len(psis), nv), np.inf)
    best_r2 = np.zeros((len(psis), nv))
    yn = (np.abs(Y) ** 2).sum(0)
    for i, ps in enumerate(psis):
        for r2 in r2s:
            dec = np.exp(2j * np.pi * ps * te - r2 * te)
            A = np.stack([dec, dec * cfat], 1)
            Q, _ = np.linalg.qr(A)
            res = yn - (np.abs(Q.conj().T @ Y) ** 2).sum(0)
            upd = res < best_r[i]
            best_r[i] = np.where(upd, res, best_r[i])
            best_r2[i] = np.where(upd, r2, best_r2[i])
    # spatially regularised choice of the field map: smooth the cost volume, take the smooth argmin, then refine locally
    cost = np.full((len(psis),) + mask.shape, np.nan)
    cost[:, mask] = best_r / (yn[None] + 1e-12)
    cfill = np.where(np.isfinite(cost), cost, 0.0)
    wts = gaussian_filter(mask.astype(float), SMOOTH_SIGMA)
    sm = np.array([gaussian_filter(c_, SMOOTH_SIGMA) for c_ in cfill]) / np.maximum(wts, 1e-6)[None]
    coarse = psis[np.argmin(sm, 0)]
    coarse = gaussian_filter(coarse, SMOOTH_SIGMA)
    near = np.abs(psis[:, None] - coarse[mask][None, :]) <= 80
    rr = np.where(near, best_r, np.inf)
    ib = np.argmin(rr, 0)
    psi0 = psis[ib]
    # local refinement on a fine grid
    fine_p = np.arange(-6, 6.01, 0.5)
    fine_r = np.arange(-12, 12.01, 1.0)
    bestv = np.full(nv, np.inf); bp = psi0.copy(); br = best_r2[ib, np.arange(nv)].copy(); bc = np.zeros((2, nv), complex)
    for dp in fine_p:
        for dr in fine_r:
            ps = psi0 + dp
            r2 = np.clip(best_r2[ib, np.arange(nv)] + dr, 0, None)
            dec = np.exp(2j * np.pi * ps[None, :] * te[:, None] - r2[None, :] * te[:, None])
            A = np.stack([dec, dec * cfat[:, None]], 1)       # [echo, 2, vox]
            AhA = np.einsum('eiv,ejv->ijv', A.conj(), A)
            Ahy = np.einsum('eiv,ev->iv', A.conj(), Y)
            det = AhA[0, 0] * AhA[1, 1] - AhA[0, 1] * AhA[1, 0]
            c0 = (AhA[1, 1] * Ahy[0] - AhA[0, 1] * Ahy[1]) / det
            c1 = (-AhA[1, 0] * Ahy[0] + AhA[0, 0] * Ahy[1]) / det
            r = ((np.abs(Y - A[:, 0] * c0 - A[:, 1] * c1)) ** 2).sum(0)
            upd = r < bestv
            bestv = np.where(upd, r, bestv); bp = np.where(upd, ps, bp); br = np.where(upd, r2, br)
            bc[0] = np.where(upd, c0, bc[0]); bc[1] = np.where(upd, c1, bc[1])
    wv, fv = np.abs(bc[0]), np.abs(bc[1])
    if T1_CORRECTION:
        al = np.deg2rad(p['flip_angle_deg']) * (b1[mask] if USE_B1 else 1.0)
        wv = wv / spgr(p['t1_water_ms'], al, p['tr_ms'])
        fv = fv / spgr(p['t1_fat_ms'], al, p['tr_ms'])
    pdff = np.zeros(mask.shape); r2m = np.zeros(mask.shape); fm = np.zeros(mask.shape)
    pdff[mask] = 100 * fv / np.maximum(wv + fv, 1e-12)
    r2m[mask] = br
    fm[mask] = bp
    np.savez_compressed(a.output, pdff_percent=pdff.astype(np.float32), r2s_per_s=r2m.astype(np.float32), fieldmap_hz=fm.astype(np.float32))


if __name__ == '__main__':
    main()

