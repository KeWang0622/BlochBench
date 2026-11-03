#!/usr/bin/env python3
"""Generate public/hidden phantoms, true fields and field-mapping scans for heldout-v5-spiralb0 (fixed seeds)."""
import json, hashlib
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; TASK = HERE.parent
N = 40; FOV = 0.216; DX = FOV / N
TE_FM = (0.0020, 0.0031)

def grid():
    idx = np.arange(N) - N // 2
    Y, X = np.meshgrid(idx * DX, idx * DX, indexing='ij')
    return X, Y

def phantom(body, vials, rho_b, t1_b, t2_b, field_coef, dipole):
    X, Y = grid()
    a, b, cx, cy = body
    lab = np.zeros((N, N), np.int16); lab[((X - cx) / a) ** 2 + ((Y - cy) / b) ** 2 <= 1] = 1
    rho = np.where(lab == 1, rho_b, 0.0); t1 = np.where(lab == 1, t1_b, 0.0); t2 = np.where(lab == 1, t2_b, 0.0)
    for k, (vx, vy, r, pd, T1, T2) in enumerate(vials):
        m = ((X - vx) ** 2 + (Y - vy) ** 2 <= r ** 2) & (lab == 1)
        lab[m] = k + 2; rho[m] = pd; t1[m] = T1; t2[m] = T2
    c0, gx, gy, q, xy = field_coef
    f = c0 + gx * X + gy * Y + q * (X ** 2 - Y ** 2) + xy * X * Y
    dx0, dy0, amp, rad = dipole            # 2D line-dipole perturbation centred outside the object
    r2 = (X - dx0) ** 2 + (Y - dy0) ** 2
    ang = np.arctan2(Y - dy0, X - dx0)
    f = f + amp * rad ** 2 / np.maximum(r2, rad ** 2) * np.cos(2 * ang)
    f = np.where(lab > 0, f, 0.0)          # field is only defined (and only matters) where there are spins
    return dict(x_m=X, y_m=Y, z_m=np.zeros_like(X), density=rho, T1_s=t1, T2_s=t2, B0_Hz=f, labels=lab)

def fieldmap_scan(ph, rng, snr=150.0):
    X, Y = grid()
    lab = ph['labels']
    mag = np.where(lab > 0, 0.6 + 0.4 * ph['density'], 0.0) * (1 + 0.10 * X / FOV)
    phi0 = 0.4 - 1.8 * X / FOV + 2.4 * Y / FOV + 2.5 * (X ** 2 + Y ** 2) / FOV ** 2
    sig = 1.0 / snr
    ims = []
    for te in TE_FM:
        im = mag * np.exp(1j * (phi0 - 2 * np.pi * ph['B0_Hz'] * te))
        im = im + sig * (rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))) / np.sqrt(2)
        ims.append(im)
    return dict(images=np.stack(ims).astype(np.complex64), echo_times_s=np.array(TE_FM))

def main():
    pub = TASK / 'public/inputs'; pub.mkdir(parents=True, exist_ok=True); hid = HERE / 'hidden'; hid.mkdir(exist_ok=True)
    p = phantom((0.086, 0.078, 0.003, -0.002), [
        (-0.040, 0.026, 0.0160, 0.75, 0.85, 0.070),
        (0.000, 0.046, 0.0160, 1.15, 0.95, 0.130),
        (0.040, 0.022, 0.0160, 0.60, 0.70, 0.055),
        (0.030, -0.034, 0.0160, 1.25, 1.05, 0.160),
        (-0.026, -0.038, 0.0160, 0.90, 0.75, 0.095)], 0.80, 0.85, 0.090,
        (-25.0, -1050.0, 1250.0, -16000.0, 14000.0), (0.118, -0.010, 125.0, 0.030))
    np.savez_compressed(pub / 'phantom.npz', **p)
    fm = fieldmap_scan(p, np.random.default_rng(52817))
    np.savez_compressed(pub / 'fieldmap_scan.npz', **fm)
    h = phantom((0.082, 0.080, -0.003, 0.002), [
        (-0.046, 0.000, 0.0160, 1.10, 0.80, 0.105),
        (-0.023, 0.040, 0.0160, 0.70, 0.90, 0.065),
        (0.023, 0.040, 0.0160, 1.30, 0.65, 0.145),
        (0.046, 0.000, 0.0160, 0.85, 1.00, 0.080),
        (0.023, -0.040, 0.0160, 0.60, 0.75, 0.120),
        (-0.023, -0.040, 0.0160, 1.20, 0.85, 0.055)], 0.75, 0.90, 0.100,
        (30.0, 950.0, 1050.0, 15500.0, -17000.0), (-0.020, -0.115, -150.0, 0.031))
    np.savez_compressed(hid / 'phantom_hidden.npz', **h)
    np.savez_compressed(hid / 'fieldmap_scan_hidden.npz', **fieldmap_scan(h, np.random.default_rng(90314)))
    sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
    (HERE / 'public_inputs_manifest.json').write_text(json.dumps({f.name: sha(f) for f in sorted(pub.iterdir())}, indent=1))
    for nm, ph in (('public', p), ('hidden', h)):
        f = ph['B0_Hz'][ph['labels'] > 0]
        print(nm, 'field range in object', f.min().round(1), f.max().round(1), {k: int((ph['labels'] == k).sum()) for k in range(9)})

if __name__ == '__main__':
    main()

