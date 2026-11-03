#!/usr/bin/env python3
"""Grade one arm of heldout-v5-t2study using the arm's own interpreter for entrypoint reruns.
Usage: python grade_t2study_arm.py <workspace_dir> <eval_dir>"""
import json, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from grade_t2study import grade, locate
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
F, _ = locate(ws); chosen = None; trials = []
cands = [ws / '.venv/bin/python'] + sorted(p for pat in ['*/bin/python', '*/*/bin/python'] for p in ws.glob(pat) if p.parts[len(ws.parts)] != '.venv')
probe_in = HERE.parent / 'public/inputs/scans/sub-01_ses-1.npz'
for py in [p for p in cands if p.exists()]:
    if not F.get('map_t2.py'):
        break
    t = ev / ('probe-' + str(len(trials))); t.mkdir(exist_ok=True)
    shutil.copy2(probe_in, t / 'scan.npz'); shutil.copy2(F['map_t2.py'], t / 'map_t2.py')
    try:
        r = subprocess.run([str(py), 'map_t2.py', '--input', 'scan.npz', '--output', 'probe_t2map.npz'], cwd=t, capture_output=True, text=True, timeout=900)
        trials.append({'python': str(py), 'returncode': r.returncode, 'stderr': r.stderr[-800:]})
        if r.returncode == 0:
            chosen = py; break
    except Exception as e:
        trials.append({'python': str(py), 'error': repr(e)})
g = grade(ws, ev, chosen); g['rerun_python'] = str(chosen) if chosen else None; g['rerun_python_trials'] = trials
(ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

