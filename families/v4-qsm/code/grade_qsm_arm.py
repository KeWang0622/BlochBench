#!/usr/bin/env python3
"""Grade one arm of heldout-v4-qsm using the arm's own interpreter for the reruns.
Usage: python grade_qsm_arm.py <workspace_dir> <eval_dir>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from grade_qsm import grade, locate, choose_python, PUB, ARGS
ws = Path(sys.argv[1]).resolve(); ev = Path(sys.argv[2]).resolve(); ev.mkdir(parents=True, exist_ok=True)
loc = locate(ws)
py, trials = choose_python(ws, ev, loc['entry'], PUB, ARGS)
g = grade(ws, ev, py)
g['rerun_python'] = str(py) if py else None; g['rerun_python_trials'] = trials
(ev/'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

