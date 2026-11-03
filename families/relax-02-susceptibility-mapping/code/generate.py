#!/usr/bin/env python3
"""Generate heldout-v4-qsm datasets (public + hidden), fixed seeds.

Numerical head: air outside the head and in a sinus (chi = +9.4 ppm relative to water/tissue), scalp/skull/CSF
(0), brain with WM (-0.03), cortex (+0.01), deep grey nuclei (+0.03 ... +0.18 ppm) and ventricles (CSF, 0).
Total field = dipole convolution (oblique B0 direction, anisotropic voxels) computed on a zero-padded grid.
Multi-echo complex GRE: m*exp(-TE*R2*)*exp(i*(phi0 + 2*pi*f*TE)) + noise; phase stored as int16, value*pi/4096."""
import json
from pathlib import Path
import numpy as np, nibabel as nib
from scipy import ndimage
HERE = Path(__file__).resolve().parent
GBAR = 42.577478e6
NAMES = {1: 'caudate', 2: 'putamen', 3: 'globus_pallidus', 4: 'thalamus', 5: 'red_nucleus', 6: 'substantia_nigra',
         7: 'lateral_ventricles_csf', 8: 'white_matter'}
CHI = {1: 0.07, 2: 0.065, 3: 0.18, 4: 0.02, 5: 0.12, 6: 0.15, 7: 0.0}

def dipole_kernel(shape, vox, b):
    k = np.meshgrid(*[np.fft.fftfreq(n, d) for n, d in zip(shape, vox)], indexing='ij')
    k2 = sum(q*q for q in k); kb = sum(q*bb for q, bb in zip(k, b))
    with np.errstate(invalid='ignore', divide='ignore'):
        D = 1/3 - kb*kb/k2
    D[0, 0, 0] = 0.0
    return D

