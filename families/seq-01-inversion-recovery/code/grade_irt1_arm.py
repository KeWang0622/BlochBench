#!/usr/bin/env python3
"""Grade one arm of heldout-v5-irt1, using the arm's own interpreter for entrypoint reruns.
Usage: python grade_irt1_arm.py <workspace_dir> <eval_dir>"""
import json, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from grade_irt1 import grade, locate
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
F, _ = locate(ws); chosen = None; trials = []
cands = [ws / '.venv/bin/python'] + sorted(p for pat in ['*/bin/python', '*/*/bin/python'] for p in ws.glob(pat) if p.parts[len(ws.parts)] != '.venv')
for py in [p for p in cands if p.exists()]:
    if not (F.get('simulation.npz') and F.get('reconstruct.py')):
        break
    t = ev / ('probe-' + str(len(trials))); t.mkdir(exist_ok=True)
    shutil.copy2(F['simulation.npz'], t / 'simulation.npz'); shutil.copy2(F['reconstruct.py'], t / 'reconstruct.py')
    try:
        r = subprocess.run([str(py), 'reconstruct.py', '--input', 'simulation.npz', '--output', 'images_probe.npz'], cwd=t, capture_output=True, text=True, timeout=900)
        trials.append({'python': str(py), 'returncode': r.returncode, 'stderr': r.stderr[-800:]})
        if r.returncode == 0:
            chosen = py; break
    except Exception as e:
        trials.append({'python': str(py), 'error': repr(e)})
g = grade(ws, ev, chosen); g['rerun_python'] = str(chosen) if chosen else None; g['rerun_python_trials'] = trials
(ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

