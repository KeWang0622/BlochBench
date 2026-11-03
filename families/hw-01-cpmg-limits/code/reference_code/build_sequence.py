#!/usr/bin/env python3
"""Build the safety-constrained CPMG sequence (reference). Writes sequence.seq and seq_params.json."""
import json, sys
from pathlib import Path
import numpy as np, pypulseq as pp

P = {'alpha_deg': 120.0, 'tau_ref_s': 7.0e-3, 'tau_exc_s': 1.0e-3, 'esp_s': 12e-3, 'n_echo': 28, 'tr_s': 1.0,
     'crusher_area_cyc_per_m': 1000.0, 'crusher_gmax_mT_per_m': 20.0, 'crusher_slew': 60.0, 'adc_samples': 1, 'adc_dwell_s': 10e-6,
     'ref_shape': 'block'}

def r10(x):
    return round(x / 1e-5) * 1e-5

def build(out='sequence.seq', p=None):
    p = dict(P, **(p or {}))
    sysm = pp.Opts(max_grad=38, grad_unit='mT/m', max_slew=150, slew_unit='T/m/s', rf_ringdown_time=20e-6, rf_dead_time=100e-6,
                   adc_dead_time=10e-6, grad_raster_time=10e-6, rf_raster_time=1e-6, block_duration_raster=10e-6, adc_raster_time=1e-7, gamma=42.576e6)
    crs = pp.Opts(max_grad=p['crusher_gmax_mT_per_m'], grad_unit='mT/m', max_slew=p['crusher_slew'], slew_unit='T/m/s', grad_raster_time=10e-6, gamma=42.576e6)
    seq = pp.Sequence(sysm)
    exc = pp.make_block_pulse(np.pi / 2, duration=p['tau_exc_s'], delay=100e-6, system=sysm, phase_offset=0.0, use='excitation')
    if p['ref_shape'] == 'block':
        ref = pp.make_block_pulse(np.deg2rad(p['alpha_deg']), duration=p['tau_ref_s'], delay=100e-6, system=sysm, phase_offset=np.pi / 2, use='refocusing')
    else:
        ref = pp.make_sinc_pulse(np.deg2rad(p['alpha_deg']), duration=p['tau_ref_s'], delay=100e-6, time_bw_product=2, apodization=0.5, system=sysm, phase_offset=np.pi / 2, use='refocusing')
    cr = pp.make_trapezoid('z', area=p['crusher_area_cyc_per_m'], system=crs)
    d_exc = pp.calc_duration(exc); t_ec = exc.delay + p['tau_exc_s'] / 2
    d_ref = pp.calc_duration(ref); c_r = ref.delay + p['tau_ref_s'] / 2; a_r = d_ref - c_r
    d_cr = pp.calc_duration(cr); esp = p['esp_s']
    gap1 = r10(esp / 2 - (d_exc - t_ec) - d_cr - c_r)
    x = esp / 2 - a_r - d_cr
    L = r10(esp / 2 - d_cr - c_r + x)
    if gap1 < 0 or x < 20e-6 or L - x < 20e-6:
        raise ValueError('timing infeasible: gap1=%g x=%g L=%g' % (gap1, x, L))
    ns, dw = p['adc_samples'], p['adc_dwell_s']
    adc = pp.make_adc(num_samples=ns, dwell=dw, delay=round((x - (ns // 2 + 0.5) * dw) / 1e-7) * 1e-7, system=sysm)
    seq.add_block(exc)
    if gap1 > 0:
        seq.add_block(pp.make_delay(gap1))
    for n in range(p['n_echo']):
        seq.add_block(cr); seq.add_block(ref); seq.add_block(cr)
        seq.add_block(adc, pp.make_delay(L))
    dur = sum(seq.block_durations.values())
    seq.add_block(pp.make_delay(r10(p['tr_s'] - dur)))
    seq.set_definition('Name', 'cpmg_safe')
    seq.write(out)
    p['crusher_area_realized'] = float(cr.area)
    Path(out).with_name('seq_params.json').write_text(json.dumps(p, indent=1))
    return seq, p

if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'sequence.seq')

