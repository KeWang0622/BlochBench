"""Generate public and hidden 3D objects for heldout-v8-mprage-r4 (fixed seeds)."""
import numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
NX, NY, NZ = 20, 12, 6; FOVX, FOVY, FOVZ = 0.240, 0.144, 0.054
X = (np.arange(NX) - NX // 2) * FOVX / NX
Y = (np.arange(NY) - NY // 2) * FOVY / NY
Zc = (np.arange(NZ) - NZ // 2) * FOVZ / NZ
NSUB = 72; DZ = FOVZ / NZ
SUB = (np.arange(NSUB) + 0.5) / NSUB * DZ - DZ / 2

def make(seed, body, vials, corners, ell):
    zz, yy, xx = np.meshgrid(np.arange(NZ), np.arange(NY), np.arange(NX), indexing='ij')
    lab = np.zeros((NZ, NY, NX), np.int16)
    lab[(((yy - 5.5) / ell[0]) ** 2 + ((xx - 9.5) / ell[1]) ** 2 <= 1) & (zz >= 1) & (zz <= 4)] = 1
    for k, (y0, x0) in enumerate(corners):
        lab[1:5, y0:y0 + 4, x0:x0 + 4] = k + 2
    rho = np.zeros(lab.shape); T1 = np.zeros(lab.shape); T2 = np.zeros(lab.shape)
    for k, (t1, t2, r) in enumerate([body] + list(vials)):
        m = lab == k + 1; T1[m] = t1; T2[m] = t2; rho[m] = r
    return dict(x_m=X, y_m=Y, z_m=Zc, z_sub_offsets_m=SUB, density=rho, T1_s=T1, T2_s=T2, B0_Hz=np.zeros(lab.shape), labels=lab, seed=np.int64(seed))

pub = make(94817, (1.35, 0.08, 0.84), [(0.78, 0.062, 0.98), (0.48, 0.052, 0.9), (1.85, 0.092, 0.93)], [(2, 4), (2, 12), (6, 8)], ell=(5.3, 8.7))
hid = make(94853, (1.15, 0.072, 0.88), [(0.78, 0.058, 0.95), (1.9, 0.097, 1.0), (0.6, 0.05, 0.8), (1.55, 0.086, 0.91)], [(2, 3), (2, 13), (6, 3), (6, 13)], ell=(5.4, 8.9))
np.savez(HERE.parent / 'public/inputs/phantom.npz', **pub)
np.savez(HERE / 'hidden/phantom_hidden.npz', **hid)
print((pub['labels'] > 0).sum(), (hid['labels'] > 0).sum())
