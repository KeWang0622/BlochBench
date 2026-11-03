#!/usr/bin/env python3
"""Informational (not a control): GRAPPA without prewhitening + RSS + unweighted log-linear fit, scored by the grader."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_t2study import grade
ws = HERE / 'validation/info_grappa_rss_naive'
make_workspace(ws, 'grappa_rss_naive')
src = (ws / 'map_t2.py').read_text(); print('noprewhite' if 'kw = ksp' in src else 'PATCH MISSING', 'unweighted' if 'w = np.ones_like(y)' in src else 'PATCH2 MISSING')
g = grade(ws, HERE / 'validation/eval_info_grappa_rss_naive')
print(json.dumps({k: v['pass'] for k, v in g['checks'].items()}))
print(json.dumps(g['checks']['per_scan_roi_accuracy']['detail']), json.dumps(g['checks']['t2map_files_consistent']['detail']))
(HERE / 'validation/informational_controls_result.json').write_text(json.dumps({'grappa_rss_naive': {'checks': {k: v['pass'] for k, v in g['checks'].items()}, 'per_scan': g['checks']['per_scan_roi_accuracy']['detail']}}, indent=1))

