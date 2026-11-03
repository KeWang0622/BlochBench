#!/usr/bin/env python3
"""Negative controls for heldout-v5-learnrecon: plausible mistakes; each must fail its targeted check(s)."""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build_workspace, GPY, ENV
MODEL = HERE / 'validation' / 'reference_model'

def slice_split(ws):
    p = ws / 'outputs' / 'split.json'; s = json.loads(p.read_text())
    allsub = sorted(set(s['train_subjects']) | set(s['validation_subjects']))
    p.write_text(json.dumps({'train_subjects': allsub, 'validation_subjects': allsub[::5], 'split_level': 'slice (random slices)'}))

CONTROLS = [
 ('N1_per_echo_intensity_normalisation', True, dict(cfg_override={'per_echo_norm': True}), ['public_learned_downstream', 'hidden_learned_downstream']),
 ('N2_magnitude_only_network_output', True, dict(cfg_override={'mag_only': True}), ['public_learned_downstream', 'hidden_learned_downstream']),
 ('N3_classical_uses_one_fixed_mask', True, dict(classical_opt={'fixed_mask': True}), ['public_classical_downstream', 'public_data_consistency', 'hidden_classical_downstream']),
 ('N4_missing_ifftshift_in_learned_output', True, dict(predict_opt={'shift_output': True}), ['public_data_consistency', 'public_learned_downstream', 'hidden_learned_downstream']),
 ('N5_slice_level_train_validation_split', False, dict(post=slice_split), ['split_by_subject']),
 ('N6_r2s_reported_in_per_ms', True, dict(report_scale={'r2s': 1e-3}), ['reported_downstream_matches_recon']),
 ('N7_zero_filled_submitted_as_classical', False, dict(classical_opt={'mode': 'zf'}), ['public_classical_downstream', 'hidden_classical_downstream']),
]
if __name__ == '__main__':
    out = {}; only = sys.argv[1:]
    for name, handoff, kw, targets in CONTROLS:
        if only and name not in only:
            continue
        ws = build_workspace(HERE / 'validation' / 'controls' / name, reuse_model=MODEL, **kw)
        ev = HERE / 'validation' / 'controls' / ('eval_' + name)
        subprocess.run([GPY, str(HERE / 'grade_learnrecon_arm.py'), str(ws), str(ev)], capture_output=True, text=True, env=ENV)
        g = json.loads((ev / 'grade.json').read_text())
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        out[name] = {'handoff_error': handoff, 'targeted': targets, 'failed': failed, 'targeted_failed': any(t in failed for t in targets) and not g['all_automated_checks_pass'], 'measurements': g['measurements']}
        print(name, 'OK' if out[name]['targeted_failed'] else 'NOT CAUGHT', failed, flush=True)
    (HERE / 'validation' / 'negative_controls_summary.json').write_text(json.dumps(out, indent=1, default=str))

