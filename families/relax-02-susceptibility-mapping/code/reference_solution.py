#!/usr/bin/env python3
"""Reference solution for heldout-v4-qsm (multi-echo GRE -> local field -> susceptibility, ROI values).

Standalone entrypoint (same CLI as the requested qsm.py):
  python reference_solution.py --input-dir inputs --out-dir results
Build + grade the reference workspace: python reference_solution.py --build-validation
Pipeline: stored phase -> radians; consecutive-echo complex differences (removes the TE-independent phase offset);
SHARP background removal with a spherical-mean-value high-pass applied to the complex echo differences
(radius 5 mm, physical voxel size); truncated deconvolution; CG dipole inversion with gradient (Tikhonov)
regularisation and the oblique B0 direction / anisotropic voxels; Hz -> ppm; reference to ventricular CSF.
MODE selects the reference or a control variant (validation scripts only)."""
import argparse, json, os
from pathlib import Path
import numpy as np, nibabel as nib
from scipy import ndimage
MODE = 'reference'

def kgrid(shape, vox):
    return np.meshgrid(*[np.fft.fftfreq(n, d) for n, d in zip(shape, vox)], indexing='ij')

def dipole(shape, vox, b):
    k = kgrid(shape, vox); k2 = sum(q*q for q in k); kb = sum(q*bb for q, bb in zip(k, b))
    with np.errstate(invalid='ignore', divide='ignore'):
        D = 1/3 - kb*kb/k2
    D[0, 0, 0] = 0.0
    return D

def sphere_kernel(shape, vox, r_mm):
    c = [np.fft.fftfreq(n, 1.0/n)*d for n, d in zip(shape, vox)]       # wrapped coordinates in mm
    X = np.meshgrid(*c, indexing='ij')
    s = (sum(q*q for q in X) <= r_mm**2).astype(float)
    return np.real(np.fft.fftn(s/s.sum()))

def load(d):
    d = Path(d); acq = json.loads((d/'acquisition.json').read_text())
    mimg = nib.load(d/'gre_mag.nii.gz'); mag = np.asarray(mimg.get_fdata(), float)
    raw = np.asarray(nib.load(d/'gre_phase.nii.gz').get_fdata(), float)
    ph = raw if MODE == 'neg_phase_raw_int' else raw*np.pi/4096.0
    mask = np.asarray(nib.load(d/'brain_mask.nii.gz').get_fdata()) > 0
    roi = np.asarray(nib.load(d/'rois.nii.gz').get_fdata()).round().astype(int)
    return mimg, mag, ph, mask, roi, acq

def local_field(mag, ph, mask, acq, vox):
    tes = np.asarray(acq['echo_times_s'], float)
    s = mag*np.exp(1j*ph)
    if MODE == 'neg_sign_flip':
        s = np.conj(s)
    pad = [16, 16, 16]
    sp = np.pad(s, [(p, p) for p in pad] + [(0, 0)])
    mp = np.pad(mask, [(p, p) for p in pad])
    shape = mp.shape
    r = 5.0
    K = sphere_kernel(shape, vox, r)
    er = np.real(np.fft.ifftn(np.fft.fftn(mp.astype(float))*K)) > 0.999      # mask eroded by the sphere
    if MODE == 'neg_no_background_removal':
        num = 0; den = 0
        for e in range(len(tes) - 1):
            p = sp[..., e + 1]*np.conj(sp[..., e]); num = num + np.angle(p); den = den + 2*np.pi*(tes[e + 1] - tes[e])
        f = num/den*er
        return f[tuple(slice(p, -p) for p in pad)], er[tuple(slice(p, -p) for p in pad)]
    hp = 0.0; w = 0.0
    for e in range(len(tes) - 1):
        p = sp[..., e + 1]*np.conj(sp[..., e])
        p = p/np.maximum(np.abs(p), 1e-12)*mp
        sm = np.fft.ifftn(np.fft.fftn(p)*K)
        hp = hp + np.angle(p*np.conj(sm))/(2*np.pi*(tes[e + 1] - tes[e])); w += 1
    hp = hp/w*er
    den = 1.0 - K
    inv = np.where(np.abs(den) > 0.05, 1.0/np.where(np.abs(den) > 0.05, den, 1.0), 0.0)
    fl = np.real(np.fft.ifftn(np.fft.fftn(hp)*inv))*er
    un = tuple(slice(p, -p) for p in pad)
    return fl[un], er[un]

def invert(fl_ppm, m, vox, b, lam=2e-3, iters=80):
    pad = 16
    f = np.pad(fl_ppm, pad); W = np.pad(m, pad).astype(float); shape = f.shape
    D = dipole(shape, vox, b)
    if MODE == 'pos_tkd':
        thr = 0.19
        Di = np.where(np.abs(D) > thr, 1.0/np.where(np.abs(D) > thr, D, 1.0), np.sign(D)/thr)
        x = np.real(np.fft.ifftn(np.fft.fftn(f)*Di))
        return x[pad:-pad, pad:-pad, pad:-pad]
    k = kgrid(shape, vox)
    L = sum((2 - 2*np.cos(2*np.pi*q*d))/(d*d) for q, d in zip(k, vox))      # -Laplacian symbol (finite differences)
    if MODE == 'pos_closed_form_tikhonov':
        den = D*D + 0.008*L*(vox[0]**2); den[0, 0, 0] = 1.0
        x = np.real(np.fft.ifftn(D*np.fft.fftn(f)/den))
        return x[pad:-pad, pad:-pad, pad:-pad]
    Dop = lambda x: np.real(np.fft.ifftn(D*np.fft.fftn(x)))
    A = lambda x: Dop(W*Dop(x)) + lam*np.real(np.fft.ifftn(L*np.fft.fftn(x)))
    bvec = Dop(W*f)
    x = np.zeros(shape); r = bvec - A(x); p = r.copy(); rs = (r*r).sum()
    for _ in range(iters):
        Ap = A(p); a = rs/(p*Ap).sum(); x += a*p; r -= a*Ap; rn = (r*r).sum()
        if rn < 1e-12*(bvec*bvec).sum():
            break
        p = r + rn/rs*p; rs = rn
    return x[pad:-pad, pad:-pad, pad:-pad]

