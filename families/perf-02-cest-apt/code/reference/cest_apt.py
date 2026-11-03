#!/usr/bin/env python3
"""APT-weighted CEST asymmetry with WASSR B0 correction (reference solution, heldout-v7-cestapt).

Usage: python cest_apt.py --input-dir <dir with cest.npz wassr.npz params.json> --output apt.npz
"""
import argparse, json
from pathlib import Path
import numpy as np
from scipy.interpolate import CubicSpline

USE_B0 = True
B0_SIGN = 1.0
WASSR_IN_PPM_ALREADY = False
B0_METHOD = 'spline_min'
NORMALISE = 's0'
TRUST_STORED_ORDER = True
ASYM_SIGN = 1.0
INTERP = 'spline'


def spline_eval(x, y, xq):
    """Cubic spline over axis 0 of y (n, nvox), evaluated at per-voxel xq (nvox,)."""
    cs = CubicSpline(x, y, axis=0)
    i = np.clip(np.searchsorted(x, xq) - 1, 0, len(x) - 2)
    dx = xq - x[i]
    v = np.arange(y.shape[1])
    c = cs.c
    return ((c[0, i, v] * dx + c[1, i, v]) * dx + c[2, i, v]) * dx + c[3, i, v]


def b0_from_wassr(w, wppm):
    order = np.argsort(wppm)
    x = wppm[order]
    y = w[order]
    y = y / np.maximum(y.max(0, keepdims=True), 1e-9)
    if B0_METHOD == 'parabola':
        k = np.argmin(y, 0)
        k = np.clip(k, 1, len(x) - 2)
        v = np.arange(y.shape[1])
        ym, y0, yp = y[k - 1, v], y[k, v], y[k + 1, v]
        den = ym - 2 * y0 + yp
        frac = np.where(np.abs(den) > 1e-12, 0.5 * (ym - yp) / den, 0.0)
        return x[k] + np.clip(frac, -1, 1) * (x[1] - x[0])
    if B0_METHOD == 'lorentz':
        from scipy.optimize import curve_fit
        out = np.zeros(y.shape[1])
        f = lambda xx, a, c, g, o: o - a * g ** 2 / (g ** 2 + (xx - c) ** 2)
        for j in range(y.shape[1]):
            c0 = x[np.argmin(y[:, j])]
            try:
                p, _ = curve_fit(f, x, y[:, j], p0=[0.8, c0, 0.15, 1.0], maxfev=2000)
                out[j] = p[1]
            except Exception:
                out[j] = c0
        return out
    xf = np.linspace(x[0], x[-1], 2001)
    cs = CubicSpline(x, y, axis=0)
    return xf[np.argmin(cs(xf), 0)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    d = Path(a.input_dir)
    prm = json.loads((d / 'params.json').read_text())
    f0 = prm['gamma_MHz_per_T'] * prm['field_strength_T']
    c = np.load(d / 'cest.npz')
    imgs, offs = c['images'].astype(float), c['offsets_ppm'].astype(float)
    w = np.load(d / 'wassr.npz')
    wimg, whz = w['images'].astype(float), w['offsets_hz'].astype(float)
    ny, nx = imgs.shape[1:]
    ref = np.abs(offs) > 100
    s0 = imgs[ref].mean(0)
    sat = imgs[~ref]
    so = offs[~ref]
    if not TRUST_STORED_ORDER:
        so = np.sort(so)
    mask = s0 > 0.15 * np.percentile(s0, 99)
    vox = np.where(mask.ravel())[0]
    if NORMALISE == 's0':
        z = sat.reshape(len(so), -1)[:, vox] / s0.ravel()[vox]
    else:
        far = np.argmin(so)
        z = sat.reshape(len(so), -1)[:, vox] / sat.reshape(len(so), -1)[far, vox]
    wppm = whz if WASSR_IN_PPM_ALREADY else whz / f0
    b0v = b0_from_wassr(wimg.reshape(len(whz), -1)[:, vox], wppm) if USE_B0 else np.zeros(len(vox))
    b0v = b0v * B0_SIGN
    order = np.argsort(so)
    x, zz = so[order], z[order]
    if INTERP == 'spline':
        zm = spline_eval(x, zz, -3.5 + b0v)
        zp = spline_eval(x, zz, 3.5 + b0v)
    else:
        zm = np.array([np.interp(-3.5 + b, x, zz[:, j]) for j, b in enumerate(b0v)])
        zp = np.array([np.interp(3.5 + b, x, zz[:, j]) for j, b in enumerate(b0v)])
    mtr = np.zeros(ny * nx)
    b0 = np.zeros(ny * nx)
    mtr[vox] = 100 * ASYM_SIGN * (zm - zp)
    b0[vox] = b0v
    np.savez_compressed(a.output, mtr_asym_3p5_percent=mtr.reshape(ny, nx), b0_ppm=b0.reshape(ny, nx))


if __name__ == '__main__':
    main()

