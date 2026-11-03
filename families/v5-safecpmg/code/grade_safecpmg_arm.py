#!/usr/bin/env python3
"""Grade one arm of heldout-v5-safecpmg, rerunning fit_t2.py with the arm's own interpreter.
Usage: python grade_safecpmg_arm.py <workspace_dir> <eval_dir>  (run with an interpreter that has pypulseq + juliacall/KomaMRI)"""
import json, shutil, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from grade_safecpmg import grade, locate, find
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
src, fitpy = locate(ws); seqf = find(ws, ['sequence.seq']); chosen = None; trials = []
cands = [ws / '.venv/bin/python'] + sorted(p for pat in ['*/bin/python', '*/*/bin/python'] for p in ws.glob(pat) if p.parts[len(ws.parts)] != '.venv')
pub = json.loads((HERE.parent / 'public' / 'inputs' / 'samples.json').read_text())['samples']
try:  # probe on the agent's own echo grid
    import seqcheck
    te_probe = np.array(seqcheck.analyze(seqf)['cpmg']['echo_times_s'], float) if seqf is not None else None
except Exception:
    te_probe = None
if te_probe is None or len(te_probe) == 0:
    te_probe = (np.arange(32) + 1) * 0.01
for py in [p for p in cands if p.exists()]:
    if fitpy is None or seqf is None:
        break
    t = ev / ('probe-%d' % len(trials)); t.mkdir(exist_ok=True)
    shutil.copy2(fitpy, t / 'fit_t2.py'); shutil.copy2(seqf, t / 'sequence.seq')
    # probe input: synthetic mono-exponential echo train on the agent's echo grid (only checks that the script runs)
    te = te_probe
    np.savez(t / 'measurement.npz', signals=(np.exp(-te / 0.08)[None, :] * np.ones((1, 1))).astype(complex), echo_times_s=te, t1_s=np.array([1.0]), sample_ids=np.array(['probe']))
    try:
        r = subprocess.run([str(py), 'fit_t2.py', '--input', 'measurement.npz', '--output', 'fit.npz'], cwd=t, capture_output=True, text=True, timeout=900)
        trials.append({'python': str(py), 'returncode': r.returncode, 'stderr': r.stderr[-800:]})
        if r.returncode == 0:
            chosen = py; break
    except Exception as e:
        trials.append({'python': str(py), 'returncode': -1, 'stderr': repr(e)[:300]})
if chosen is None:  # fall back to the first available interpreter so the hidden rerun is still attempted
    chosen = next((p for p in cands if p.exists()), None)
g = grade(ws, ev, chosen); g['rerun_python'] = str(chosen) if chosen else None; g['rerun_python_trials'] = trials
(ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

