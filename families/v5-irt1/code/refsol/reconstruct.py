#!/usr/bin/env python3
"""Reference reconstruct.py: per-TI regularised least-squares NUFFT reconstruction (sigpy CG).
Usage: python reconstruct.py --input simulation.npz --output images.npz"""
import argparse, hashlib
import numpy as np

N = 40; FOV = 0.200

def recon_ti(y, kxy, swap=False, method='cg'):
    import sigpy as sp
    coord = np.stack([kxy[..., 1], kxy[..., 0]], -1) * FOV     # sigpy order follows image axes [y, x]
    if swap:
        coord = coord[..., ::-1]
    coord = coord.reshape(-1, 2)
    if method == 'dcf':
        kr = np.sqrt((coord ** 2).sum(-1)); w = np.maximum(kr, 0.25) / N
        return sp.nufft_adjoint(y.reshape(-1) * w, coord, (N, N)) * (np.pi / 2) / y.shape[0] * N
    A = sp.linop.NUFFT((N, N), coord)
    x = sp.app.LinearLeastSquares(A, y.reshape(-1).astype(np.complex128), lamda=1e-4, max_iter=60, show_pbar=False).run()
    return x

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--swap', action='store_true'); ap.add_argument('--method', default='cg')
    a = ap.parse_args()
    d = np.load(a.input)
    raw = d['raw_signal']; k = d['kxy_cycles_per_m']
    imgs = np.stack([recon_ti(raw[i], k[i], a.swap, a.method) for i in range(raw.shape[0])])
    np.savez(a.output, images=imgs.astype(np.complex128), inversion_times_s=np.asarray(d['inversion_times_s'], float),
             input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('reconstructed', imgs.shape)

if __name__ == '__main__':
    main()

