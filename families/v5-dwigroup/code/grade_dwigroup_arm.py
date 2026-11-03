#!/usr/bin/env python3
"""Grade one arm of heldout-v5-dwigroup, rerunning process_subject.py with the arm's own interpreter.
Usage: python grade_dwigroup_arm.py <workspace_dir> <eval_dir>"""
import json, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from grade_dwigroup import grade, locate
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
src, entry = locate(ws); chosen = None; trials = []
cands = [ws / '.venv/bin/python'] + sorted(p for pat in ['*/bin/python', '*/*/bin/python'] for p in ws.glob(pat) if p.parts[len(ws.parts)] != '.venv')
probe = sorted((HERE.parent / 'public' / 'inputs').glob('sub-01'))
for py in [p for p in cands if p.exists()]:
    if entry is None or not probe:
        break
    t = ev / ('probe-%d' % len(trials))
    d = probe[0]
    r = subprocess.run([str(py), str(entry), '--dwi', str(d / 'dwi.nii.gz'), '--sidecar', str(d / 'dwi.json'), '--labels', str(d / 'labels.nii.gz'), '--outdir', str(t)],
                       cwd=str(entry.parent), capture_output=True, text=True, timeout=900)
    trials.append({'python': str(py), 'returncode': r.returncode, 'stderr': r.stderr[-800:]})
    if r.returncode == 0 and (t / 'results.json').exists():
        chosen = py; break
if chosen is None:  # fall back to the first available interpreter so the hidden rerun is still attempted
    chosen = next((p for p in cands if p.exists()), None)
g = grade(ws, ev, chosen); g['rerun_python'] = str(chosen) if chosen else None; g['rerun_python_trials'] = trials
(ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

