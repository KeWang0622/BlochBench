#!/usr/bin/env python3
"""Reference: build the IR radial sequence with pypulseq. Usage: python build_sequence.py [--out sequence.seq] [--variant name]"""
import argparse, json, math
import numpy as np
import pypulseq as pp

FOV = 0.200; N = 40; NSPOKE = 40
TI = [0.045, 0.13, 0.33, 0.80, 1.60]
TD = 2.4

def build(out='sequence.seq', inv_dur=1.8e-3, exc_dur=1.0e-3, dwell=20e-6, dummy=True, half_shift=True,
          spoke_angle=lambda s: math.pi * s / NSPOKE, ti_list=TI, td=TD):
    sysm = pp.Opts(max_grad=30, grad_unit='mT/m', max_slew=120, slew_unit='T/m/s', rf_ringdown_time=20e-6,
                   rf_dead_time=100e-6, adc_dead_time=10e-6, grad_raster_time=10e-6, rf_raster_time=1e-6,
                   adc_raster_time=100e-9, block_duration_raster=10e-6, gamma=42.576e6)
    seq = pp.Sequence(sysm)
    rf_inv = pp.make_block_pulse(math.pi, duration=inv_dur, system=sysm, use='inversion')
    rf_exc = pp.make_block_pulse(math.pi / 2, duration=exc_dur, system=sysm, use='excitation')
    dk = 1.0 / FOV
    ro_dur = N * dwell
    gro = pp.make_trapezoid('x', flat_area=N * dk, flat_time=ro_dur, system=sysm)
    adc = pp.make_adc(num_samples=N, dwell=dwell, delay=gro.rise_time, system=sysm)
    pre_area = -gro.area / 2 - (0.5 * dk if half_shift else 0.0)
    gpre = pp.make_trapezoid('x', area=pre_area, system=sysm)
    # common prephaser duration so that both axes can share timing
    inv_c = rf_inv.delay + pp.calc_rf_center(rf_inv)[0]
    exc_c = rf_exc.delay + pp.calc_rf_center(rf_exc)[0]
    inv_blk = pp.calc_duration(rf_inv); exc_blk = pp.calc_duration(rf_exc)
    def rot(g, ang):
        gx = pp.scale_grad(g, math.cos(ang)); gy = pp.scale_grad(g, math.sin(ang)); gy.channel = 'y'
        return gx, gy
    ro_blk = pp.calc_duration(gro, adc)
    pre_blk = pp.calc_duration(gpre)
    after_exc = (exc_blk - exc_c) + pre_blk + ro_blk
    r = sysm.block_duration_raster
    def rnd(t):
        return round(t / r) * r
    td_delay = rnd(td - after_exc - inv_c)
    if dummy:
        seq.add_block(rf_exc)
        seq.add_block(pp.make_delay(rnd(td - (exc_blk - exc_c) - inv_c)))
    for ti in ti_list:
        ti_delay = rnd(ti - (inv_blk - inv_c) - exc_c)
        for s in range(NSPOKE):
            ang = spoke_angle(s)
            seq.add_block(rf_inv)
            seq.add_block(pp.make_delay(ti_delay))
            seq.add_block(rf_exc)
            px, py = rot(gpre, ang)
            seq.add_block(px, py)
            gx, gy = rot(gro, ang)
            seq.add_block(gx, gy, adc)
            seq.add_block(pp.make_delay(td_delay))
    ok, rep = seq.check_timing()
    if not ok:
        raise RuntimeError('timing check failed: ' + str(rep[:3]))
    seq.set_definition('FOV', [FOV, FOV, 0.005])
    seq.set_definition('Name', 'ir_radial_t1')
    seq.set_definition('InversionTimes', ti_list)
    seq.set_definition('RecoveryDelay', td)
    seq.write(out)
    te = exc_blk - exc_c + pre_blk + gro.rise_time + (N // 2 + 0.5) * dwell
    return dict(te_s=te, inv_b1_uT=float(np.max(np.abs(rf_inv.signal)) / 42.576e6 * 1e6),
                exc_b1_uT=float(np.max(np.abs(rf_exc.signal)) / 42.576e6 * 1e6))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq')
    a = ap.parse_args()
    print(json.dumps(build(a.out)))

