#!/usr/bin/env python3
"""Reference reconstruct.py: field map from the dual-echo scan, then off-resonance-corrected least-squares
reconstruction with an explicit spiral encoding model exp(-2pi i (k.r + df*t)), t from the excitation centre.
Usage: python reconstruct.py --input simulation.npz --fieldmap fieldmap_scan.npz --output image.npz"""
import argparse, hashlib
import numpy as np

N = 40; FOV = 0.216
VARIANT = 'ref'

def estimate_field(fm):
    im = fm['images']; te = np.asarray(fm['echo_times_s'], float)
    dte = te[1] - te[0]
    if VARIANT == 'tems':
        dte = dte * 1e3
    f = -np.angle(im[1] * np.conj(im[0])) / (2 * np.pi * dte)
    if VARIANT == 'sign':
        f = -f
    mag = np.abs(im[0]); mask = mag > 0.25 * np.percentile(mag, 99)
    # fill voxels without signal with the nearest masked value (only matters for regularisation)
    from scipy import ndimage
    idx = ndimage.distance_transform_edt(~mask, return_distances=False, return_indices=True)
    f = f[tuple(idx)]
    if VARIANT == 'transpose':
        f = f.T
    return f, mask

def recon(raw, k, t, field, lam=1e-3, chunk=1500):
    idx = np.arange(N) - N // 2
    Y, X = np.meshgrid(idx * FOV / N, idx * FOV / N, indexing='ij')
    r = np.stack([X.ravel(), Y.ravel()], 1); fv = field.ravel()
    AhA = np.zeros((N * N, N * N), complex); Ahy = np.zeros(N * N, complex)
    for s in range(0, len(raw), chunk):
        E = np.exp(-2j * np.pi * (k[s:s + chunk] @ r.T + np.outer(t[s:s + chunk], fv)))
        AhA += E.conj().T @ E; Ahy += E.conj().T @ raw[s:s + chunk]
    reg = lam * np.trace(AhA).real / (N * N)
    x = np.linalg.solve(AhA + reg * np.eye(N * N), Ahy)
    return x.reshape(N, N)

def recon_tseg(raw, k, t, field, L=12, iters=40):
    import sigpy as sp
    coord = np.stack([k[:, 1], k[:, 0]], -1) * FOV
    F = sp.linop.NUFFT((N, N), coord, oversamp=2.0, width=6)
    tl = np.linspace(t.min(), t.max(), L)
    # temporal interpolator: least-squares weights b_l(t) for exp(-2pi i f t) on a field histogram (MFI style)
    fgrid = np.linspace(field.min() - 5, field.max() + 5, 200)
    Bm = np.exp(-2j * np.pi * np.outer(fgrid, tl))
    Ct = np.exp(-2j * np.pi * np.outer(fgrid, t))
    Wt = np.linalg.lstsq(Bm, Ct, rcond=None)[0]                       # [L, Ns]
    def fwd(x):
        return sum(Wt[l] * F(x * np.exp(-2j * np.pi * field * tl[l])) for l in range(L))
    def adj(y):
        return sum(np.exp(2j * np.pi * field * tl[l]) * F.H(np.conj(Wt[l]) * y) for l in range(L))
    x = np.zeros((N, N), complex); b = adj(raw); rr = b.copy(); p = rr.copy(); rs = np.vdot(rr, rr)
    lam = 1e-4 * np.abs(b).max()
    for _ in range(iters):
        Ap = adj(fwd(p)) + lam * p
        a = rs / np.vdot(p, Ap); x = x + a * p; rr = rr - a * Ap; rn = np.vdot(rr, rr)
        p = rr + rn / rs * p; rs = rn
    return x

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True); ap.add_argument('--fieldmap', required=True); ap.add_argument('--output', required=True)
    a = ap.parse_args()
    d = np.load(a.input); fm = np.load(a.fieldmap)
    raw = np.asarray(d['raw_signal']).reshape(-1); k = np.asarray(d['kxy_cycles_per_m']).reshape(-1, 2)
    t = np.asarray(d['adc_times_s']).reshape(-1) - float(d['excitation_time_s'])
    if VARIANT == 'te0':
        t = t - t[0]
    if VARIANT == 'swapk':
        k = k[:, ::-1]
    field, mask = estimate_field(fm)
    use = np.zeros_like(field) if VARIANT == 'none' else field
    img = recon_tseg(raw, k, t, use) if VARIANT == 'tseg' else recon(raw, k, t, use)
    np.savez(a.output, image=img, field_map_hz=field, input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest(),
             fieldmap_sha256=hashlib.sha256(open(a.fieldmap, 'rb').read()).hexdigest())
    print('reconstructed; field range', float(field[mask].min()), float(field[mask].max()))

if __name__ == '__main__':
    main()

