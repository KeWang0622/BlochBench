"""Generate public and hidden objects for heldout-v8-spiral-r4 (fixed seeds)."""
import json, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = 36; FOV = 0.234; DX = FOV / N
X = (np.arange(N) - N // 2) * DX
NZ = 11; L = 0.0072
Z = (np.arange(NZ) + 0.5) / NZ * L - L / 2

def make(seed, body, vials, corners, size=5, ell=(15.8, 14.4)):
    yy, xx = np.meshgrid(np.arange(N), np.arange(N), indexing='ij')
    lab = np.zeros((N, N), np.int16)
    lab[((yy - 17.5) / ell[0]) ** 2 + ((xx - 17.5) / ell[1]) ** 2 <= 1] = 1
    for k, (y0, x0) in enumerate(corners):
        lab[y0:y0 + size, x0:x0 + size] = k + 2
    rho = np.zeros((N, N)); T1 = np.zeros((N, N)); T2 = np.zeros((N, N))
    for k, (t1, t2, r) in enumerate([body] + list(vials)):
        m = lab == k + 1; T1[m] = t1; T2[m] = t2; rho[m] = r
    return dict(x_m=X, y_m=X.copy(), z_offsets_m=Z, density=rho, T1_s=T1, T2_s=T2, B0_Hz=np.zeros((N, N)), labels=lab, seed=np.int64(seed))

pub = make(95601, (0.55, 0.07, 0.83), [(0.32, 0.042, 1.0), (0.6, 0.14, 0.64), (0.48, 0.17, 0.9), (0.4, 0.036, 0.7), (0.58, 0.1, 0.97)],
           [(7, 10), (7, 21), (15, 15), (23, 9), (23, 22)])
hid = make(95691, (0.5, 0.065, 0.88), [(0.6, 0.16, 1.0), (0.28, 0.04, 0.68), (0.56, 0.09, 0.94), (0.44, 0.055, 0.78), (0.52, 0.13, 0.9), (0.37, 0.048, 0.96)],
           [(5, 12), (5, 20), (13, 6), (13, 15), (13, 24), (22, 15)], ell=(15.6, 15.2))
np.savez(HERE.parent / 'public/inputs/phantom.npz', **pub)
np.savez(HERE / 'hidden/phantom_hidden.npz', **hid)
json.dump({'hidden_delays_s': [-4.0e-6, 10.0e-6], 'note': 'known delay written into the hidden archive as gradient_delay_s; replay shifts ADC times by -delta'}, open(HERE / 'hidden/hidden_params.json', 'w'))
print((pub['labels'] > 0).sum(), (hid['labels'] > 0).sum())
print(pub['labels'])


