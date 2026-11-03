#!/usr/bin/env python3
"""Informational (not a control): simple ramp-filter density-compensated gridding (no iterations), scored by the grader."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_irt1 import grade
ws = HERE / 'validation/info_dcf_gridding'
make_workspace(ws, 'dcf_gridding')
g = grade(ws, HERE / 'validation/eval_info_dcf_gridding')
res = {'dcf_gridding': {'checks': {k: v['pass'] for k, v in g['checks'].items()}, 'public': g['measurements'].get('public'), 'hidden': g['measurements'].get('hidden')}}
(HERE / 'validation/informational_result.json').write_text(json.dumps(res, indent=1, default=float))
print(json.dumps(res)[:1500])

