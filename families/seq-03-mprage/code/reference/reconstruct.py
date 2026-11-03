#!/usr/bin/env python3
"""Standalone 3D Cartesian reconstruction: python reconstruct.py --input simulation.npz --output image.npz"""
import argparse, hashlib, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--variant', default='reference')
    a = ap.parse_args()
    z = np.load(a.input)
    raw = np.asarray(z['raw_signal']); k = np.asarray(z['kxyz_cycles_per_m'])
    nc, ny, nx = raw.shape; nz = nc
    dkx = np.median(np.diff(k[..., 0], axis=-1))
    dky = np.median(np.diff(np.median(k[0, :, :, 1], axis=-1)))
    dkz = np.median(np.diff(np.sort(np.median(k[..., 2], axis=(1, 2)))))
    K = np.zeros((nz, ny, nx), complex)
    for c in range(nc):
        for j in range(ny):
            iz = int(np.clip(np.rint(np.median(k[c, j, :, 2]) / dkz) + nz // 2, 0, nz - 1))
            if a.variant == 'neg_recon_kz_order':
                iz = c                                   # mistake: assumes partitions were acquired in kz order
            iy = int(np.clip(np.rint(np.median(k[c, j, :, 1]) / dky) + ny // 2, 0, ny - 1))
            ix = np.clip(np.rint(k[c, j, :, 0] / dkx).astype(int) + nx // 2, 0, nx - 1)
            K[iz, iy, ix] = raw[c, j]
    img = np.fft.fftshift(np.fft.ifftn(np.fft.ifftshift(K))) * K.size
    np.savez(a.output, image=img, input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('image written', a.output)

if __name__ == '__main__':
    main()

