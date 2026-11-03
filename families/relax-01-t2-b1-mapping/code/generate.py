#!/usr/bin/env python3
"""Generate public and hidden data for heldout-v4-t2epg (fixed seeds).
CPMG multi-echo spin-echo magnitude data simulated with the extended phase graph (EPG) model,
B1+-scaled hard excitation and refocusing pulses, tissue T1, and Rician noise."""
import json
from pathlib import Path
import numpy as np
import nibabel as nib

HERE = Path(__file__).resolve().parent
TASK = HERE.parent


def rot(alpha, phi):
    """EPG rotation matrices for flip alpha (rad, array [V]) about an axis at phase phi (rad)."""
    c2 = np.cos(alpha / 2) ** 2; s2 = np.sin(alpha / 2) ** 2; s = np.sin(alpha); c = np.cos(alpha)
    e1 = np.exp(1j * phi); e2 = np.exp(2j * phi)
    T = np.empty(alpha.shape + (3, 3), complex)
    T[..., 0, 0] = c2; T[..., 0, 1] = e2 * s2; T[..., 0, 2] = -1j * e1 * s
    T[..., 1, 0] = np.conj(e2) * s2; T[..., 1, 1] = c2; T[..., 1, 2] = 1j * np.conj(e1) * s
    T[..., 2, 0] = -0.5j * np.conj(e1) * s; T[..., 2, 1] = 0.5j * e1 * s; T[..., 2, 2] = c
    return T


def epg_cpmg(T2, T1, B1, esp, n_echo, refoc_deg, exc_deg=90.0):
    """Echo magnitudes (M0 = 1) of a CPMG train. All inputs broadcast to [V]."""
    T2, T1, B1 = np.broadcast_arrays(np.atleast_1d(T2).astype(float), np.atleast_1d(T1).astype(float), np.atleast_1d(B1).astype(float))
    V = T2.size; T2 = T2.ravel(); T1 = T1.ravel(); B1 = B1.ravel()
    ns = 2 * n_echo + 3
    F = np.zeros((V, 3, ns), complex); F[:, 2, 0] = 1.0
    Te = rot(np.deg2rad(exc_deg) * B1, np.pi / 2)
    Tr = rot(np.deg2rad(refoc_deg) * B1, 0.0)
    E2 = np.exp(-esp / 2 / T2)[:, None]; E1 = np.exp(-esp / 2 / T1)[:, None]

    def apply(T, F):
        return np.einsum('vij,vjs->vis', T, F)

    def relax_shift(F):
        F = F.copy()
        F[:, 0:2, :] *= E2[:, :, None]
        F[:, 2, :] *= E1
        F[:, 2, 0] += (1 - E1[:, 0])
        Fp = np.roll(F[:, 0, :], 1, axis=1); Fm = np.roll(F[:, 1, :], -1, axis=1)
        Fm[:, -1] = 0
        Fp[:, 0] = np.conj(Fm[:, 0])
        F[:, 0, :] = Fp; F[:, 1, :] = Fm
        return F

    F = apply(Te, F)
    out = np.zeros((V, n_echo))
    for n in range(n_echo):
        F = relax_shift(F); F = apply(Tr, F); F = relax_shift(F)
        out[:, n] = np.abs(F[:, 0, 0])
    return out


def phantom(shape, seed, t2_ms, t1_s, centres, radii, b1_range):
    rng = np.random.default_rng(seed)
    nx, ny, nz = shape
    x, y, z = np.meshgrid(np.linspace(-1, 1, nx), np.linspace(-1, 1, ny), np.linspace(-1, 1, nz), indexing='ij')
    lab = np.zeros(shape, np.int16)
    body = (x / 0.9) ** 2 + (y / 0.78) ** 2 <= 1
    lab[body] = 1
    for k, ((cx, cy), r) in enumerate(zip(centres, radii)):
        lab[((x - cx) ** 2 + (y - cy) ** 2) <= r ** 2] = k + 2
    # smooth within-label variation of T2 (+-4 %) and proton density
    def smooth_field(a):
        f = sum(rng.normal() * np.cos(np.pi * (i * x + j * y) / 2 + rng.uniform(0, 2 * np.pi)) for i in range(3) for j in range(3))
        f = (f - f.mean()) / (np.abs(f).max() + 1e-9)
        return a * f
    T2 = np.zeros(shape); T1 = np.zeros(shape); PD = np.zeros(shape)
    var = smooth_field(0.04)
    for k in range(1, len(t2_ms) + 1):
        m = lab == k
        T2[m] = t2_ms[k - 1] * 1e-3 * (1 + var[m]); T1[m] = t1_s[k - 1]; PD[m] = 0.75 + 0.25 * rng.uniform()
    PD = PD * (1 + smooth_field(0.05)) * (lab > 0)
    # smooth B1+ scale field
    c = rng.uniform(-0.4, 0.4, 3)
    b = 1 - 0.9 * ((x - c[0]) ** 2 * 0.8 + (y - c[1]) ** 2 + 0.3 * (z - c[2]) ** 2) + 0.15 * x * y
    bb = b[lab > 0]
    b = np.clip((b - bb.min()) / (bb.max() - bb.min()), 0, 1)
    B1 = b1_range[0] + (b1_range[1] - b1_range[0]) * b
    return lab, T2, T1, PD, B1


