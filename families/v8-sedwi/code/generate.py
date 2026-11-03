"""Generate public and hidden objects for heldout-v8-sedwi-r4 (fixed seeds)."""
import numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = 24; FOV = 0.204; DX = FOV / N
X = (np.arange(N) - N // 2) * DX
NZ = 135; L = 0.0135
Z = (np.arange(NZ) + 0.5) / NZ * L - L / 2

def make(seed, body, vials, corners, size=5, ell=(10.4, 9.8)):
    yy, xx = np.meshgrid(np.arange(N), np.arange(N), indexing='ij')
    lab = np.zeros((N, N), np.int16)
    lab[((yy - 11.5) / ell[0]) ** 2 + ((xx - 11.5) / ell[1]) ** 2 <= 1] = 1
    for k, (y0, x0) in enumerate(corners):
        lab[y0:y0 + size, x0:x0 + size] = k + 2
    rho = np.zeros((N, N)); T1 = np.zeros((N, N)); T2 = np.zeros((N, N)); D = np.zeros((N, N))
    for k, (t1, t2, r, d) in enumerate([body] + list(vials)):
        m = lab == k + 1; T1[m] = t1; T2[m] = t2; rho[m] = r; D[m] = d
    return dict(x_m=X, y_m=X.copy(), z_offsets_m=Z, density=rho, T1_s=T1, T2_s=T2, B0_Hz=np.zeros((N, N)), D_mm2_per_s=D, labels=lab, seed=np.int64(seed))

pub = make(94401, (1.1, 0.08, 0.84, 0.7e-3), [(2.5, 0.21, 1.0, 2.55e-3), (0.6, 0.06, 0.9, 0.5e-3), (1.6, 0.12, 0.84, 1.35e-3), (0.9, 0.07, 0.95, 0.95e-3), (1.9, 0.16, 0.76, 1.75e-3)],
           [(4, 7), (4, 13), (10, 10), (16, 6), (16, 13)])
hid = make(94491, (0.95, 0.075, 0.88, 0.8e-3), [(2.4, 0.19, 1.0, 2.8e-3), (0.7, 0.062, 0.87, 0.6e-3), (1.8, 0.14, 0.93, 1.45e-3), (1.2, 0.1, 0.8, 1.15e-3), (2.1, 0.17, 0.91, 2.05e-3), (0.8, 0.055, 1.0, 0.4e-3)],
           [(2, 9), (8, 3), (8, 9), (8, 15), (15, 5), (15, 13)], ell=(10.6, 10.3))
np.savez(HERE.parent / 'public/inputs/phantom.npz', **pub)
np.savez(HERE / 'hidden/phantom_hidden.npz', **hid)
print('ok')

