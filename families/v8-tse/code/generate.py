"""Generate public and hidden objects for heldout-v8-tse (fixed seeds)."""
import numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = 18; FOV = 0.216; DX = FOV / N
X = (np.arange(N) - N // 2) * DX
NZ = 105; L = 0.0105
Z = (np.arange(NZ) + 0.5) / NZ * L - L / 2

def make(seed, body, vials, corners, size=4):
    yy, xx = np.meshgrid(np.arange(N), np.arange(N), indexing='ij')
    lab = np.zeros((N, N), np.int16)
    lab[np.hypot(yy - 8.5, xx - 8.5) <= 7.9] = 1
    for k, (y0, x0) in enumerate(corners):
        lab[y0:y0 + size, x0:x0 + size] = k + 2
    rho = np.zeros((N, N)); T1 = np.zeros((N, N)); T2 = np.zeros((N, N))
    for k, (t1, t2, r) in enumerate([body] + list(vials)):
        m = lab == k + 1; T1[m] = t1; T2[m] = t2; rho[m] = r
    return dict(x_m=X, y_m=X.copy(), z_offsets_m=Z, density=rho, T1_s=T1, T2_s=T2, B0_Hz=np.zeros((N, N)), labels=lab, seed=np.int64(seed))

pub = make(93201, (0.95, 0.085, 0.82), [(0.4, 0.048, 0.97), (1.5, 0.2, 0.9), (0.75, 0.07, 0.86), (1.2, 0.12, 0.94), (0.55, 0.27, 0.92)],
           [(3, 5), (3, 10), (8, 3), (8, 11), (12, 7)])
hid = make(93291, (0.8, 0.072, 0.88), [(1.6, 0.25, 1.0), (0.36, 0.046, 0.86), (1.05, 0.14, 0.95), (0.5, 0.065, 0.82), (1.3, 0.095, 0.9), (0.65, 0.18, 1.0)],
           [(1, 7), (6, 2), (6, 7), (6, 12), (11, 4), (11, 10)])
np.savez(HERE.parent / 'public/inputs/phantom.npz', **pub)
np.savez(HERE / 'hidden/phantom_hidden.npz', **hid)
print('ok', (pub['labels'] > 0).sum())

