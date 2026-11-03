"""Generate public and hidden objects for heldout-v8-epinav-r4 (fixed seeds)."""
import json, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = 24; FOV = 0.21; DX = FOV / N
X = (np.arange(N) - N // 2) * DX
NZ = 31; L = 0.0135
Z = (np.arange(NZ) + 0.5) / NZ * L - L / 2

def make(seed, body, vials, corners, size=5, ell=(10.3, 9.6)):
    yy, xx = np.meshgrid(np.arange(N), np.arange(N), indexing='ij')
    lab = np.zeros((N, N), np.int16)
    lab[((yy - 11.5) / ell[0]) ** 2 + ((xx - 11.5) / ell[1]) ** 2 <= 1] = 1
    for k, (y0, x0) in enumerate(corners):
        lab[y0:y0 + size, x0:x0 + size] = k + 2
    rho = np.zeros((N, N)); T1 = np.zeros((N, N)); T2 = np.zeros((N, N))
    for k, (t1, t2, r) in enumerate([body] + list(vials)):
        m = lab == k + 1; T1[m] = t1; T2[m] = t2; rho[m] = r
    return dict(x_m=X, y_m=X.copy(), z_offsets_m=Z, density=rho, T1_s=T1, T2_s=T2, B0_Hz=np.zeros((N, N)), labels=lab, seed=np.int64(seed))

pub = make(96601, (1.2, 0.07, 0.84), [(0.5, 0.04, 1.0), (1.4, 0.14, 0.6), (0.8, 0.17, 0.9), (0.6, 0.055, 0.74), (1.6, 0.1, 0.96)],
           [(4, 7), (4, 13), (10, 10), (15, 5), (15, 14)])
hid = make(96691, (1.0, 0.062, 0.87), [(1.25, 0.16, 1.0), (0.42, 0.044, 0.68), (0.7, 0.08, 0.94), (1.45, 0.052, 0.77), (0.62, 0.13, 0.91), (1.1, 0.046, 0.98)],
           [(3, 8), (3, 14), (9, 3), (9, 10), (9, 17), (16, 9)], ell=(11.0, 10.6))
np.savez(HERE.parent / 'public/inputs/phantom.npz', **pub)
np.savez(HERE / 'hidden/phantom_hidden.npz', **hid)
json.dump({'hidden_delays_s': [-4.6e-6, 3.1e-6], 'note': 'gradients lag the ADC by delta: ADC sample times shifted by -delta in the replay'}, open(HERE / 'hidden/hidden_params.json', 'w'))
print((pub['labels'] > 0).sum(), (hid['labels'] > 0).sum())
print(pub['labels'])

