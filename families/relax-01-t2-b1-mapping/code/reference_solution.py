#!/usr/bin/env python3
"""Reference solution for heldout-v4-t2epg (builds private/validation/workspace and grades it)."""
import json, platform, re, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TASK = HERE.parent


def build(ws, method='dictionary', mistake=None, py=sys.executable):
    ws = Path(ws); ws.mkdir(parents=True, exist_ok=True)
    s = (HERE / 'ref_fit_template.py').read_text()
    s = re.sub(r"^METHOD = .*$", "METHOD = %r" % method, s, count=1, flags=re.M)
    s = re.sub(r"^MISTAKE = .*$", "MISTAKE = %r" % (mistake,), s, count=1, flags=re.M)
    (ws / 'fit_t2.py').write_text(s)
    r = subprocess.run([py, 'fit_t2.py', '--input-dir', str(TASK / 'public/inputs'), '--output-dir', 'outputs'], cwd=ws, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr)
    roi = json.loads((ws / 'outputs/roi_t2.json').read_text())['label_mean_T2_s']
    import scipy, nibabel
    rep = {'scope': 'CPMG multi-echo spin-echo T2 mapping with stimulated-echo correction (simulated data)',
           'model': 'extended phase graph CPMG model; free T2, B1+ scale and M0 per voxel; T1 fixed at AssumedT1_s',
           'fit_method': {'dictionary': 'EPG dictionary matching (420 log-spaced T2 x B1 0.40-1.20 step 0.005)',
                          'dictionary_truncated': 'EPG dictionary matching on echoes above 4x the background noise',
                          'gauss_newton': 'coarse EPG grid followed by vectorised Gauss-Newton (variable projection on M0)'}[method],
           'roi_mean_T2_s': roi,
           'software': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'nibabel': nibabel.__version__},
           'validation_summary': 'EPG reduces to exp(-TE/T2) at B1 = 1; fitted curves overlay the data; B1 map is smooth and within the stated range.',
           'limitations': ['hard-pulse model; slice-profile effects not modelled', 'T1 fixed to the assumed value', 'Rician noise floor not modelled']}
    (ws / 'report.json').write_text(json.dumps(rep, indent=1))
    (ws / 'README.md').write_text('# CPMG T2 mapping\n\nRun: python fit_t2.py --input-dir inputs --output-dir outputs\n')
    return ws


if __name__ == '__main__':
    sys.path.insert(0, str(HERE))
    from grade_t2epg import grade
    ws = build(HERE / 'validation/workspace')
    g = grade(ws, HERE / 'validation/grade_reference', Path(sys.executable))
    (HERE / 'validation/grade_reference/grade.json').write_text(json.dumps(g, indent=1, default=str))
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

