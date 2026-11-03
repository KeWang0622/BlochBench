#!/usr/bin/env python3
"""Standalone classical reconstruction: joint-sparsity (group L1 across echoes) wavelet CS with sigpy.
python classical_recon.py --input test.npz --output recon.npz"""
import argparse
import numpy as np, sigpy as sp
LAM = 0.03   # tuned on validation subjects (downstream R2*/B0 error), relative to a unit echo-1 peak
OPT = {'mode': 'joint', 'iters': 100, 'fixed_mask': False}

class GroupL1(sp.prox.Prox):
    def __init__(self, shape, lamda):
        self.lamda = lamda; super().__init__(shape)
    def _prox(self, alpha, x):
        nrm = np.sqrt((np.abs(x) ** 2).sum(0, keepdims=True))
        return x * np.maximum(1 - self.lamda * alpha / np.maximum(nrm, 1e-12), 0)

def recon_one(k, m, lam):
    E = k.shape[0]
    zf = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))
    if OPT['mode'] == 'zf':   # (negative control) zero-filled submitted as the classical method
        return zf
    s = np.abs(zf[0]).max() + 1e-12; y = k / s; w = m.astype(float)
    F = sp.linop.Multiply(k.shape, w) * sp.linop.FFT(k.shape, axes=(-2, -1), center=True)
    W = sp.linop.Wavelet(k.shape, axes=(-2, -1))
    if OPT['mode'] == 'joint':
        prox = GroupL1(W.oshape, lam)
    else:
        prox = sp.prox.L1Reg(W.oshape, lam)
    x = sp.app.LinearLeastSquares(F, y * w, proxg=prox, G=W, max_iter=OPT['iters'], show_pbar=False).run()
    return x * s

def main(inp, outp, lam=LAM):
    d = np.load(inp); K = d['kspace']; M = d['mask'].astype(bool)
    if OPT['fixed_mask']:   # (negative control) uses the first case's mask for every case
        M = np.broadcast_to(M[:1], M.shape)
    R = np.stack([recon_one(K[i], M[i], lam) for i in range(len(K))]).astype(np.complex64)
    np.savez_compressed(outp, recon=R)
    return R

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    a = ap.parse_args(); main(a.input, a.output)

