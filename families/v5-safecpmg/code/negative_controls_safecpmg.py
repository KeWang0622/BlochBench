#!/usr/bin/env python3
"""Negative controls for heldout-v5-safecpmg: plausible mistakes; each must fail its targeted check(s)."""
import json, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import build_workspace, GPY
CONTROLS = [
 # name, handoff_error, seq_p, fit_opt, sim_p, targeted checks
 ('N1_refocusing_180deg_3p5ms_exceeds_b1rms', False, {'alpha_deg': 180.0, 'tau_ref_s': 3.5e-3}, None, None, ['b1_rms_limit']),
 ('N2_b1rms_evaluated_over_wrong_window', True, {'tr_s': 0.6}, None, {'report_tr_s': 1.0}, ['b1_rms_limit', 'report_matches_sequence']),
 ('N3_crushers_at_max_slew_exceed_pns', False, {'crusher_gmax_mT_per_m': 38.0, 'crusher_slew': 150.0}, None, None, ['pns_limit']),
 ('N4_instantaneous_pulse_epg_for_long_pulses', True, None, {'finite_pulse': False}, None, ['hidden_t2_accuracy', 'public_fit_accuracy']),
 ('N5_model_assumes_nominal_180_refocusing', True, None, {'model_alpha_deg': 180.0}, None, ['hidden_b1_accuracy']),
 ('N6_stale_echo_spacing_in_model', True, None, {'model_esp_s': 11e-3}, None, ['hidden_t2_accuracy']),
 ('N7_b1_not_estimated', False, None, {'fit_b1': False}, None, ['hidden_t2_accuracy', 'hidden_b1_accuracy']),
 ('N8_simulated_a_different_sequence_than_exported', True, None, None, {'simulate_other': {'alpha_deg': 180.0, 'tau_ref_s': 3.5e-3}}, ['simulation_matches_replay']),
 ('N9_crushers_below_required_moment', False, {'crusher_area_cyc_per_m': 400.0}, None, None, ['crusher_moments']),
 ('N10_monoexponential_fit', False, None, {'mono': True}, None, ['hidden_t2_accuracy']),
]
if __name__ == '__main__':
    out = {}
    only = sys.argv[1:]
    for name, handoff, sp, fo, simp, targets in CONTROLS:
        if only and name not in only:
            continue
        ws = build_workspace(HERE / 'validation' / 'controls' / name, seq_p=sp, fit_opt=fo, sim_p=simp)
        ev = HERE / 'validation' / 'controls' / ('eval_' + name)
        subprocess.run([GPY, str(HERE / 'grade_safecpmg_arm.py'), str(ws), str(ev)], capture_output=True, text=True, env=dict(os.environ, OMP_NUM_THREADS='1', JULIA_NUM_THREADS='1'))
        g = json.loads((ev / 'grade.json').read_text())
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        m = {k: v for k, v in g['measurements'].items() if k != 'sequence'}
        out[name] = {'handoff_error': handoff, 'targeted': targets, 'failed': failed, 'targeted_failed': any(t in failed for t in targets) and not g['all_automated_checks_pass'], 'measurements': m}
        print(name, 'OK' if out[name]['targeted_failed'] else 'NOT CAUGHT', failed, flush=True)
    (HERE / 'validation' / 'negative_controls_summary.json').write_text(json.dumps(out, indent=1, default=str))

