"""Generate public and hidden objects for heldout-v8-ute-r4 (fixed seeds)."""
import json, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = 26; FOV = 0.208; DX = FOV / N
X = (np.arange(N) - N // 2) * DX
NZ = 61; L = 0.03355
Z = (np.arange(NZ) + 0.5) / NZ * L - L / 2

def make(seed, body, vials, corners, size=5, ell=(11.2, 10.6)):
    yy, xx = np.meshgrid(np.arange(N), np.arange(N), indexing='ij')
    lab = np.zeros((N, N), np.int16)
    lab[((yy - 12.5) / ell[0]) ** 2 + ((xx - 12.5) / ell[1]) ** 2 <= 1] = 1
    for k, (y0, x0) in enumerate(corners):
        lab[y0:y0 + size, x0:x0 + size] = k + 2
    rho = np.zeros((N, N)); T1 = np.zeros((N, N)); T2 = np.zeros((N, N))
    for k, (t1, t2, r) in enumerate([body] + list(vials)):
        m = lab == k + 1; T1[m] = t1; T2[m] = t2; rho[m] = r
    return dict(x_m=X, y_m=X.copy(), z_offsets_m=Z, density=rho, T1_s=T1, T2_s=T2, B0_Hz=np.zeros((N, N)), labels=lab, seed=np.int64(seed))

pub = make(98601, (0.85, 0.07, 0.82), [(0.33, 0.00065, 1.0), (0.55, 0.0016, 0.9), (0.9, 0.08, 0.74), (0.42, 0.0026, 0.87), (1.05, 0.05, 0.97)],
           [(2, 10), (8, 4), (8, 16), (15, 7), (15, 14)])
hid = make(98691, (0.75, 0.06, 0.86), [(0.4, 0.00085, 1.0), (0.32, 0.00068, 0.9), (0.88, 0.065, 0.78), (0.6, 0.0021, 0.95), (1.0, 0.09, 0.82), (0.36, 0.0012, 1.0)],
           [(4, 8), (4, 14), (10, 3), (10, 10), (10, 17), (17, 11)], ell=(11.4, 11.1))
np.savez(HERE.parent / 'public/inputs/phantom.npz', **pub)
np.savez(HERE / 'hidden/phantom_hidden.npz', **hid)

print((pub['labels'] > 0).sum(), (hid['labels'] > 0).sum())
print(pub['labels'])


