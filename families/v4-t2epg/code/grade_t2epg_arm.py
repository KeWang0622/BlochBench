#!/usr/bin/env python3
"""Grade one arm of heldout-v4-t2epg, rerunning fit_t2.py with the arm's own interpreter.
Usage: python grade_t2epg_arm.py <workspace_dir> <eval_dir>"""
import json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from grade_t2epg import grade, locate, python_candidates, run_entry, CASES
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
src, script = locate(ws); chosen = None; trials = []
for py in python_candidates(ws):
    if script is None:
        break
    t = ev / ('probe-' + str(len(trials))); t.mkdir(exist_ok=True)
    shutil.copy2(script, t / 'fit_t2.py')
    if not (t / 'in').exists():
        shutil.copytree(CASES['public'][0], t / 'in')
    rc, so, se = run_entry(py, 'fit_t2.py', ['--input-dir', 'in', '--output-dir', 'out'], t)
    trials.append({'python': str(py), 'returncode': rc, 'stderr': se[-800:]})
    if rc == 0 and (t / 'out/t2_map.nii.gz').exists():
        chosen = py; break
g = grade(ws, ev, chosen); g['rerun_python'] = str(chosen) if chosen else None; g['rerun_python_trials'] = trials
(ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

