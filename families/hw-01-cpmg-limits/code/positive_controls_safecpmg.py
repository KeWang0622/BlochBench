#!/usr/bin/env python3
"""Positive controls for heldout-v5-safecpmg: acceptable alternative designs that must pass."""
import json, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build_workspace, GPY
CONTROLS = [
 ('P1_100deg_5p5ms_esp11_32echoes', {'alpha_deg': 100.0, 'tau_ref_s': 5.5e-3, 'esp_s': 11e-3, 'n_echo': 32}, None),
 ('P2_122deg_7p5ms_esp12_28echoes_5sample_adc', {'alpha_deg': 122.0, 'tau_ref_s': 7.5e-3, 'tau_exc_s': 0.8e-3, 'esp_s': 12e-3, 'n_echo': 28, 'adc_samples': 5, 'crusher_area_cyc_per_m': 900.0}, None),
]
if __name__ == '__main__':
    out = {}
    for name, sp, fo in CONTROLS:
        ws = build_workspace(HERE / 'validation' / 'controls' / name, seq_p=sp, fit_opt=fo)
        ev = HERE / 'validation' / 'controls' / ('eval_' + name)
        subprocess.run([GPY, str(HERE / 'grade_safecpmg_arm.py'), str(ws), str(ev)], capture_output=True, text=True, env=dict(os.environ, OMP_NUM_THREADS='1', JULIA_NUM_THREADS='1'))
        g = json.loads((ev / 'grade.json').read_text())
        m = {k: v for k, v in g['measurements'].items() if k != 'sequence'}
        out[name] = {'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']], 'measurements': m,
                     'safety': {k: g['measurements']['sequence'][k] for k in ('b1_rms_uT', 'pns_max_fraction', 'b1_peak_uT')} if 'sequence' in g['measurements'] else None}
        print(name, out[name]['pass'], out[name]['failed'], flush=True)
    (HERE / 'validation' / 'positive_controls_summary.json').write_text(json.dumps(out, indent=1, default=str))

