#!/usr/bin/env python3
"""Negative controls for heldout-v4-t2epg: each plausible mistake must fail its targeted check(s)."""
import json, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build
from grade_t2epg import grade

CONTROLS = {
    'monoexp_all': (['public_t2_low_b1_bias', 'public_roi_t2_endpoint'], 'mono-exponential fit over all echoes (stimulated echoes ignored)'),
    'monoexp_skip_first': (['public_t2_low_b1_bias', 'public_roi_t2_endpoint'], 'mono-exponential fit discarding the first echo'),
    'epg_b1_fixed': (['public_t2_low_b1_bias', 'public_b1_accuracy'], 'EPG fit with nominal flip angles (B1 fixed to 1)'),
    'cp_phase': (['public_t2_voxel_accuracy', 'public_b1_accuracy'], 'EPG with refocusing about the excitation axis (CP instead of CPMG)'),
    'esp_full_each_half': (['public_t2_voxel_accuracy', 'public_roi_t2_endpoint'], 'relaxation over a full echo spacing in each half interval'),
    'hardcoded_protocol': (['hidden_t2_voxel_accuracy', 'hidden_roi_t2_endpoint'], 'echo spacing and refocusing angle hard-coded from the public data'),
}

if __name__ == '__main__':
    base = Path(tempfile.mkdtemp(prefix='nc_t2epg_', dir=str(HERE.parents[1] / '_trash')))
    res = {}
    for name, (targets, desc) in CONTROLS.items():
        ws = build(base / name, mistake=name)
        g = grade(ws, base / (name + '_eval'), Path(sys.executable))
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        res[name] = {'description': desc, 'targets': targets, 'failed_checks': failed,
                     'targeted_fail': all(t in failed for t in targets), 'overall_pass': g['all_automated_checks_pass'],
                     'public': g['measurements'].get('public'), 'hidden': g['measurements'].get('hidden')}
        print(name, res[name]['targeted_fail'], failed, flush=True)
    ok = all(v['targeted_fail'] and not v['overall_pass'] for v in res.values())
    (HERE / 'validation/negative_controls_results.json').write_text(json.dumps({'all_controls_fail_as_targeted': ok, 'controls': res}, indent=1, default=str))
    print('ALL_NEGATIVE_CONTROLS_OK', ok)

