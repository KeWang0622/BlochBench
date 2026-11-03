#!/usr/bin/env python3
"""Negative controls for heldout-v5-irt1: each plausible mistake must fail its targeted check."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_irt1 import grade

CONTROLS = {
    # name: (targeted check, description, hand-off?)
    'no_half_shift': ('trajectory_contract', 'readout prephaser = -area/2 (k=0 falls between samples 19 and 20)', 'sequence->sampling contract'),
    'b1_violation': ('sequence_hardware_limits', '1.0 ms block inversion pulse (B1 11.7 uT > 8 uT)', None),
    'no_dummy': ('periodic_state_preparation', 'no preparation before the first acquired inversion', None),
    'swap_xy_sim': ('simulation_matches_replay', 'phantom x/y swapped when handed to the Bloch simulator', 'phantom->simulator'),
    'recon_swap': ('hidden_rerun_t1_accuracy', 'archive trajectory [kx,ky] handed to the NUFFT in the wrong axis order', 'archive->reconstruction'),
    'twoparam': ('public_t1_accuracy', 'fit assumes full recovery S=M0(1-2exp(-TI/T1)) despite the finite recovery delay', 'sequence timing->signal model'),
    'naive_mag': ('hidden_fit_only_accuracy', 'magnitude images fitted with the signed model A-B*exp(-TI/T1) (no polarity restoration)', 'images->fit'),
}

def main():
    out = {}
    names = sys.argv[1:] or list(CONTROLS)
    for name in names:
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

