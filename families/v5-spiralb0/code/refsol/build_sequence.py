#!/usr/bin/env python3
"""Reference: single-shot spiral-out GRE (pypulseq). Usage: python build_sequence.py [--out sequence.seq]"""
import argparse, json, math
import numpy as np
import pypulseq as pp

FOV = 0.216; N = 40; GAMMA = 42.576e6

def spiral_k(gmax_frac=0.92, smax_frac=0.88, turn_spacing=1.0, gmax=30e-3, smax=125.0, dt=1e-6):
    """Archimedean spiral k(theta)=A*theta*exp(i theta), time-parametrised under amplitude and slew limits.
    Returns k(t) samples (cycles/m, complex) on a dt grid."""
    dk = turn_spacing / FOV; A = dk / (2 * np.pi); kmax = N / (2 * FOV)
    thmax = 2 * np.pi * 1.04 * kmax / dk
    G = GAMMA * gmax * gmax_frac; S = GAMMA * smax * smax_frac
    th, thd = 0.0, 0.0; ks = [0j]
    while th < thmax:
        a = 1 + 1j * th; b = thd ** 2 * (2j - th); c = S / A
        aa = abs(a) ** 2; ab = (np.conj(a) * b).real; disc = ab ** 2 - aa * (abs(b) ** 2 - c ** 2)
        thdd = (-ab + math.sqrt(disc)) / aa if disc > 0 else -ab / aa
        thd_new = thd + thdd * dt
        thd_g = G / (A * math.sqrt(1 + th ** 2))
        thd = min(thd_new, thd_g)
        th += thd * dt
        ks.append(A * th * np.exp(1j * th))
    return np.array(ks), dt

def build(out='sequence.seq', dwell=4e-6, gmax_frac=0.92, smax_frac=0.88, turn_spacing=1.0, smax_design=125.0, exc_dur=0.6e-3, te=2.4e-3):
    sysm = pp.Opts(max_grad=30, grad_unit='mT/m', max_slew=125 if smax_design <= 125 else smax_design, slew_unit='T/m/s',
                   rf_ringdown_time=20e-6, rf_dead_time=100e-6, adc_dead_time=10e-6, grad_raster_time=10e-6,
                   rf_raster_time=1e-6, adc_raster_time=100e-9, block_duration_raster=10e-6, gamma=GAMMA)
    k, dt = spiral_k(gmax_frac, smax_frac, turn_spacing, smax=smax_design)
    gr = sysm.grad_raster_time
    T = (len(k) - 1) * dt
    nr = int(math.floor(T / gr))
    tb = np.arange(nr + 1) * gr                      # raster boundaries
    kb = np.interp(tb, np.arange(len(k)) * dt, k.real) + 1j * np.interp(tb, np.arange(len(k)) * dt, k.imag)

    g = np.diff(kb) / gr                             # Hz/m at raster centres: exact k at boundaries
    # slew-limited ramp-down appended on both axes
    smax_hz = GAMMA * 125.0 * 0.9
    nramp = int(math.ceil(abs(g[-1]) / (smax_hz * gr))) + 1
    ramp = g[-1] * (1 - (np.arange(1, nramp + 1)) / nramp)
    gw = np.concatenate([g, ramp])
    gx = pp.make_arbitrary_grad('x', gw.real, system=sysm, first=0, last=0)
    gy = pp.make_arbitrary_grad('y', gw.imag, system=sysm, first=0, last=0)
    nadc = int(math.floor(T / dwell))
    adc = pp.make_adc(num_samples=nadc, dwell=dwell, delay=0, system=sysm)
    rf = pp.make_block_pulse(math.pi / 2, duration=exc_dur, system=sysm, use='excitation')
    seq = pp.Sequence(sysm)
    seq.add_block(rf)
    rfc = rf.delay + pp.calc_rf_center(rf)[0]
    first = adc.delay + dwell / 2
    gap = round((te - (pp.calc_duration(rf) - rfc) - first) / sysm.block_duration_raster) * sysm.block_duration_raster
    if gap > 0:
        seq.add_block(pp.make_delay(gap))
    seq.add_block(gx, gy, adc)
    seq.add_block(pp.make_delay(0.05))
    ok, rep = seq.check_timing()
    if not ok:
        raise RuntimeError(str(rep[:3]))
    seq.set_definition('FOV', [FOV, FOV, 0.005]); seq.set_definition('Name', 'spiral_out_b0')
    seq.write(out)
    return dict(readout_ms=nadc * dwell * 1e3, n_adc=nadc, max_g_mT=float(np.abs(gw).max() / GAMMA * 1e3))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq'); a = ap.parse_args()
    print(json.dumps(build(a.out)))

