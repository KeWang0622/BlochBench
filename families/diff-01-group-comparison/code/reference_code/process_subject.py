#!/usr/bin/env python3
"""Standalone per-subject DTI pipeline (reference). Usage:
python process_subject.py --dwi dwi.nii.gz --sidecar dwi.json --labels labels.nii.gz --outdir OUT"""
import argparse, json
from pathlib import Path
import numpy as np, nibabel as nib
from dipy.core.gradients import gradient_table
from dipy.reconst.dti import TensorModel

OPT = {'frame': 'ras', 'bscale': True, 'drift': 'quadratic', 'fit': 'WLS', 'md_unit': 1e3, 'v1_world': True}

def run(dwi, sidecar, labels, outdir, opt=OPT):
    img = nib.load(dwi); data = np.asarray(img.dataobj, dtype=np.float64)
    lab = np.asarray(nib.load(labels).dataobj).astype(int)
    side = json.loads(Path(sidecar).read_text())
    if opt.get('hardcode_sidecar'):  # (negative control) fixed public gradient table
        side = json.loads((Path(__file__).resolve().parent / opt['hardcode_sidecar']).read_text())
    nom = np.asarray(side['NominalBValue_s_per_mm2'], float)
    g = np.asarray(side['DiffusionGradientDirection_LPS'], float)
    t = np.asarray(side['VolumeAcquisitionTime_s'], float)
    A = img.affine
    if opt['frame'] == 'ras':
        g = g * np.array([-1, -1, 1])
    elif opt['frame'] == 'voxel_noaffine':
        pass  # (negative control) treat as voxel frame then map to world
    elif opt['frame'] == 'voxel_proper':
        R = A[:3, :3] / np.linalg.norm(A[:3, :3], axis=0)
        g = (g * np.array([-1, -1, 1])) @ R  # RAS -> voxel axes (R orthogonal)
    n2 = (g ** 2).sum(1)
    b = nom * n2 if opt['bscale'] else nom * (n2 > 0)
    gu = np.where(n2[:, None] > 0, g / np.sqrt(np.maximum(n2, 1e-12))[:, None], 0.0)
    b0 = b < 50
    brain = lab > 0
    if opt['drift'] in ('quadratic', 'linear', 'interp'):
        s = np.array([data[..., i][brain].mean() for i in range(data.shape[-1])])
        if opt['drift'] == 'interp':
            d = np.interp(t, t[b0], s[b0])
        else:
            deg = 2 if (opt['drift'] == 'quadratic' and b0.sum() >= 3) else 1
            c = np.polyfit(t[b0], s[b0], deg); d = np.polyval(c, t)
        data = data / (d / d[0])
    elif opt['drift'] == 'allvol':
        s = np.array([data[..., i][brain].mean() for i in range(data.shape[-1])])
        c = np.polyfit(t, s, 2); d = np.polyval(c, t); data = data / (d / d[0])
    gt = gradient_table(b, bvecs=gu, b0_threshold=50)
    fit = TensorModel(gt, fit_method=opt['fit']).fit(data, mask=brain)
    fa = np.nan_to_num(fit.fa); md = np.nan_to_num(fit.md) * opt['md_unit']
    v1 = np.nan_to_num(fit.evecs[..., :, 0])
    if opt['frame'] in ('voxel_noaffine', 'voxel_proper'):
        R = A[:3, :3] / np.linalg.norm(A[:3, :3], axis=0)
        v1 = v1 @ R.T
    if not opt['v1_world']:
        R = A[:3, :3] / np.linalg.norm(A[:3, :3], axis=0)
        v1 = v1 @ R  # world -> voxel axes (negative control)
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(fa.astype(np.float32), A), str(out / 'fa.nii.gz'))
    nib.save(nib.Nifti1Image(md.astype(np.float32), A), str(out / 'md.nii.gz'))
    nib.save(nib.Nifti1Image(v1.astype(np.float32), A), str(out / 'v1_ras.nii.gz'))
    res = {'labels': {}, 'effective_b_s_per_mm2': b.tolist()}
    for k in range(1, 5):
        m = lab == k
        e = {'fa': float(fa[m].mean()), 'md_um2_per_ms': float(md[m].mean()), 'n_voxels': int(m.sum())}
        if k in (1, 2):
            dy = np.einsum('ni,nj->ij', v1[m], v1[m]); w, V = np.linalg.eigh(dy); u = V[:, 2]
            e['v1_ras'] = (u * np.sign(u[np.argmax(np.abs(u))])).tolist()
        res['labels'][str(k)] = e
    (out / 'results.json').write_text(json.dumps(res, indent=1) + '\n')
    return res

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for a in ['--dwi', '--sidecar', '--labels', '--outdir']:
        ap.add_argument(a, required=True)
    a = ap.parse_args(); run(a.dwi, a.sidecar, a.labels, a.outdir)

