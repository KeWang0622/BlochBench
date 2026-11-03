#!/usr/bin/env python3
"""Standalone spiral reconstruction (iterative least squares with the exact non-uniform DFT).
python reconstruct.py --input simulation.npz --output image.npz"""
import argparse, hashlib, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--variant', default='reference')
    a = ap.parse_args(); V = a.variant
    z = np.load(a.input)
    raw = np.asarray(z['raw_signal']).ravel(); k = np.asarray(z['kxy_cycles_per_m']); t = np.asarray(z['adc_times_s'])
    fov = float(z['fov_m']); n = int(np.asarray(z['matrix'])[0]); d = float(z['gradient_delay_s'])
    if V == 'neg_recon_ignores_delay':
        d = 0.0
    if V == 'neg_recon_delay_wrong_sign':
        d = -d
    # true k at nominal sample time t is k_nominal(t - d): interpolate along each interleave in time
    kk = np.empty_like(k)
    for i in range(k.shape[0]):
        tt = t[i] - d
        for c in range(2):
            kk[i, :, c] = np.interp(tt, t[i], k[i, :, c])
        early = tt < t[i, 0]
        if early.any():   # before the first sample: extrapolate linearly from the first two samples
            for c in range(2):
                slope = (k[i, 1, c] - k[i, 0, c]) / (t[i, 1] - t[i, 0])
                kk[i, early, c] = k[i, 0, c] + slope * (tt[early] - t[i, 0])
    kx = kk[:, :, 0].ravel(); ky = kk[:, :, 1].ravel()
    x = (np.arange(n) - n // 2) * fov / n
    X, Y = np.meshgrid(x, x)
    r = np.stack([X.ravel(), Y.ravel()], 1)
    def E(img):
        out = np.empty(kx.size, complex)
        for s in range(0, kx.size, 4096):
            out[s:s + 4096] = np.exp(-2j * np.pi * (np.outer(kx[s:s + 4096], r[:, 0]) + np.outer(ky[s:s + 4096], r[:, 1]))) @ img
        return out
    def EH(y):
        out = np.zeros(r.shape[0], complex)
        for s in range(0, kx.size, 4096):
            out += np.exp(2j * np.pi * (np.outer(r[:, 0], kx[s:s + 4096]) + np.outer(r[:, 1], ky[s:s + 4096]))) @ y[s:s + 4096]
        return out
    if V == 'pos_gridding_dcf':
        # Voronoi density compensation + exact adjoint DFT (gridding-type reconstruction without iterations)
        from scipy.spatial import Voronoi
        pts = np.stack([kx, ky], 1)
        dk = 1.0 / fov; R = np.abs(kx + 1j * ky).max() + dk
        ang = np.linspace(0, 2 * np.pi, 400, endpoint=False)
        ring = np.stack([R * np.cos(ang), R * np.sin(ang)], 1)
        vor = Voronoi(np.vstack([pts, ring]))
        w = np.zeros(len(pts))
        for i in range(len(pts)):
            reg = vor.regions[vor.point_region[i]]
            if -1 in reg or len(reg) == 0:
                w[i] = dk * dk; continue
            v = vor.vertices[reg]; xx, yy = v[:, 0], v[:, 1]
            w[i] = 0.5 * abs(np.dot(xx, np.roll(yy, 1)) - np.dot(yy, np.roll(xx, 1)))
        w = np.minimum(w, 4 * dk * dk)
        img = EH(w * raw) * (fov / n) ** 2
    else:
        b = EH(raw); xk = np.zeros_like(b); rr = b.copy(); p = rr.copy(); rs = np.vdot(rr, rr)
        for it in range(40):
            Ap = EH(E(p)); al = rs / np.vdot(p, Ap); xk = xk + al * p; rr = rr - al * Ap
            rn = np.vdot(rr, rr)
            if abs(rn) < 1e-12 * abs(np.vdot(b, b)): break
            p = rr + rn / rs * p; rs = rn
        img = xk
    np.savez(a.output, image=img.reshape(n, n), input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('image written', a.output)

if __name__ == '__main__':
    main()