def make(out, seed, shape, vox, b_dir, tes, b0=3.0, sigma=0.006, scale=1.0, shift_mm=(0, 0, 0)):
    rng = np.random.default_rng(seed)
    b = np.asarray(b_dir, float); b /= np.linalg.norm(b)
    c = [(np.arange(n) - n/2 + 0.5)*d for n, d in zip(shape, vox)]
    X, Y, Z = np.meshgrid(*c, indexing='ij')
    X = X - shift_mm[0]; Y = Y - shift_mm[1]; Z = Z - shift_mm[2]
    def ell(cx, cy, cz, a, bb, cc):
        return ((X - cx)/(a*scale))**2 + ((Y - cy)/(bb*scale))**2 + ((Z - cz)/(cc*scale))**2 <= 1
    head = ell(0, 0, 0, 68, 84, 61); sinus = ell(0, 56, -38, 16, 12, 10) | ell(0, 32, -49, 9, 8, 7) | ell(0, 63, -12, 8, 5, 6)
    brain = ell(0, -3, 7, 55, 70, 45) & ~ell(0, 56, -38, 30, 25, 22) & ~ell(0, 32, -49, 15, 14, 13) & ~ell(0, 63, -12, 13, 9, 10)
    lab = np.zeros(shape, np.uint8)
    wm = ell(0, -4, 8, 47, 61, 37) & brain
    lab[wm] = 8
    for sx in (-1, 1):
        lab[ell(sx*12, 16, 12, 5, 9.5, 7) & brain] = 1
        lab[ell(sx*25, 4, 2, 5, 13, 9.5) & brain] = 2
        lab[ell(sx*17.5, 2, -1, 4.2, 7, 5.5) & brain] = 3
        lab[ell(sx*9.5, -18, 6, 8, 10.5, 7.5) & brain] = 4
        lab[ell(sx*5, -15, -12, 3.6, 3.6, 3.4) & brain] = 5
        lab[ell(sx*11, -11, -19, 3.4, 7, 3.6) & brain] = 6
        lab[ell(sx*7, 3, 20, 4.2, 18, 5.5) & brain] = 7
    chi = np.zeros(shape)
    chi[brain] = 0.010                                   # cortex / grey matter default
    chi[lab == 8] = -0.030
    for k, v in CHI.items():
        chi[lab == k] = v
    chi_air = np.where(~head | sinus, 9.4, 0.0)
    pad = [n for n in shape]
    big = [2*n for n in shape]
    full = np.zeros(big); air = np.ones(big)*9.4                     # padding is air
    sl = tuple(slice(p//2, p//2 + n) for p, n in zip(pad, shape))
    full[sl] = chi + chi_air
    D = dipole_kernel(big, vox, b)
    field_ppm = np.real(np.fft.ifftn(D*np.fft.fftn(full)))[sl]
    brainonly = np.zeros(big); brainonly[sl] = np.where(brain, chi, 0.0)
    local_ppm = np.real(np.fft.ifftn(D*np.fft.fftn(brainonly)))[sl]
    hz = field_ppm*1e-6*GBAR*b0; local_hz = local_ppm*1e-6*GBAR*b0
    hz = hz - hz[brain].mean()
    sm = lambda s: ndimage.gaussian_filter(rng.standard_normal(shape), s)
    phi0 = 1.6*sm(14)/np.abs(sm(14)).max() + 0.3
    pd = np.where(head & ~sinus, 0.70, 0.0); pd[brain] = 0.84; pd[lab == 8] = 0.71; pd[lab == 7] = 1.0
    r2s = np.where(brain, 16.0, 26.0); r2s[lab == 8] = 20.0; r2s[lab == 7] = 3.0
    for k in (1, 2, 3, 5, 6):
        r2s[lab == k] = 24.0 + 75*CHI[k]
    mag = []; ph = []
    for te in tes:
        s = pd*np.exp(-te*r2s)*np.exp(1j*(phi0 + 2*np.pi*hz*te))
        s = s + sigma*(rng.standard_normal(shape) + 1j*rng.standard_normal(shape))
        mag.append(np.abs(s)); ph.append(np.angle(s))
    mag = np.stack(mag, -1); ph = np.stack(ph, -1)
    phint = np.clip(np.round(ph*4096/np.pi), -4096, 4095).astype(np.int16)
    out.mkdir(parents=True, exist_ok=True)
    aff = np.diag(list(vox) + [1.0])
    nib.save(nib.Nifti1Image((mag*1000).astype(np.float32), aff), out/'gre_mag.nii.gz')
    nib.save(nib.Nifti1Image(phint, aff), out/'gre_phase.nii.gz')
    nib.save(nib.Nifti1Image(brain.astype(np.uint8), aff), out/'brain_mask.nii.gz')
    roi = np.where(np.isin(lab, list(range(1, 9))), lab, 0).astype(np.uint8)
    roi[(roi == 8) & ~ndimage.binary_erosion(lab == 8, iterations=2)] = 0
    nib.save(nib.Nifti1Image(roi, aff), out/'rois.nii.gz')
    side = {'field_strength_T': b0, 'gamma_bar_Hz_per_T': GBAR, 'echo_times_s': [float(t) for t in tes],
            'voxel_size_mm': [float(v) for v in vox], 'b0_direction_voxel_axes': [float(q) for q in b],
            'phase_scaling': 'radians = stored_value * pi / 4096', 'phase_sign': 'phase(TE) = phi0 + 2*pi*f*TE; f > 0 for paramagnetic sources aligned with B0',
            'roi_labels': {str(k): v for k, v in NAMES.items()}}
    (out/'acquisition.json').write_text(json.dumps(side, indent=1))
    return {'chi_ppm': chi.astype(np.float32), 'labels': lab, 'roi': roi, 'brain': brain, 'local_hz': local_hz.astype(np.float32),
            'total_hz': hz.astype(np.float32)}

if __name__ == '__main__':
    tr = make(HERE.parent/'public/inputs', 7272, (112, 124, 60), (1.3, 1.4, 2.1), (0.40, 0.42, 1.0),
              [0.0036, 0.0081, 0.0126, 0.0171, 0.0216, 0.0261], shift_mm=(-2, 1.5, -1), sigma=0.0045)
    np.savez_compressed(HERE/'truth_public.npz', **tr)
    tr = make(HERE/'hidden/inputs', 9494, (100, 116, 64), (1.6, 1.5, 2.0), (-np.sin(np.deg2rad(14)), np.sin(np.deg2rad(18)), 1.0),
              [0.0045, 0.0105, 0.0165, 0.0225], scale=1.0, shift_mm=(2.5, -4, 3), sigma=0.0060)
    np.savez_compressed(HERE/'hidden/truth_hidden.npz', **tr)
    print('done')

