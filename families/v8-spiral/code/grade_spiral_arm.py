#!/usr/bin/env python3
"""Grade one arm of heldout-v8-spiral, using the arm's own interpreter for reruns.
usage: grade_spiral_arm.py <workspace_dir> <eval_dir>  -> <eval_dir>/grade.json"""
import json, sys, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import v8common as V
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
try:
    from grade_spiral import grade
    src, where = V.locate(ws)
    chosen, trials = V.choose_python(ws, src / 'reconstruct.py', src / 'simulation.npz', ev, 'simulation.npz', 'image_probe.npz')
    g = grade(ws, ev, chosen)
    g['rerun_python'] = str(chosen) if chosen else None; g['rerun_python_trials'] = trials
except Exception as e:
    g = {'all_automated_checks_pass': False, 'checks': {'grader_internal': {'pass': False, 'detail': traceback.format_exc()[-1500:]}}}
(ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))



