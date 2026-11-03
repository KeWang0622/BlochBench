#!/usr/bin/env python3
"""Generate public phantom and hidden phantom for heldout-v5-irt1 (deterministic)."""
import json, hashlib
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
N = 40; FOV = 0.200; DX = FOV / N

def phantom(body, vials, t1_body, t2_body, rho_body, rot_rad=0.0):
    idx = np.arange(N) - N // 2
    Y, X = np.meshgrid(idx * DX, idx * DX, indexing='ij')
    c, s = np.cos(rot_rad), np.sin(rot_rad)
    u = c * X + s * Y; v = -s * X + c * Y
    lab = np.zeros((N, N), np.int16)
    a, b, cx, cy = body
    lab[((u - cx) / a) ** 2 + ((v - cy) / b) ** 2 <= 1] = 1
    t1 = np.zeros((N, N)); t2 = np.zeros((N, N)); rho = np.zeros((N, N))
    t1[lab == 1] = t1_body; t2[lab == 1] = t2_body; rho[lab == 1] = rho_body
    for k, (vx, vy, r, T1, T2, pd) in enumerate(vials):
        m = ((X - vx) ** 2 + (Y - vy) ** 2 <= r ** 2) & (lab == 1)
        lab[m] = k + 2; t1[m] = T1; t2[m] = T2; rho[m] = pd
    return dict(x_m=X, y_m=Y, z_m=np.zeros_like(X), density=rho, T1_s=t1, T2_s=t2, B0_Hz=np.zeros_like(X), labels=lab)

def main():
    pub = TASK / 'public' / 'inputs'; pub.mkdir(parents=True, exist_ok=True)
    hid = HERE / 'hidden'; hid.mkdir(exist_ok=True)
    ring = lambda c, R, angs: [(c[0] + R * np.cos(np.radians(a)), c[1] + R * np.sin(np.radians(a))) for a in angs]
    pv = ring((-0.002, 0.003), 0.045, (35, 107, 179, 251, 323))
    p = phantom((0.082, 0.072, -0.002, 0.003), [(-0.002, 0.003, 0.0150, 0.58, 0.060, 1.00)] + [
        (x, y, 0.0150, T1, T2, pd) for (x, y), T1, T2, pd in zip(pv, (1.92, 0.40, 1.22, 0.85, 1.55),
                                                                  (0.150, 0.045, 0.100, 0.080, 0.120), (0.85, 0.95, 0.90, 1.00, 0.90))],
        1.10, 0.080, 0.75, rot_rad=-0.35)
    np.savez_compressed(pub / 'phantom.npz', **p)
    hv = ring((0.004, -0.003), 0.040, (60, 150, 240, 330))
    h = phantom((0.078, 0.085, 0.004, -0.003), [
        (x, y, 0.0160, T1, T2, pd) for (x, y), T1, T2, pd in zip(hv, (1.80, 0.50, 1.30, 0.75),
                                                                  (0.140, 0.050, 0.110, 0.070), (0.95, 0.90, 1.00, 0.85))],
        0.90, 0.085, 0.80, rot_rad=0.4)
    np.savez_compressed(hid / 'phantom_hidden.npz', **h)
    sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
    (HERE / 'public_inputs_manifest.json').write_text(json.dumps({'phantom.npz': sha(pub / 'phantom.npz')}, indent=1))
    print({k: int((p['labels'] == k).sum()) for k in range(8)}, {k: int((h['labels'] == k).sum()) for k in range(6)})

if __name__ == '__main__':
    main()

