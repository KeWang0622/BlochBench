#!/usr/bin/env python3
"""Generate public and hidden data for heldout-v5-t2study (fixed seeds).
Usage: python generate.py   (writes public/inputs and private/hidden)"""
import json, hashlib, csv
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
N = 72; FOV = 0.216; DX = FOV / N
NC = 12
MISSING_SCAN = 'sub-11_ses-2'   # second session not usable (coil failure); file absent
TE_MS = np.arange(1, 10) * 9.5
R = 3; NACS = 24

def sampling_mask():
    ky = np.arange(N)
    m = ((ky - N // 2) % R == 0) | (np.abs(ky - N // 2) < NACS // 2)
    return m

def fft2c(x):
    return np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(x, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))

def inside_ellipse(X, Y, cx, cy, a, b, ang=0.0):
    c, s = np.cos(ang), np.sin(ang)
    u = (X - cx) * c + (Y - cy) * s
    v = -(X - cx) * s + (Y - cy) * c
    return (u / a) ** 2 + (v / b) ** 2 <= 1.0

def make_scan(rng, subj, pose, coil_rng):
    """subj: dict of subject anatomy/T2; pose: (dx_m, dy_m, rot_rad). Returns dict."""
    idx = np.arange(N) - N // 2
    Yg, Xg = np.meshgrid(idx * DX, idx * DX, indexing='ij')   # [y,x]
    dx, dy, th = pose
    # object coordinates (inverse rigid transform of grid)
    c, s = np.cos(-th), np.sin(-th)
    Xo = c * (Xg - dx) - s * (Yg - dy)
    Yo = s * (Xg - dx) + c * (Yg - dy)
    sc = subj['scale']
    head = inside_ellipse(Xo, Yo, 0.0, 0.0, 0.069 * sc, 0.089 * sc)
    vent_l = inside_ellipse(Xo, Yo, -0.012 * sc, 0.024 * sc, 0.0060 * sc, 0.016 * sc, 0.25)
    vent_r = inside_ellipse(Xo, Yo, 0.012 * sc, 0.024 * sc, 0.0060 * sc, 0.016 * sc, -0.25)
    cis_l = inside_ellipse(Xo, Yo, -0.028 * sc, -0.068 * sc, 0.012 * sc, 0.0095 * sc, -0.15)
    cis_r = inside_ellipse(Xo, Yo, 0.028 * sc, -0.068 * sc, 0.012 * sc, 0.0095 * sc, 0.15)
    csf = (vent_l | vent_r | cis_l | cis_r) & head
    roi = (inside_ellipse(Xo, Yo, -0.028 * sc, 0.004 * sc, 0.0110 * sc, 0.0100 * sc, -0.15) |
           inside_ellipse(Xo, Yo, 0.028 * sc, 0.004 * sc, 0.0110 * sc, 0.0100 * sc, 0.15)) & head & ~csf
    brain = head & ~csf & ~roi
    labels = np.zeros((N, N), np.int16)
    labels[brain] = 2; labels[csf] = 3; labels[roi] = 1
    # T2 and PD maps (ms); smooth spatial variation defined in object coordinates
    t2 = np.zeros((N, N)); pd = np.zeros((N, N))
    wm_var = subj['wm_amp'] * np.cos(2 * np.pi * Xo / 0.11 + subj['ph1']) * np.cos(2 * np.pi * Yo / 0.16 + subj['ph2'])
    t2[brain] = subj['t2_brain'] + wm_var[brain]
    pd[brain] = 0.78 + 0.05 * np.cos(2 * np.pi * Xo[brain] / 0.17)
    t2[csf] = 900.0; pd[csf] = 1.0
    roi_var = subj['roi_amp'] * np.cos(2 * np.pi * Xo / 0.028 + subj['ph3']) * np.sin(2 * np.pi * Yo / 0.024)
    t2[roi] = subj['t2_roi'] + roi_var[roi]
    pd[roi] = 0.86
    # coil sensitivities: 8 coils on a ring, random rotation of the array and per-coil phase
    phi0 = coil_rng.uniform(0, 2 * np.pi)
    sens = np.zeros((NC, N, N), complex)
    for k in range(NC):
        ang = phi0 + 2 * np.pi * k / NC
        cx, cy = 0.135 * np.cos(ang), 0.150 * np.sin(ang)
        d2 = (Xg - cx) ** 2 + (Yg - cy) ** 2
        mag = np.exp(-d2 / (2 * 0.092 ** 2))
        phs = coil_rng.uniform(-np.pi, np.pi) + 25.0 * ((Xg - cx) * np.cos(ang + 1.0) + (Yg - cy) * np.sin(ang + 1.0)) * 0.3
        sens[k] = mag * np.exp(1j * phs)
    sens /= np.sqrt((np.abs(sens) ** 2).sum(0)).max() * 0.85
    # noise covariance (correlated)
    A = np.eye(NC)
    for k in range(NC):
        A[k, (k + 1) % NC] = 0.22; A[(k + 1) % NC, k] = 0.22
        A[k, (k + 2) % NC] = 0.06; A[(k + 2) % NC, k] = 0.06
    dvar = coil_rng.uniform(0.8, 1.25, NC)
    cov = np.sqrt(np.outer(dvar, dvar)) * A
    L = np.linalg.cholesky(cov)
    sigma = 0.0045
    mask = sampling_mask()
    ksp = np.zeros((len(TE_MS), NC, N, N), np.complex64)
    t2s = np.where(t2 > 0, t2, 1.0)
    for e, te in enumerate(TE_MS):
        img = pd * np.exp(-te / t2s)
        coil_imgs = sens * img[None]
        k = fft2c(coil_imgs)
        w = (rng.standard_normal((N, N, NC)) + 1j * rng.standard_normal((N, N, NC))) / np.sqrt(2)
        noise = sigma * (w @ L.T)
        k = k + np.moveaxis(noise, -1, 0)
        k[:, ~mask, :] = 0
        ksp[e] = k.astype(np.complex64)
    w = (rng.standard_normal((512, NC)) + 1j * rng.standard_normal((512, NC))) / np.sqrt(2)
    noise_prescan = (sigma * (w @ L.T)).astype(np.complex64)
    truth_roi = float(t2[labels == 1].mean())
    return dict(kspace=ksp, sampling_mask=mask, labels=labels, noise_prescan=noise_prescan,
                echo_times_ms=TE_MS.copy()), dict(t2_ms=t2.astype(np.float32), pd=pd.astype(np.float32), labels=labels,
                                                 roi_true_t2_ms=truth_roi, sens=sens.astype(np.complex64))

def subject_params(rng, group):
    mu = 82.0 if group == 'control' else 76.5
    return dict(scale=rng.uniform(0.95, 1.05), t2_brain=rng.normal(88.0, 2.0), wm_amp=rng.uniform(2, 5),
                ph1=rng.uniform(0, 6.3), ph2=rng.uniform(0, 6.3), ph3=rng.uniform(0, 6.3),
                roi_amp=rng.uniform(1.0, 2.5), t2_roi=rng.normal(mu, 2.4))

def pose(rng):
    return (rng.uniform(-0.004, 0.004), rng.uniform(-0.006, 0.006), np.deg2rad(rng.uniform(-6, 6)))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write_scan(path, data, scan_id):
    np.savez_compressed(path, scan_id=np.array(scan_id), **data)

def main():
    pub = TASK / 'public' / 'inputs'; (pub / 'scans').mkdir(parents=True, exist_ok=True)
    hid = HERE / 'hidden'; hid.mkdir(exist_ok=True)
    rng = np.random.default_rng(16180339)
    groups = ['control'] * 10 + ['patient'] * 8
    rng.shuffle(groups)
    parts = []; truth = {'scans': {}, 'subjects': {}}
    for i, g in enumerate(groups):
        sid = f'sub-{i + 1:02d}'
        sp = subject_params(rng, g)
        parts.append(dict(subject_id=sid, group=g, age=int(rng.integers(30, 70)), sex=str(rng.choice(['F', 'M']))))
        truth['subjects'][sid] = dict(group=g, t2_roi_param=sp['t2_roi'])
        for ses in (1, 2):
            data, tr = make_scan(rng, sp, pose(rng), np.random.default_rng(rng.integers(1 << 30)))
            scan_id = f'{sid}_ses-{ses}'
            if scan_id == MISSING_SCAN:
                continue
            write_scan(pub / 'scans' / f'{scan_id}.npz', data, scan_id)
            truth['scans'][scan_id] = dict(subject_id=sid, group=g, session=ses, roi_true_t2_ms=tr['roi_true_t2_ms'])
            np.savez_compressed(hid / f'truth_{scan_id}.npz', **{k: v for k, v in tr.items() if k != 'sens'})
    with open(pub / 'participants.tsv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['subject_id', 'group', 'age', 'sex'], delimiter='\t')
        w.writeheader(); [w.writerow(p) for p in parts]
    # hidden scans for the rerun of the mapping entrypoint
    hrng = np.random.default_rng(424242)
    hscans = {}
    for j, (g, t2r) in enumerate([('patient', 58.0), ('control', 75.0), ('patient', 92.0)]):
        sp = subject_params(hrng, g); sp['t2_roi'] = t2r; sp['t2_brain'] = [70.0, 86.0, 100.0][j]
        data, tr = make_scan(hrng, sp, pose(hrng), np.random.default_rng(hrng.integers(1 << 30)))
        scan_id = f'hidden-{j + 1}'
        write_scan(hid / f'{scan_id}.npz', data, scan_id)
        np.savez_compressed(hid / f'truth_{scan_id}.npz', **{k: v for k, v in tr.items() if k != 'sens'})
        hscans[scan_id] = dict(roi_true_t2_ms=tr['roi_true_t2_ms'])
    truth['hidden_scans'] = hscans
    # hidden tables for the statistics entrypoint (unbalanced, one subject with a single scan, shuffled rows)
    trng = np.random.default_rng(271828)
    tables = []
    for t, (nc, npat, miss) in enumerate([(8, 8, 'sub-h03'), (6, 11, 'sub-h12')]):
        rows = []
        for i in range(nc + npat):
            sid = f'sub-h{i + 1:02d}'; g = 'control' if i < nc else 'patient'
            m = trng.normal(82.0 if g == 'control' else 77.5 - t, 3.0)
            for ses in (1, 2):
                if sid == miss and ses == 2:
                    continue
                rows.append(dict(subject_id=sid, group=g, session=ses, roi_t2_ms=round(float(m + trng.normal(0, 1.0)), 4)))
        trng.shuffle(rows)
        p = hid / f'hidden_table_{t + 1}.csv'
        with open(p, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['subject_id', 'group', 'session', 'roi_t2_ms'])
            w.writeheader(); [w.writerow(r) for r in rows]
        tables.append(p.name)
    truth['hidden_tables'] = tables
    (hid / 'truth.json').write_text(json.dumps(truth, indent=1))
    man = {p.relative_to(pub).as_posix(): sha(p) for p in sorted(pub.rglob('*')) if p.is_file()}
    (HERE / 'public_inputs_manifest.json').write_text(json.dumps(man, indent=1))
    print('wrote', len(man), 'public files')

if __name__ == '__main__':
    main()

