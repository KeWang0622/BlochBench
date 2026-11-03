#!/usr/bin/env python3
"""Reference fit_t1.py: phase-sensitive IR fit S(TI) = A - B exp(-TI/T1) by variable projection.
Usage: python fit_t1.py --input images.npz --output t1map.npz [--mode signed|magnitude|naive|twoparam]"""
import argparse, hashlib
import numpy as np

def fit(img, ti, mode='signed'):
    E = img.shape[0]
    mag = np.abs(img)
    ref = img[np.argmax(ti)]                       # longest TI: positive longitudinal magnetisation
    if mode in ('signed', 'twoparam'):
        y = np.real(img * np.exp(-1j * np.angle(ref))[None])
    else:
        y = mag
    Y = y.reshape(E, -1)
    t1g = np.exp(np.linspace(np.log(0.02), np.log(6.0), 1500))
    best = np.full(Y.shape[1], np.inf); bt1 = np.zeros(Y.shape[1]); bA = np.zeros(Y.shape[1]); bB = np.zeros(Y.shape[1])
    for t1 in t1g:
        ex = np.exp(-ti / t1)
        if mode == 'twoparam':
            X = (1 - 2 * ex)[:, None]
            c = np.linalg.lstsq(X, Y, rcond=None)[0]
            r = ((Y - X @ c) ** 2).sum(0)
            upd = r < best; best[upd] = r[upd]; bt1[upd] = t1; bA[upd] = c[0, upd]; bB[upd] = 2 * c[0, upd]
            continue
        X = np.stack([np.ones(E), -ex], 1)
        if mode == 'magnitude':           # polarity-free: |A - B e^{-TI/T1}|, try every null position
            for nflip in range(E + 1):
                sgn = np.ones(E); sgn[:nflip] = -1
                c = np.linalg.lstsq(X, sgn[:, None] * Y, rcond=None)[0]
                r = ((np.abs(X @ c) - Y) ** 2).sum(0)
                upd = r < best; best[upd] = r[upd]; bt1[upd] = t1; bA[upd] = c[0, upd]; bB[upd] = c[1, upd]
        else:                              # 'signed' or 'naive' (magnitude data fitted with signed model)
            c = np.linalg.lstsq(X, Y, rcond=None)[0]
            r = ((Y - X @ c) ** 2).sum(0)
            upd = r < best; best[upd] = r[upd]; bt1[upd] = t1; bA[upd] = c[0, upd]; bB[upd] = c[1, upd]
    shp = img.shape[1:]
    t1 = bt1.reshape(shp); A = bA.reshape(shp); B = bB.reshape(shp)
    thr = 0.05 * mag.max()
    t1 = np.where(mag.max(0) > thr, t1, np.nan)
    return t1, A, B

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    ap.add_argument('--mode', default='signed')
    a = ap.parse_args()
    d = np.load(a.input)
    img = d['images']; ti = np.asarray(d['inversion_times_s'], float)
    t1, A, B = fit(img, ti, a.mode)
    np.savez(a.output, t1_s=t1, a_map=A, b_map=B, input_sha256=hashlib.sha256(open(a.input, 'rb').read()).hexdigest())
    print('fitted; median T1 in object', np.nanmedian(t1))

if __name__ == '__main__':
    main()

