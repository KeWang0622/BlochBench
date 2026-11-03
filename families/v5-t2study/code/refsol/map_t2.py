#!/usr/bin/env python3
"""Reference T2 mapping entrypoint: noise prewhitening, ESPIRiT sensitivities from the ACS block,
CG-SENSE per echo (sigpy), voxelwise mono-exponential magnitude fit (log-linear start + Gauss-Newton).
Usage: python map_t2.py --input scan.npz --output t2map.npz"""
import argparse, hashlib, os
import numpy as np

def recon_echoes(ksp, mask, noise, method='espirit'):
    import sigpy.mri as mr
    E, C, N, _ = ksp.shape
    psi = noise.conj().T @ noise / noise.shape[0]
    Lc = np.linalg.cholesky(psi)
    Wm = np.linalg.inv(Lc)
    kw = np.einsum('ij,ejyx->eiyx', Wm, ksp).astype(np.complex64)
    nacs = 0
    c = N // 2
    while c - nacs - 1 >= 0 and mask[c - nacs - 1] and mask[c + nacs]:
        nacs += 1
    calib = 2 * nacs
    if method == 'espirit':
        mps = mr.app.EspiritCalib(kw[0], calib_width=calib, thresh=0.02, kernel_width=6, crop=0.9, show_pbar=False).run()
    else:  # low-resolution ACS sensitivities normalised by their RSS
        k0 = np.zeros_like(kw[0])
        k0[:, c - nacs:c + nacs, c - nacs:c + nacs] = kw[0][:, c - nacs:c + nacs, c - nacs:c + nacs]
        win = np.outer(np.hanning(2 * nacs + 2)[1:-1], np.hanning(2 * nacs + 2)[1:-1])
        k0[:, c - nacs:c + nacs, c - nacs:c + nacs] *= win
        lo = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k0, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))
        rss = np.sqrt((np.abs(lo) ** 2).sum(0))
        mps = lo / np.maximum(rss, 1e-3 * rss.max())
        mps[:, rss < 0.05 * rss.max()] = 0
    wts = np.broadcast_to(mask[None, :, None], kw.shape[1:]).astype(np.float32)
    imgs = np.stack([mr.app.SenseRecon(kw[e], mps, lamda=1e-3, weights=wts, max_iter=60, show_pbar=False).run() for e in range(E)])
    return imgs, mps

def fit_t2(mag, te, mask):
    """mag [E,N,N]; returns t2 (ms), s0."""
    E = len(te)
    y = mag[:, mask].astype(float)              # [E,V]
    y = np.maximum(y, 1e-6 * y.max())
    A = np.stack([np.ones(E), -te], 1)
    w = y ** 2
    p = np.zeros((2, y.shape[1]))
    for v in range(y.shape[1]):
        Aw = A * w[:, v:v + 1] ** 0.5
        p[:, v] = np.linalg.lstsq(Aw, np.log(y[:, v]) * w[:, v] ** 0.5, rcond=None)[0]
    s0 = np.exp(p[0]); r2 = np.clip(p[1], 1e-4, 1.0)
    for _ in range(30):                          # Gauss-Newton on S0*exp(-R2*TE)
        ex = np.exp(-np.outer(te, r2)); f = s0 * ex
        res = y - f
        J0 = ex; J1 = -s0 * te[:, None] * ex
        a = (J0 * J0).sum(0); b = (J0 * J1).sum(0); d = (J1 * J1).sum(0)
        g0 = (J0 * res).sum(0); g1 = (J1 * res).sum(0)
        det = a * d - b * b
        det = np.where(np.abs(det) < 1e-30, 1e-30, det)
        ds0 = (d * g0 - b * g1) / det; dr2 = (-b * g0 + a * g1) / det
        s0 = s0 + ds0; r2 = np.clip(r2 + dr2, 1e-4, 1.0)
    t2 = np.full(mag.shape[1:], np.nan); s0m = np.full(mag.shape[1:], np.nan)
    t2[mask] = 1.0 / r2; s0m[mask] = s0
    return t2, s0m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--method', default=os.environ.get('T2MAP_METHOD', 'espirit'))
    a = ap.parse_args()
    d = np.load(a.input)
    ksp = d['kspace']; mask = d['sampling_mask'].astype(bool); labels = d['labels']
    te = np.asarray(d['echo_times_ms'], float); noise = d['noise_prescan']
    imgs, mps = recon_echoes(ksp, mask, noise, a.method)
    mag = np.abs(imgs)
    t2, s0 = fit_t2(mag, te, labels > 0)
    roi = float(np.nanmean(t2[labels == 1]))
    np.savez_compressed(a.output, t2_ms=t2.astype(np.float32), s0=s0.astype(np.float32), echo_images=imgs.astype(np.complex64),
                        roi_mean_t2_ms=roi, input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print(f'{a.input}: ROI mean T2 = {roi:.2f} ms')

if __name__ == '__main__':
    main()

