#!/usr/bin/env python3
"""Generate public inputs and hidden data for heldout-v5-dwigroup (fixed seeds)."""
import json, sys
from pathlib import Path
import numpy as np, nibabel as nib

HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'
HID = HERE / 'hidden'
SHAPE = (50, 44, 16)
VOX = 2.0
SIGMA = 16.0

def rotmat(ax, ay, az):
    ax, ay, az = np.deg2rad([ax, ay, az])
    Rx = np.array([[1,0,0],[0,np.cos(ax),-np.sin(ax)],[0,np.sin(ax),np.cos(ax)]])
    Ry = np.array([[np.cos(ay),0,np.sin(ay)],[0,1,0],[-np.sin(ay),0,np.cos(ay)]])
    Rz = np.array([[np.cos(az),-np.sin(az),0],[np.sin(az),np.cos(az),0],[0,0,1]])
    return Rz @ Ry @ Rx

def hemi_dirs(n, rng):
    # Fibonacci directions on a hemisphere, randomly rotated (scanner LPS frame)
    i = np.arange(n) + 0.5
    z = 1 - i / n
    phi = np.pi * (1 + 5 ** 0.5) * i
    r = np.sqrt(1 - z ** 2)
    d = np.stack([r * np.cos(phi), r * np.sin(phi), z], 1)
    R = rotmat(*rng.uniform(-180, 180, 3))
    d = d @ R.T
    d *= np.sign(d[:, 2:3] + 1e-9)
    return d / np.linalg.norm(d, axis=1, keepdims=True)

def protocol(rng, n_per_shell, scale2, n_between, nominal=1200.0, n_start=2):
    """Return list of (nominal_b, g_LPS) in acquisition order; b0 interspersed."""
    lo = hemi_dirs(n_per_shell, rng) * np.sqrt(scale2)
    hi = hemi_dirs(n_per_shell, rng)
    dw = list(lo) + list(hi)          # shells acquired sequentially, low shell first
    vols = [(0.0, np.zeros(3))] * n_start   # b=0 volumes at the start
    for k, g in enumerate(dw):
        vols.append((nominal, g))
        if (k + 1) % n_between == 0:
            vols.append((0.0, np.zeros(3)))   # interspersed b=0
    if vols[-1][0] != 0.0:
        vols.append((0.0, np.zeros(3)))
    return vols

def smooth_field(rng, shape, amp, sm=3.0):
    from scipy.ndimage import gaussian_filter
    f = gaussian_filter(rng.standard_normal(shape), sm)
    return amp * f / (f.std() + 1e-12)

def cyl(ijk, c, a, rad):
    a = np.asarray(a, float); a /= np.linalg.norm(a)
    d = ijk - np.asarray(c, float)
    proj = d @ a
    perp = d - proj[..., None] * a
    return np.linalg.norm(perp, axis=-1) <= rad

def tensor_from(evals, v1, rng_perp):
    v1 = v1 / np.linalg.norm(v1, axis=-1, keepdims=True)
    t = rng_perp - (rng_perp * v1).sum(-1, keepdims=True) * v1
    v2 = t / np.linalg.norm(t, axis=-1, keepdims=True)
    v3 = np.cross(v1, v2)
    E = np.stack([v1, v2, v3], -1)  # columns
    return np.einsum('...ik,...k,...jk->...ij', E, evals, E)

def fa_md(D):
    w = np.linalg.eigvalsh(D)
    md = w.mean(-1)
    fa = np.sqrt(1.5 * ((w - md[..., None]) ** 2).sum(-1) / (w ** 2).sum(-1))
    return fa, md

