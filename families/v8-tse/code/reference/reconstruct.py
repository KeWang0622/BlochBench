#!/usr/bin/env python3
"""Standalone TSE reconstruction: python reconstruct.py --input simulation.npz --output image.npz"""
import argparse, hashlib, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--variant', default='reference')
    a = ap.parse_args()
    z = np.load(a.input)
    raw = np.asarray(z['raw_signal']); k = np.asarray(z['kxy_cycles_per_m'])
    ne, ns = raw.shape; n = ns
    dk = np.median(np.diff(k[:, :, 0], axis=1))
    K = np.zeros((n, n), complex)
    for e in range(ne):
        if a.variant == 'neg_recon_acquisition_order':
            iy = e                                   # mistake: assumes lines were acquired in ky order
        else:
            iy = int(np.rint(np.median(k[e, :, 1]) / dk)) + n // 2
        ix = np.clip(np.rint(k[e, :, 0] / dk).astype(int) + n // 2, 0, n - 1)
        iy = int(np.clip(iy, 0, n - 1))
        K[iy, ix] = raw[e]
    img = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(K))) * n * n
    np.savez(a.output, image=img, input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('image written', a.output)

if __name__ == '__main__':
    main()

