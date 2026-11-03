#!/usr/bin/env python3
"""Grade one arm of heldout-v5-learnrecon, rerunning predict.py / classical_recon.py with the arm's own interpreter.
Usage: python grade_learnrecon_arm.py <workspace_dir> <eval_dir>"""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from grade_learnrecon import grade, locate
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
pred, clas = locate(ws); chosen = None; trials = []
cands = [ws / '.venv/bin/python'] + sorted(p for pat in ['*/bin/python', '*/*/bin/python'] for p in ws.glob(pat) if p.parts[len(ws.parts)] != '.venv')
for py in [p for p in cands if p.exists()]:
    if pred is None:
        break
    out = ev / ('probe-%d.npz' % len(trials))
    try:
        r = subprocess.run([str(py), str(pred), '--input', str(HERE.parent / 'public' / 'inputs' / 'test.npz'), '--output', str(out)], cwd=str(pred.parent), capture_output=True, text=True, timeout=1200)
        trials.append({'python': str(py), 'returncode': r.returncode, 'stderr': r.stderr[-800:]})
        if r.returncode == 0 and out.exists():
            chosen = py; break
    except Exception as e:
        trials.append({'python': str(py), 'returncode': -1, 'stderr': repr(e)[:300]})
if chosen is None:  # fall back to the first available interpreter so the hidden rerun is still attempted
    chosen = next((p for p in cands if p.exists()), None)
g = grade(ws, ev, chosen); g['rerun_python'] = str(chosen) if chosen else None; g['rerun_python_trials'] = trials
(ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