def make(case, seed, shape, esp, n_echo, refoc, t2_ms, t1_s, centres, radii, b1_range, sigma, affine, outdir, truthfile):
    rng = np.random.default_rng(seed + 1000)
    lab, T2, T1, PD, B1 = phantom(shape, seed, t2_ms, t1_s, centres, radii, b1_range)
    sig = np.zeros(shape + (n_echo,))
    m = lab > 0
    sig[m] = epg_cpmg(T2[m], T1[m], B1[m], esp, n_echo, refoc) * (1000.0 * PD[m])[:, None]
    noisy = np.abs(sig + rng.normal(0, sigma, sig.shape) + 1j * rng.normal(0, sigma, sig.shape))
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    img = nib.Nifti1Image(noisy.astype(np.float32), affine)
    img.header.set_xyzt_units('mm', 'sec')
    nib.save(img, str(outdir / 'mese.nii.gz'))
    nib.save(nib.Nifti1Image(lab.astype(np.int16), affine), str(outdir / 'labels.nii.gz'))
    acq = {
        'SequenceName': 'CPMG multi-echo spin echo (3D, non-selective hard pulses)',
        'EchoSpacing_s': esp,
        'EchoTime_s': [round(esp * (i + 1), 6) for i in range(n_echo)],
        'NumberOfEchoes': n_echo,
        'ExcitationFlipAngle_deg': 90.0,
        'RefocusingFlipAngle_deg': refoc,
        'RefocusingPhase': 'CPMG: refocusing pulses applied about an axis 90 deg from the excitation axis',
        'AssumedT1_s': 1.25,
        'MagnitudeData': True,
    }
    (outdir / 'acquisition.json').write_text(json.dumps(acq, indent=1) + '\n')
    np.savez_compressed(truthfile, labels=lab, T2=T2, T1=T1, PD=PD, B1=B1, affine=affine, sigma=sigma)


def aff(vox, rotdeg, shift):
    t = np.deg2rad(rotdeg)
    R = np.array([[np.cos(t), -np.sin(t), 0], [np.sin(t), np.cos(t), 0], [0, 0, 1]])
    A = np.eye(4); A[:3, :3] = R @ np.diag(vox); A[:3, 3] = shift
    return A


if __name__ == '__main__':
    make('public', 83, (92, 104, 4), 0.0095, 30, 165.0, [76, 44, 105, 140, 210], [1.10, 0.95, 1.30, 1.45, 1.60],
         [(0.36, 0.34), (-0.42, 0.18), (0.12, -0.44), (-0.28, -0.3)], [0.15, 0.17, 0.16, 0.15],
         (0.45, 1.05), 2.1, aff([2.1, 1.9, 4.0], 9, [-96, -99, -8]), TASK / 'public/inputs', HERE / 'truth_public.npz')
    make('hidden', 71, (86, 94, 4), 0.012, 26, 155.0, [52, 34, 90, 120, 245], [1.0, 0.92, 1.2, 1.4, 1.58],
         [(-0.38, -0.32), (0.42, -0.05), (-0.05, 0.4), (0.3, -0.38)], [0.16, 0.15, 0.17, 0.15],
         (0.60, 1.15), 2.0, aff([2.5, 2.2, 3.6], -15, [-108, -103, -7]), HERE / 'hidden/inputs', HERE / 'hidden/truth_hidden.npz')
    print('done')
