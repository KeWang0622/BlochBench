#!/usr/bin/env python3
"""Negative controls for heldout-v5-spiralb0: each plausible mistake must fail its targeted check."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_spiralb0 import grade

CONTROLS = {
    'no_correction': ('hidden_rerun_correction', 'field map estimated but not used in the reconstruction (plain least-squares spiral recon)', None),
    'field_sign': ('public_field_map_accuracy', 'field map computed with the opposite phase convention (df = +dphi/(2 pi dTE))', 'field-map scan->field estimate'),
    'delta_te_ms': ('public_field_map_accuracy', 'echo-time difference taken in ms when converting phase to Hz', 'field-map scan->field estimate'),
    'field_transposed': ('public_field_map_accuracy', 'field map stored/used as [x,y] instead of [y,x]', 'field estimate->reconstruction grid'),
    'time_from_adc_start': ('public_image_fidelity', 'off-resonance time measured from the first ADC sample instead of the excitation centre', 'sequence timing->reconstruction model'),
    'kxy_swapped': ('hidden_rerun_correction', 'archive trajectory columns [kx,ky] read in the wrong order', 'archive->reconstruction'),
    'hz_as_rad': ('simulation_matches_replay', 'field in Hz handed to the simulator as if it were rad/s', 'field->simulator'),
    'slew_violation': ('sequence_hardware_limits', 'spiral designed for 195 T/m/s', None),
    'undersampled_spiral': ('trajectory_coverage_contract', 'turn spacing 1.7/FOV (spiral undersampled)', None),
}

def main():
    out = {}
    for name in (sys.argv[1:] or list(CONTROLS)):
        tgt, desc, handoff = CONTROLS[name]
        ws = HERE / 'validation' / f'neg_{name}'
        make_workspace(ws, name)
        g = grade(ws, HERE / 'validation' / f'eval_neg_{name}')
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        out[name] = dict(target=tgt, description=desc, handoff=handoff, target_failed=tgt in failed, failed_checks=failed,
                         target_detail=g['checks'][tgt]['detail'])
        print(name, 'target failed' if tgt in failed else 'TARGET PASSED (bad)', failed, flush=True)
    p = HERE / 'validation' / 'negative_controls_result.json'
    prev = json.loads(p.read_text()) if p.exists() else {}
    prev.update(out); p.write_text(json.dumps(prev, indent=1, default=str))
    print('ALL TARGETS FAILED' if all(v['target_failed'] for v in prev.values()) else 'SOME CONTROL NOT DETECTED')

if __name__ == '__main__':
    main()

