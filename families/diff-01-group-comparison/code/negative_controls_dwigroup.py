#!/usr/bin/env python3
"""Negative controls for heldout-v5-dwigroup: plausible mistakes; each must fail its targeted check(s)."""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build_workspace, GPY, PUB

def flip_group(ws):
    p = ws / 'outputs' / 'group_results.json'; g = json.loads(p.read_text())
    for k in g:
        g[k]['difference_patient_minus_control'] *= -1; lo, hi = g[k]['ci95']; g[k]['ci95'] = [-hi, -lo]
    p.write_text(json.dumps(g, indent=1))

HARD = PUB / 'sub-01' / 'dwi.json'
CONTROLS = [
 # name, handoff?, opt, post, extra, targeted checks
 ('N1_bvec_normalised_no_bscale', True, {'bscale': False}, None, None, ['public_md_accuracy', 'hidden_md_accuracy']),
 ('N2_lps_read_as_ras', True, {'frame': 'lps'}, None, None, ['public_v1_accuracy', 'hidden_v1_accuracy']),
 ('N3_scanner_dirs_used_as_voxel_axes', True, {'frame': 'voxel_noaffine'}, None, None, ['public_v1_accuracy', 'hidden_v1_accuracy']),
 ('N4_no_drift_correction', False, {'drift': 'none'}, None, None, ['public_md_accuracy', 'hidden_md_accuracy']),
 ('N5_drift_fit_on_all_volumes', False, {'drift': 'allvol'}, None, None, ['public_md_accuracy', 'public_fa_accuracy']),
 ('N6_md_reported_in_mm2_per_s', True, {'md_unit': 1.0}, None, None, ['public_md_accuracy', 'hidden_md_accuracy', 'hidden_maps']),
 ('N7_v1_reported_in_voxel_axes', True, {'v1_world': False}, None, None, ['public_v1_accuracy', 'hidden_v1_accuracy']),
 ('N8_group_difference_sign_reversed', False, {}, flip_group, None, ['group_difference_accuracy']),
 ('N9_entrypoint_hardcodes_public_gradient_table', True, {'hardcode_sidecar': 'public_dwi.json'}, None, {'public_dwi.json': HARD}, ['hidden_rerun_runs']),
]

if __name__ == '__main__':
    out = {}
    for name, handoff, opt, post, extra, targets in CONTROLS:
        ws = build_workspace(HERE / 'validation' / 'controls' / name, opt=opt, post=post, extra_files=extra)
        ev = HERE / 'validation' / 'controls' / ('eval_' + name)
        r = subprocess.run([GPY, str(HERE / 'grade_dwigroup_arm.py'), str(ws), str(ev)], capture_output=True, text=True)
        g = json.loads((ev / 'grade.json').read_text())
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        hit = [t for t in targets if t in failed]
        out[name] = {'handoff_error': handoff, 'targeted': targets, 'failed': failed, 'targeted_failed': bool(hit) and not g['all_automated_checks_pass'], 'measurements': g['measurements']}
        print(name, 'OK' if out[name]['targeted_failed'] else 'NOT CAUGHT', failed)
    (HERE / 'validation' / 'negative_controls_summary.json').write_text(json.dumps(out, indent=1, default=str))

