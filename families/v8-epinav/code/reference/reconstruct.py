#!/usr/bin/env python3
"""Standalone ramp-sampled EPI reconstruction with navigator-based delay correction.
python reconstruct.py --input simulation.npz --output image.npz"""
import argparse, hashlib, numpy as np

def proj(s, kx, x):
    E = np.exp(-2j * np.pi * np.outer(kx, x))
    return np.linalg.lstsq(E, s, rcond=None)[0]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--variant', default='reference')
    a = ap.parse_args(); V = a.variant
    z = np.load(a.input)
    raw = np.asarray(z['raw_signal']); k = np.asarray(z['kxy_cycles_per_m']); t = np.asarray(z['adc_times_s'])
    nav = np.asarray(z['is_navigator']).astype(bool); fov = float(z['fov_m']); n = int(np.asarray(z['matrix'])[0])
    x = (np.arange(n) - n // 2) * fov / n
    kx = k[:, :, 0]
    kdot = np.gradient(kx, axis=1) / np.gradient(t, axis=1)
    if V == 'neg_uniform_kx_recon':
        # mistake: treat the samples as uniformly spaced in kx (ignores ramp sampling)
        lin = np.linspace(-1, 1, kx.shape[1])
        kx = np.where(np.sign(kdot[:, kx.shape[1] // 2:kx.shape[1] // 2 + 1]) > 0, 1, -1) * lin * np.abs(kx).max(axis=1, keepdims=True)
    ni = np.nonzero(nav)[0]
    def cost(d):
        kk = kx - d * kdot
        p = [proj(raw[i], kk[i], x) for i in ni[:3]]
        ref = 0.5 * (p[0] + p[2]); c = np.vdot(p[1], ref) / np.vdot(p[1], p[1])
        return float(np.linalg.norm(ref - c * p[1]) ** 2)
    d = 0.0
    if V == 'reference' and len(ni) >= 3:
        lo, hi = -10e-6, 10e-6
        grid = np.linspace(lo, hi, 41); cs = [cost(g) for g in grid]; g0 = grid[int(np.argmin(cs))]
        lo, hi = g0 - 0.5e-6, g0 + 0.5e-6
        gr = (np.sqrt(5) - 1) / 2
        c1, c2 = hi - gr * (hi - lo), lo + gr * (hi - lo); f1, f2 = cost(c1), cost(c2)
        for _ in range(40):
            if f1 < f2: hi, c2, f2 = c2, c1, f1; c1 = hi - gr * (hi - lo); f1 = cost(c1)
            else: lo, c1, f1 = c1, c2, f2; c2 = lo + gr * (hi - lo); f2 = cost(c2)
        d = 0.5 * (lo + hi)
    kk = kx - d * kdot
    img_idx = np.nonzero(~nav)[0]
    P = np.array([proj(raw[i], kk[i], x) for i in img_idx])
    if V == 'pos_linear_phase_nav' and len(ni) >= 3:
        p = [proj(raw[i], kx[i], x) for i in ni[:3]]
        q = (0.5 * (p[0] + p[2])) * np.conj(p[1])
        slope = np.angle(np.sum(q[1:] * np.conj(q[:-1]))) / (x[1] - x[0])      # phase gradient, no unwrapping needed
        c0 = np.angle(np.sum(q * np.exp(-1j * slope * x)))
        c = (c0, slope)
        corr = np.exp(1j * (c[0] + c[1] * x))
        pol = np.sign(kdot[img_idx, kdot.shape[1] // 2]); polnav = np.sign(kdot[ni[1], kdot.shape[1] // 2])
        P = np.where((pol == polnav)[:, None], P * corr[None, :], P)
    ky = np.median(k[img_idx, :, 1], axis=1)
    y = x.copy()
    img = np.exp(2j * np.pi * np.outer(y, ky)) @ P
    np.savez(a.output, image=img, estimated_delay_s=d, input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('image written', a.output, 'delay estimate %.3f us' % (d * 1e6))

if __name__ == '__main__':
    main()