def make_subject(seed, group, prot, affine_angles, flip_x, ttot):
    rng = np.random.default_rng(seed)
    nx, ny, nz = SHAPE
    ijk = np.stack(np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing='ij'), -1).astype(float)
    c = np.array([24.5, 21.5, 7.5]) + rng.uniform(-1, 1, 3) * [1, 1, 0.3]
    u = (ijk - c) / [22.5, 19.5, 7.8]
    brain = (u ** 2).sum(-1) <= 1
    lab = np.zeros(SHAPE, np.int16)
    lab[brain] = 5
    ax1 = np.array([0.7, 0.8, -0.25]) + rng.normal(0, 0.05, 3)
    ax2 = np.array([0.95, -0.35, 0.3]) + rng.normal(0, 0.05, 3)
    m1 = cyl(ijk, c + [6.0, -5.0, 0], ax1, 2.8) & brain
    m2 = cyl(ijk, c + [-5.0, 7.0, 0], ax2, 2.6) & brain & ~m1
    m3 = ((((ijk - (c + [-7, -6, 0])) / [3.7, 3.3, 2.6]) ** 2).sum(-1) <= 1) & brain & ~m1 & ~m2
    m4 = ((((ijk - (c + [2, 2, 0])) / [4.2, 3.6, 2.4]) ** 2).sum(-1) <= 1) & brain & ~m1 & ~m2 & ~m3
    for k, m in zip([1, 2, 3, 4], [m1, m2, m3, m4]):
        lab[m] = k
    # affine: voxel -> RAS mm
    R = rotmat(*affine_angles)
    S = np.diag([-VOX if flip_x else VOX, VOX, VOX])
    A = np.eye(4); A[:3, :3] = R @ S
    A[:3, 3] = -(A[:3, :3] @ np.array([24.5, 21.5, 7.5])) + rng.uniform(-7, 7, 3)
    Rw = A[:3, :3] / VOX  # orthogonal (possibly improper)
    # tissue parameters (eigenvalues um^2/ms), subject random effects
    se = lambda: 1 + rng.normal(0, 0.03)
    rad1 = 0.29 * (1.12 if group == 'patient' else 1.0) * se()
    pars = {1: (1.74 * (0.94 if group == 'patient' else 1.0) * se(), rad1, rad1), 2: (1.46 * se(), 0.38 * se(), 0.31 * se()),
            3: (0.90 * se(), 0.76 * se(), 0.66 * se()), 4: (3.00 * se(), 2.92 * se(), 2.84 * se()),
            5: (1.05, 0.60, 0.49)}
    s0v = {1: 860., 2: 900., 3: 1040., 4: 1600., 5: 940.}
    D = np.zeros(SHAPE + (3, 3)); S0 = np.zeros(SHAPE)
    vf = 1 + smooth_field(rng, SHAPE, 0.03)
    perp = rng.standard_normal(SHAPE + (3,))
    for k in range(1, 6):
        m = lab == k
        if not m.any():
            continue
        ev = np.array(pars[k])[None, :] * vf[m][:, None]
        if k == 1:
            v1 = np.tile(Rw @ (ax1 / np.linalg.norm(ax1)), (m.sum(), 1))
        elif k == 2:
            v1 = np.tile(Rw @ (ax2 / np.linalg.norm(ax2)), (m.sum(), 1))
        else:
            v1 = rng.standard_normal((m.sum(), 3))
        if k in (1, 2):
            v1 = v1 + rng.normal(0, 0.05, v1.shape)  # ~3 deg dispersion
        D[m] = tensor_from(ev, v1, perp[m])
        S0[m] = s0v[k] * (1 + smooth_field(rng, SHAPE, 0.04)[m])
    # signals
    nominal = np.array([p[0] for p in prot]); gl = np.array([p[1] for p in prot])
    g_ras = gl * np.array([-1, -1, 1])
    n2 = (g_ras ** 2).sum(1)
    beff = nominal * n2
    gu = np.where(n2[:, None] > 0, g_ras / np.sqrt(np.maximum(n2, 1e-12))[:, None], 0)
    adc = np.einsum('vi,...ij,vj->...v', gu, D, gu) * 1e-3  # mm^2/s
    sig = S0[..., None] * np.exp(-beff * adc)
    nvol = len(prot)
    times = np.linspace(0, ttot, nvol)
    tau = times / ttot
    c1 = rng.uniform(-0.20, -0.14); c2 = rng.uniform(0.02, 0.05)
    drift = 1 + c1 * tau + c2 * tau ** 2
    sig = sig * drift
    noisy = np.sqrt((sig + rng.normal(0, SIGMA, sig.shape)) ** 2 + rng.normal(0, SIGMA, sig.shape) ** 2)
    noisy = np.clip(np.round(noisy), 0, 65535).astype(np.uint16)
    # truth
    fa, md = fa_md(D)
    fa[lab == 0] = 0; md[lab == 0] = 0
    w, V = np.linalg.eigh(D)
    v1map = V[..., :, 2]
    v1map[lab == 0] = 0
    truth = {'group': group, 'labels': {}}
    for k in range(1, 5):
        m = lab == k
        ent = {'fa': float(fa[m].mean()), 'md_um2_per_ms': float(md[m].mean()), 'n_voxels': int(m.sum())}
        if k in (1, 2):
            dy = np.einsum('ni,nj->ij', v1map[m], v1map[m])
            ww, vv = np.linalg.eigh(dy); e = vv[:, 2]
            e = e * np.sign(e[np.argmax(np.abs(e))])
            ent['v1_ras'] = e.tolist()
        truth['labels'][str(k)] = ent
    truth['drift'] = {'c1': c1, 'c2': c2}
    img = nib.Nifti1Image(noisy, A); img.header.set_xyzt_units('mm', 'sec')
    limg = nib.Nifti1Image(lab, A)
    side = {
        'MagneticFieldStrength_T': 1.5,
        'ImageType': 'magnitude, integer scanner units, no preprocessing applied',
        'NominalBValue_s_per_mm2': nominal.tolist(),
        'DiffusionGradientDirection_LPS': [list(map(float, g)) for g in gl],
        'VolumeAcquisitionTime_s': times.round(3).tolist(),
        'AcquisitionOrder': 'volume index order equals acquisition order',
    }
    maps = {'fa': fa.astype(np.float32), 'md': md.astype(np.float32), 'v1': v1map.astype(np.float32)}
    return img, limg, side, truth, maps

