#!/usr/bin/env python3
"""Standalone UTE reconstruction: pair-sum the two half-pulse acquisitions of each spoke, then iterative least squares
with the exact non-uniform DFT.  python reconstruct.py --input simulation.npz --output image.npz"""
import argparse, hashlib, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--variant', default='reference')
    a = ap.parse_args(); V = a.variant
    z = np.load(a.input)
    raw = np.asarray(z['raw_signal']); k = np.asarray(z['kxy_cycles_per_m']); fov = float(z['fov_m']); n = int(np.asarray(z['matrix'])[0])
    pair = np.asarray(z['pair_index'])
    if V == 'neg_recon_no_pair_sum':
        sel = np.array([np.nonzero(pair == p)[0][0] for p in np.unique(pair)])
        data = raw[sel]; kk = k[sel]
    else:
        data = np.array([raw[pair == p].sum(0) for p in np.unique(pair)]); kk = np.array([k[pair == p][0] for p in np.unique(pair)])
    kx = kk[:, :, 0].ravel(); ky = kk[:, :, 1].ravel(); y = data.ravel()
    x = (np.arange(n) - n // 2) * fov / n; X, Y = np.meshgrid(x, x); r = np.stack([X.ravel(), Y.ravel()], 1)
    def E(img):
        out = np.empty(kx.size, complex)
        for s in range(0, kx.size, 4096):
            out[s:s + 4096] = np.exp(-2j * np.pi * (np.outer(kx[s:s + 4096], r[:, 0]) + np.outer(ky[s:s + 4096], r[:, 1]))) @ img
        return out
    def EH(v):
        out = np.zeros(r.shape[0], complex)
        for s in range(0, kx.size, 4096):
            out += np.exp(2j * np.pi * (np.outer(r[:, 0], kx[s:s + 4096]) + np.outer(r[:, 1], ky[s:s + 4096]))) @ v[s:s + 4096]
        return out
    b = EH(y); xk = np.zeros_like(b); rr = b.copy(); p = rr.copy(); rs = np.vdot(rr, rr)
    for it in range(40):
        Ap = EH(E(p)); al = rs / np.vdot(p, Ap); xk = xk + al * p; rr = rr - al * Ap
        rn = np.vdot(rr, rr)
        if abs(rn) < 1e-12 * abs(np.vdot(b, b)): break
        p = rr + rn / rs * p; rs = rn
    np.savez(a.output, image=xk.reshape(n, n), input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('image written', a.output)

if __name__ == '__main__':
    main()

