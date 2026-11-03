#!/usr/bin/env python3
"""Generate training / public-test / hidden-test multi-echo GRE data for heldout-v5-learnrecon (fixed seeds)."""
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter
HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'; HID = HERE / 'hidden'
N = 64; TE = np.array([4.0, 9.9, 15.8, 21.7, 27.6]) * 1e-3; SIG = 0.018; NCENT = 8; NLINES = 16

def fft2c(x):
    return np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(x, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))

def ell(Y, X, cy, cx, ay, ax, th):
    c, s = np.cos(th), np.sin(th)
    u = ((X - cx) * c + (Y - cy) * s) / ax; v = (-(X - cx) * s + (Y - cy) * c) / ay
    return u ** 2 + v ** 2 <= 1

def subject(rng):
    """Subject-level parameters."""
    return {'ay': rng.uniform(0.72, 0.86), 'ax': rng.uniform(0.60, 0.74), 'th': rng.uniform(-0.35, 0.35), 'cy': rng.uniform(-0.04, 0.04), 'cx': rng.uniform(-0.04, 0.04),
            'r2': {1: 22 * rng.uniform(0.9, 1.1), 2: 32 * rng.uniform(0.9, 1.1), 3: 18.5 * rng.uniform(0.9, 1.1), 4: 52 * rng.uniform(0.88, 1.12)},
            'pd': {1: 0.68, 2: 0.76, 3: 0.86, 4: 0.70}, 'fpoly': rng.normal(0, 11, 6), 'sinus': (rng.uniform(-0.15, 0.15), rng.uniform(0.42, 0.62) * rng.choice([-1, 1]), rng.uniform(22, 48) * rng.choice([-1, 1])),
            'ph0': rng.normal(0, 0.8, 4), 'seed': int(rng.integers(1 << 30))}

def slice_data(P, z, rng):
    y, x = np.meshgrid(np.linspace(-1, 1, N), np.linspace(-1, 1, N), indexing='ij')
    sc = 1 - 0.25 * z ** 2  # head shrinks away from the central slice
    head = ell(y, x, P['cy'], P['cx'], P['ay'] * sc, P['ax'] * sc, P['th'])
    inner = ell(y, x, P['cy'], P['cx'], P['ay'] * sc - 0.10, P['ax'] * sc - 0.10, P['th'])
    lab = np.zeros((N, N), np.int16); lab[head] = 3; lab[inner] = 1
    for sgn in (-1, 1):
        lab[ell(y, x, P['cy'] + 0.05, P['cx'] + sgn * 0.22 * sc, 0.17 * sc, 0.09 * sc, sgn * 0.3) & inner] = 2
    for k in range(rng.integers(2, 4)):
        cy, cx = rng.uniform(-0.45, 0.45) * sc, rng.uniform(-0.4, 0.4) * sc
        m = ell(y, x, cy, cx, rng.uniform(0.06, 0.11), rng.uniform(0.06, 0.11), rng.uniform(0, 3)) & inner & (lab == 1)
        lab[m] = 4
    tex = gaussian_filter(rng.standard_normal((N, N)), 1.2); tex /= tex.std()
    smooth = gaussian_filter(rng.standard_normal((N, N)), 6); smooth /= smooth.std()
    pd = np.zeros((N, N)); r2 = np.zeros((N, N))
    for k in range(1, 5):
        m = lab == k
        pd[m] = P['pd'][k] * (1 + 0.06 * tex[m] + 0.04 * smooth[m])
        r2[m] = P['r2'][k] * (1 + 0.05 * smooth[m] + 0.03 * tex[m])
    a = P['fpoly']
    f = a[0] + a[1] * y + a[2] * x + a[3] * y * x + a[4] * y ** 2 + a[5] * x ** 2
    sy, sx, amp = P['sinus']
    f = f + amp * np.exp(-((y - sy) ** 2 + (x - sx) ** 2) / (2 * 0.12 ** 2)) * (1 - 0.5 * abs(z))
    f = np.clip(f, -72, 72)
    b = P['ph0']; ph0 = b[0] + b[1] * y + b[2] * x + b[3] * (x ** 2 + y ** 2)
    img = pd[None] * np.exp(-r2[None] * TE[:, None, None]) * np.exp(1j * (ph0[None] + 2 * np.pi * f[None] * TE[:, None, None]))
    img[:, lab == 0] = 0
    f[lab == 0] = 0; r2[lab == 0] = 0
    k = fft2c(img) + SIG * (rng.standard_normal(img.shape) + 1j * rng.standard_normal(img.shape))
    return k.astype(np.complex64), lab, r2.astype(np.float32), f.astype(np.float32)

def masks(rng, n, accel=4.0, rc=5.5):
    """2D variable-density random phase-encode masks (ky-kz plane of a 3D acquisition), different per echo."""
    out = np.zeros((n, len(TE), N, N), bool)
    ky, kx = np.meshgrid(np.arange(N) - N // 2, np.arange(N) - N // 2, indexing='ij')
    r = np.sqrt(ky ** 2 + kx ** 2); cen = r <= rc
    w = 1.0 / (1 + (r / 8.0) ** 2); w[cen] = 0; w = w.ravel() / w.sum()
    nsel = int(round(N * N / accel)) - int(cen.sum())
    for i in range(n):
        for e in range(len(TE)):
            sel = rng.choice(N * N, nsel, replace=False, p=w)
            m = cen.copy().ravel(); m[sel] = True
            out[i, e] = m.reshape(N, N)
    return out

def make_set(rng, sids, nsl):
    K, L, R, F, S, Z = [], [], [], [], [], []
    for sid in sids:
        P = subject(rng); srng = np.random.default_rng(P['seed'])
        for j in range(nsl):
            z = -0.6 + 1.2 * j / max(nsl - 1, 1)
            k, lab, r2, f = slice_data(P, z, srng)
            K.append(k); L.append(lab); R.append(r2); F.append(f); S.append(sid); Z.append(j)
    return np.array(K), np.array(L), np.array(R), np.array(F), np.array(S), np.array(Z)

def roi_truth(L, R, F):
    out = []
    for i in range(len(L)):
        d = {}
        for k in range(1, 5):
            m = L[i] == k
            if m.sum() >= 5:
                d[str(k)] = {'r2s_per_s': float(R[i][m].mean()), 'b0_hz': float(F[i][m].mean()), 'n': int(m.sum())}
        out.append(d)
    return out

def main():
    PUB.mkdir(parents=True, exist_ok=True); HID.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(737373)
    tr = ['A%03d' % i for i in range(401, 431)]; te_ = ['B%03d' % i for i in range(501, 509)]; hi = ['C%03d' % i for i in range(601, 609)]
    K, L, R, F, S, Z = make_set(rng, tr, 6)
    np.savez_compressed(PUB / 'train.npz', kspace=K, labels=L, subject_id=S, slice_index=Z, te_s=TE)
    for name, ids, dst in [('test', te_, PUB), ('hidden_test', hi, HID)]:
        K, L, R, F, S, Z = make_set(rng, ids, 4)
        M = masks(rng, len(K))
        Kus = (K * M).astype(np.complex64)
        np.savez_compressed(dst / (name + '.npz'), kspace=Kus, mask=M, labels=L, subject_id=S, slice_index=Z, te_s=TE)
        np.savez_compressed(HERE / (name + '_truth.npz'), kspace_full=K, r2s=R, b0=F, labels=L)
        (HERE / (name + '_roi_truth.json')).write_text(json.dumps(roi_truth(L, R, F)))
    print('done')

if __name__ == '__main__':
    main()

