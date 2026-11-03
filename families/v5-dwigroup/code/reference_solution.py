#!/usr/bin/env python3
"""Reference solution for heldout-v5-dwigroup.
Builds a workspace in private/validation/ws_reference from private/reference_code, runs the
public pipeline, writes README/environment/QC, then grades it with grade_dwigroup_arm.py.
build_workspace() is reused by the negative/positive control scripts."""
import json, os, shutil, subprocess, sys, platform
from pathlib import Path
HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'
GPY = '/Users/kewang/Documents/Codex/2026-09-22/read-mri-talk-handoff-md-and/work/radial-gre-venv/bin/python'

def build_workspace(ws, opt=None, post=None, extra_files=None):
    ws = Path(ws)
    if ws.exists():
        tr = HERE / 'validation' / '_trash'; tr.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ws), str(tr / (ws.name + '_%d' % len(list(tr.iterdir())))))
    code = ws / 'code'; code.mkdir(parents=True)
    for f in ['process_subject.py', 'run_all.py']:
        shutil.copy2(HERE / 'reference_code' / f, code / f)
    if opt:
        s = (code / 'process_subject.py').read_text()
        s = s.replace("OPT = {", "OPT = {**{", 1).replace("'v1_world': True}", "'v1_world': True}, **" + repr(opt) + "}", 1)
        (code / 'process_subject.py').write_text(s)
    for name, content in (extra_files or {}).items():
        p = code / name
        if isinstance(content, Path):
            shutil.copy2(content, p)
        else:
            p.write_text(content)
    os.symlink(str(Path(GPY).parent.parent), str(ws / '.venv'))
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    r = subprocess.run([GPY, 'run_all.py', str(PUB), str(ws / 'outputs')], cwd=code, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(r.stderr[-2000:])
    if post:
        post(ws)
    qc(ws)
    (ws / 'README.md').write_text(README)
    fr = subprocess.run([GPY, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    (ws / 'environment.txt').write_text('python ' + platform.python_version() + '\n' + fr)
    return ws

def qc(ws):
    try:
        import numpy as np, nibabel as nib, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        o = ws / 'outputs' / 'subjects' / 'sub-01'
        fa = np.asarray(nib.load(str(o / 'fa.nii.gz')).dataobj); v1 = np.asarray(nib.load(str(o / 'v1_ras.nii.gz')).dataobj)
        z = fa.shape[2] // 2
        rgb = np.clip(np.abs(v1[:, :, z]) * fa[:, :, z, None], 0, 1)
        fig, ax = plt.subplots(1, 2, figsize=(8, 4)); ax[0].imshow(fa[:, :, z].T, origin='lower', cmap='gray'); ax[0].set_title('FA sub-01')
        ax[1].imshow(np.transpose(rgb, (1, 0, 2)), origin='lower'); ax[1].set_title('|V1_RAS| x FA')
        fig.savefig(ws / 'outputs' / 'qc.png', dpi=80); plt.close(fig)
    except Exception as e:
        print('qc failed', e)

README = """# DTI group pipeline (reference)
Entry point: code/process_subject.py --dwi --sidecar --labels --outdir (standalone, reruns on any subject).
Steps: LPS->RAS gradient conversion; effective b = nominal b x |g|^2 with unit directions; multiplicative drift
correction from a quadratic fit of the brain-mean b=0 signal vs acquisition time; WLS tensor fit (dipy) in the RAS
frame; FA, MD (um^2/ms) and V1 (RAS) maps; regional means; Welch tests on label-1 FA/MD (code/run_all.py).
Validation: synthetic truth comparison during authoring; recovered tract directions agree within <1 deg.
Limitations: magnitude data with Rician noise (no noise-floor correction, small positive FA bias in isotropic
regions); drift assumed spatially uniform and smooth; no motion/eddy correction because none was simulated.
"""

if __name__ == '__main__':
    ws = build_workspace(HERE / 'validation' / 'ws_reference')
    ev = HERE / 'validation' / 'eval_reference'
    r = subprocess.run([GPY, str(HERE / 'grade_dwigroup_arm.py'), str(ws), str(ev)], capture_output=True, text=True)
    print(r.stdout, r.stderr[-2000:])

