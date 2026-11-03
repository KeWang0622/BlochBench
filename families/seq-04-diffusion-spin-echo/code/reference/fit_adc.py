#!/usr/bin/env python3
"""Standalone ADC (mean diffusivity) fit: python fit_adc.py --input simulation.npz --output adcmap.npz"""
import argparse, hashlib, numpy as np

def recon(raw, k, fov, n):
    x = (np.arange(n) - n // 2) * fov / n
    P = np.array([np.linalg.lstsq(np.exp(-2j * np.pi * np.outer(kk[:, 0], x)), s, rcond=None)[0] for s, kk in zip(raw, k)])
    ky = np.median(k[:, :, 1], axis=1)
    return np.exp(2j * np.pi * np.outer(x, ky)) @ P

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--variant', default='reference')
    a = ap.parse_args()
    z = np.load(a.input)
    raw = np.asarray(z['raw_signal']); k = np.asarray(z['kxy_cycles_per_m']); vol = np.asarray(z['volume_index'])
    b = np.asarray(z['b_values_s_per_mm2'], float); fov = float(z['fov_m']); n = int(np.asarray(z['matrix'])[0])
    if a.variant == 'neg_fit_nominal_b':
        b = np.where(b > 100, 1200.0, 0.0)
    imgs = np.array([np.abs(recon(raw[vol == v], k[vol == v], fov, n)) for v in range(len(b))])
    i0 = int(np.argmin(b)); S0 = imgs[i0]
    mask = S0 > 0.05 * S0.max()
    adc = np.zeros((n, n))
    dw = [v for v in range(len(b)) if v != i0]
    with np.errstate(divide='ignore', invalid='ignore'):
        est = np.mean([-np.log(imgs[v] / S0) / (b[v] - b[i0]) for v in dw], axis=0)
    adc[mask] = est[mask]
    np.savez(a.output, adc_mm2_per_s=adc, input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('adc written', a.output)

if __name__ == '__main__':
    main()