def analyse(input_dir, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    mimg, mag, ph, mask, roi, acq = load(input_dir)
    vox = [float(v) for v in acq['voxel_size_mm']]
    b = np.asarray(acq['b0_direction_voxel_axes'], float); b = b/np.linalg.norm(b)
    if MODE == 'neg_isotropic_voxel':
        vox = [1.0, 1.0, 1.0]
    if MODE == 'neg_wrong_b0_direction':
        b = np.array([0.0, 0.0, 1.0])
    fl, m = local_field(mag, ph, mask, acq, vox)
    gam = acq['gamma_bar_Hz_per_T']*(2*np.pi if MODE == 'neg_hz_to_ppm_rad' else 1.0)
    fl_ppm = fl/(gam*acq['field_strength_T'])*1e6
    chi = invert(fl_ppm, m, vox, b)*mask
    chi = (chi - chi[(roi == 7) & m].mean())*mask
    nib.save(nib.Nifti1Image(chi.astype(np.float32), mimg.affine), out/'chi_ppm.nii.gz')
    nib.save(nib.Nifti1Image((fl*m).astype(np.float32), mimg.affine), out/'local_field_hz.nii.gz')
    names = acq['roi_labels']
    res = {k: {'name': v, 'mean_chi_ppm': float(chi[(roi == int(k)) & m].mean()) if ((roi == int(k)) & m).any() else None,
               'n_voxels': int(((roi == int(k)) & m).sum())} for k, v in names.items()}
    (out/'roi_results.json').write_text(json.dumps({'reference_region': 'lateral_ventricles_csf', 'rois': res}, indent=1))
    return res

def main(argv=None):
    ap = argparse.ArgumentParser(description='Multi-echo GRE QSM')
    ap.add_argument('--input-dir'); ap.add_argument('--out-dir'); ap.add_argument('--build-validation', action='store_true')
    a = ap.parse_args(argv)
    if a.build_validation:
        return build_validation()
    analyse(a.input_dir, a.out_dir)

ARGS = ['--input-dir', 'inputs', '--out-dir', 'results']

def run_case(name, entry_text):
    import sys, shutil
    here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
    import validation_harness as H
    ws = H.make_ws('qsm', name)
    (ws/'qsm.py').write_text(entry_text)
    shutil.copytree(here.parent/'public/inputs', ws/'inputs')
    H.run_entry_public(ws, 'qsm.py', ARGS)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    c = nib.load(ws/'results/chi_ppm.nii.gz').get_fdata(); f = nib.load(ws/'results/local_field_hz.nii.gz').get_fdata()
    k = c.shape[2]//2 + 2
    fig, ax = plt.subplots(1, 2, figsize=(8, 4))
    ax[0].imshow(f[:, :, k].T, origin='lower', cmap='gray', vmin=-3, vmax=3); ax[0].set_title('local field (Hz)')
    ax[1].imshow(c[:, :, k].T, origin='lower', cmap='gray', vmin=-0.1, vmax=0.2); ax[1].set_title('chi (ppm)')
    fig.savefig(ws/'results/qsm.png', dpi=70); plt.close(fig)
    H.basic_docs(ws, 'QSM (%s)' % name, 'echo differences, SHARP, CG Tikhonov dipole inversion')
    (ws/'report.json').write_text(json.dumps({'method': 'complex echo differences; SHARP (5 mm); CG gradient-regularised dipole inversion',
        'software': {'numpy': np.__version__, 'nibabel': nib.__version__}, 'validation_summary': 'synthetic checks',
        'limitations': ['regularisation biases small structures low', 'SHARP erodes the brain edge']}, indent=1))
    shutil.move(str(ws/'inputs'), str(H.fresh(H.TMPROOT/'_trash'/('qsm_in_' + name + os.urandom(3).hex()))))
    return ws, H.grade_ws('qsm', name, ws)

def build_validation():
    import shutil
    here = Path(__file__).resolve().parent
    from validation_harness import summarize, fresh, TMPROOT
    ws, g = run_case('reference', Path(__file__).read_text())
    dst = here/'validation'/'reference_ws'
    if dst.exists():
        shutil.move(str(dst), str(fresh(TMPROOT/'_trash'/('refws_' + os.urandom(3).hex()))))
    shutil.copytree(ws, dst, ignore=shutil.ignore_patterns('.venv'), symlinks=True)
    s = summarize('reference', g); print(json.dumps(s))
    (here/'validation'/'reference_summary.json').write_text(json.dumps(s, indent=1))

if __name__ == '__main__':
    main()

