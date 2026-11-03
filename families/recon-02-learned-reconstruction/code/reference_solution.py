#!/usr/bin/env python3
"""Reference solution for heldout-v5-learnrecon: train a small learned reconstruction on CPU, tune a classical
joint-sparsity CS reconstruction on validation subjects, compare both via downstream R2*/B0 ROI accuracy.
build_workspace() is reused by the control scripts."""
import json, os, platform, re, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'
PY = str(HERE / 'refenv' / 'bin' / 'python')
GPY = '/Users/kewang/Documents/Codex/2026-09-22/read-mri-talk-handoff-md-and/work/radial-gre-venv/bin/python'
ENV = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1', MKL_NUM_THREADS='1')

def set_opt(path, varname, upd):
    s = path.read_text()
    m = re.search(r'^' + varname + r' = \{.*\}$', s, re.M)
    s = s[:m.end()] + '\n' + varname + '.update(' + repr(upd) + ')' + s[m.end():]
    path.write_text(s)

def build_workspace(ws, train_opts=None, reuse_model=None, cfg_override=None, predict_opt=None, classical_opt=None, report_scale=None, post=None):
    ws = Path(ws)
    if ws.exists():
        tr = HERE / 'validation' / '_trash'; tr.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ws), str(tr / (ws.name + '_%d' % len(list(tr.iterdir())))))
    code = ws / 'code'; outd = ws / 'outputs'; code.mkdir(parents=True); outd.mkdir()
    for f in ['common.py', 'net.py', 'train.py', 'predict.py', 'classical_recon.py', 'evaluate.py']:
        shutil.copy2(HERE / 'reference_code' / f, code / f)
    if predict_opt:
        set_opt(code / 'predict.py', 'OPT', predict_opt)
    if classical_opt:
        set_opt(code / 'classical_recon.py', 'OPT', classical_opt)
    if report_scale:
        set_opt(code / 'evaluate.py', 'REPORT_SCALE', report_scale)
    os.symlink(str(HERE / 'refenv'), str(ws / '.venv'))
    if reuse_model:
        shutil.copy2(Path(reuse_model) / 'model.pt', code / 'model.pt'); shutil.copy2(Path(reuse_model) / 'split.json', code / 'split.json')
        shutil.copy2(Path(reuse_model) / 'train_log.json', code / 'train_log.json')
    else:
        (code / '_opts.json').write_text(json.dumps(dict({'epochs': 30}, **(train_opts or {}))))
        r = subprocess.run([PY, 'train.py', str(PUB / 'train.npz'), '.', '_opts.json'], cwd=code, capture_output=True, text=True, env=ENV)
        (code / 'train_stdout.log').write_text(r.stdout[-20000:] + r.stderr[-5000:])
    if cfg_override:
        r = subprocess.run([PY, '-c', 'import torch,sys,json; ck=torch.load("model.pt"); ck["cfg"].update(json.loads(sys.argv[1])); torch.save(ck,"model.pt")', json.dumps(cfg_override)], cwd=code, capture_output=True, text=True, env=ENV)
    shutil.move(str(code / 'split.json'), str(outd / 'split.json'))
    r = subprocess.run([PY, 'evaluate.py', str(PUB), str(outd)], cwd=code, capture_output=True, text=True, env=ENV)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-3000:])
    if post:
        post(ws)
    (ws / 'README.md').write_text(README)
    fr = subprocess.run([PY, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    (ws / 'environment.txt').write_text('python ' + platform.python_version() + '\n' + fr)
    return ws

README = """# Learned vs classical reconstruction judged by downstream R2*/B0 (reference)
Data: 28 training subjects (6 slices, fully sampled 5-echo GRE k-space); split by subject (22 train / 6 validation, outputs/split.json).
Learned: code/train.py trains a 2-cascade residual U-Net with hard data consistency on CPU (30 epochs, ~2 min) with masks drawn from the
stated variable-density distribution; one intensity scale per slice shared by all echoes (preserves the echo decay and phase).
Classical: code/classical_recon.py, joint-sparsity (group L1 across echoes) wavelet CS (sigpy), lambda tuned on validation slices by the
downstream R2* error. Downstream: weighted log-linear R2* and consecutive-echo phase-difference B0, ROI means over eroded labels.
Entrypoints: code/predict.py and code/classical_recon.py --input <npz> --output <npz>.
Validation: downstream R2*/B0 ROI errors of both methods and of zero filling on the validation subjects (outputs/downstream_results.json).
Limitations: single-coil synthetic data, one acceleration factor and mask distribution; small network trained for minutes; ROI means
over eroded labels hide edge errors; validation reference maps come from noisy fully sampled data.
"""

if __name__ == '__main__':
    ws = build_workspace(HERE / 'validation' / 'ws_reference')
    keep = HERE / 'validation' / 'reference_model'; keep.mkdir(parents=True, exist_ok=True)
    for f in ['model.pt', 'train_log.json']:
        shutil.copy2(ws / 'code' / f, keep / f)
    shutil.copy2(ws / 'outputs' / 'split.json', keep / 'split.json')
    ev = HERE / 'validation' / 'eval_reference'
    r = subprocess.run([GPY, str(HERE / 'grade_learnrecon_arm.py'), str(ws), str(ev)], capture_output=True, text=True, env=ENV)
    print(r.stdout, r.stderr[-1500:])