def write(dirp, sid, img, limg, side):
    d = dirp / sid; d.mkdir(parents=True, exist_ok=True)
    nib.save(img, str(d / 'dwi.nii.gz')); nib.save(limg, str(d / 'labels.nii.gz'))
    (d / 'dwi.json').write_text(json.dumps(side, indent=1) + '\n')

def main():
    PUB.mkdir(parents=True, exist_ok=True); HID.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(60721)
    protA = protocol(rng, 16, 0.42, 8, nominal=1000.0, n_start=3)   # public protocol
    protB = protocol(rng, 14, 0.33, 7, nominal=1100.0, n_start=2)   # hidden protocol (different scheme)
    groups = ['control'] * 7 + ['patient'] * 7
    rng.shuffle(groups)
    truth_pub = {}; rows = ['participant_id\tgroup']
    for s in range(14):
        sid = 'sub-%02d' % (s + 1)
        ang = rng.uniform(-18, 18, 3); ang[np.argmax(np.abs(ang))] = np.sign(ang[np.argmax(np.abs(ang))]) * rng.uniform(12, 20)
        img, limg, side, tr, _ = make_subject(5100 + s, groups[s], protA, ang, s % 3 == 1, 330.0)
        write(PUB, sid, img, limg, side); truth_pub[sid] = tr
        rows.append(sid + '\t' + groups[s])
    (PUB / 'participants.tsv').write_text('\n'.join(rows) + '\n')
    fa = {g: [truth_pub[s]['labels']['1']['fa'] for s in truth_pub if truth_pub[s]['group'] == g] for g in ['control', 'patient']}
    md = {g: [truth_pub[s]['labels']['1']['md_um2_per_ms'] for s in truth_pub if truth_pub[s]['group'] == g] for g in ['control', 'patient']}
    grp = {'fa_label1_patient_minus_control': float(np.mean(fa['patient']) - np.mean(fa['control'])),
           'md_label1_patient_minus_control': float(np.mean(md['patient']) - np.mean(md['control']))}
    (HERE / 'truth_public.json').write_text(json.dumps({'subjects': truth_pub, 'group': grp}, indent=1) + '\n')
    truth_hid = {}
    for h, (grp_h, flip) in enumerate([('control', True), ('patient', True), ('control', False)]):
        sid = 'sub-h%d' % (h + 1)
        ang = rng.uniform(-22, 22, 3); ang[2] = rng.choice([-1, 1]) * rng.uniform(14, 22)
        img, limg, side, tr, maps = make_subject(9700 + h, grp_h, protB, ang, flip, 400.0)
        write(HID, sid, img, limg, side); truth_hid[sid] = tr
        np.savez_compressed(HID / sid / 'truth_maps.npz', **maps)
    (HID / 'truth_hidden.json').write_text(json.dumps(truth_hid, indent=1) + '\n')
    print(json.dumps(grp))

if __name__ == '__main__':
    main()

