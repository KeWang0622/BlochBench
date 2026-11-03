"""Build the single-shot spin-echo EPI diffusion sequence (reference design and control variants)."""
import argparse, json, numpy as np, pypulseq as pp
from bcalc import bmatrix
ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq'); ap.add_argument('--variant', default='reference')
a = ap.parse_args(); V = a.variant
sysd = pp.Opts(max_grad=42, grad_unit='mT/m', max_slew=160, slew_unit='T/m/s', rf_dead_time=100e-6, rf_ringdown_time=20e-6,
               adc_dead_time=10e-6, grad_raster_time=1e-5, rf_raster_time=1e-6, adc_raster_time=1e-7, block_duration_raster=1e-5)
N = 24; FOV = 0.204; DK = 1 / FOV; THK = 0.0045; TE = 0.072; TR = 3.2; BT = 1200.0
S = 160 * 42.576e6 * 0.999
rise = 150e-6; flat = 40e-6; G = rise * S; dwell = 4e-6
lobe_dur = 2 * rise + flat; A_lobe = G * (rise + flat); blip_t = 40e-6
ns = int((lobe_dur - 2 * blip_t - 10e-6) // dwell)
q = lambda v: round(v / 1e-5) * 1e-5
rf, gz, gzr = pp.make_sinc_pulse(flip_angle=np.pi / 2, duration=2e-3, slice_thickness=THK, apodization=0.5, time_bw_product=4,
                                 phase_offset=np.pi / 2, system=sysd, return_gz=True, use='excitation')
rf180, gz180, _ = pp.make_sinc_pulse(flip_angle=np.pi, duration=2.4e-3, slice_thickness=THK * 1.2, apodization=0.5, time_bw_product=4,
                                     phase_offset=0.0, system=sysd, return_gz=True, use='refocusing')
gzr = pp.make_trapezoid('z', area=0.0 if V == 'neg_no_slice_rephaser' else gzr.area, duration=1.0e-3, system=sysd)
crush = {'pos_alt_timing': 2200.0, 'pos_alt_crushers': 1000.0}.get(V, 1600.0)
T_C = 2.0e-3
gc = pp.make_trapezoid('z', area=crush, duration=T_C, system=sysd)
gx_pre = pp.make_trapezoid('x', area=-A_lobe / 2, duration=1.0e-3, system=sysd)
gy_pre = pp.make_trapezoid('y', area=-(N // 2) * DK, duration=1.0e-3, system=sysd)
def lobe(sign):
    return pp.make_trapezoid('x', amplitude=sign * G, rise_time=rise, flat_time=flat, fall_time=rise, system=sysd)
def blip():
    return pp.make_extended_trapezoid('y', times=np.array([0, blip_t, 2 * blip_t]) + lobe_dur - 2 * blip_t, amplitudes=np.array([0, DK / blip_t, 0]), system=sysd)
adc = pp.make_adc(ns, dwell=dwell, delay=10e-6, system=sysd, phase_offset=np.pi / 2)
# diffusion lobe timing
G_d = 30e-3 * 42.576e6
d_rise = 300e-6
B_ex = pp.calc_duration(rf, gz); tc_ex = rf.delay + rf.center
B_180 = pp.calc_duration(rf180, gz180); tc_180 = rf180.delay + rf180.center
t_echo_from_train_start = 1.0e-3 + (N // 2) * lobe_dur + lobe_dur / 2    # pre-phasers then N/2 lobes then half lobe
half = TE / 2
# first half: exc tail, rephaser, diffusion lobe, fill1, crusher, 180 first half
# second half: 180 tail, crusher, fill2, diffusion lobe, fill3, readout to echo
avail1 = half - (B_ex - tc_ex) - 1.0e-3 - T_C - tc_180
avail2 = half - (B_180 - tc_180) - T_C - t_echo_from_train_start
d_dur = q(min(avail1, avail2) - 0.2e-3 - (4e-3 if V == 'pos_alt_timing' else 0.0))
d_flat = d_dur - 2 * d_rise
fill1 = q(avail1 - d_dur); fill2 = q(avail2 - d_dur)
if V == 'neg_spin_echo_misaligned':
    fill1 = q(fill1 + 0.15e-3); fill2 = q(fill2 - 0.15e-3)
assert fill1 >= 0 and fill2 >= 0, (fill1, fill2)
dirs = {'b0': None, 'x': 'x', 'y': 'y', 'z': 'z'}
vols = ['b0', 'x', 'y', 'z']
def make_seq(amp_scale, nodummy=False):
    seq = pp.Sequence(sysd)
    plan = ([] if nodummy else ['dummy']) + vols
    for n, vname in enumerate(plan):
        ax = dirs.get(vname) if vname != 'dummy' else None
        acq = vname != 'dummy'
        amp = (G_d * amp_scale.get(vname, 1.0)) if ax else 0.0
        def dlobe(sign=1):
            if not ax:
                return pp.make_delay(d_dur)
            return pp.make_trapezoid(ax, amplitude=sign * amp, rise_time=d_rise, flat_time=d_flat, fall_time=d_rise, system=sysd)
        seq.add_block(rf, gz); seq.add_block(gzr); seq.add_block(dlobe())
        if fill1 > 0: seq.add_block(pp.make_delay(fill1))
        seq.add_block(gc); seq.add_block(rf180, gz180); seq.add_block(gc)
        if fill2 > 0: seq.add_block(pp.make_delay(fill2))
        seq.add_block(dlobe(-1 if V == 'neg_diffusion_lobes_opposite_polarity' else 1))
        seq.add_block(gx_pre, gy_pre)
        for j in range(N):
            ev = [lobe(1 if j % 2 == 0 else -1)]
            if acq: ev.append(adc)
            if j < N - 1: ev.append(blip())
            seq.add_block(*ev)
        seq.add_block(pp.make_trapezoid('z', area=4000, system=sysd))
        pad = q((n + 1) * TR - seq.duration()[0])
        seq.add_block(pp.make_delay(pad))
    return seq
def realized_b(seq):
    from refkit import rf_table
    rfs, adcs = rf_table(seq)
    exc = [r[0] for r in rfs if r[1] < 135]; ref = [r[0] for r in rfs if r[1] >= 135]
    kt = seq.calculate_kspace()[0]
    nsamp = len(adcs[0]); out = []
    for v in range(len(adcs) // N):
        j0 = v * N + N // 2
        t_ad = adcs[j0]; kx = kt[0, j0 * nsamp:(j0 + 1) * nsamp]
        o = np.argsort(kx); te = float(np.interp(0.0, kx[o], t_ad[o]))
        e = max(t for t in exc if t < te); rr = [t for t in ref if e < t < te]
        out.append(np.trace(bmatrix(seq, e, rr, te)))
    return np.array(out)
scale = {}
seq = make_seq(scale, nodummy=(V == 'neg_no_dummy_volume'))
if V == 'neg_nominal_stejskal_tanner':
    # mistake: amplitude from the rectangular-pulse Stejskal-Tanner formula with delta = flat time, ignoring ramps, crushers and imaging gradients
    gam = 2 * np.pi * 42.576e6; Delta = d_dur + fill1 + 2 * T_C + B_180
    for v in 'xyz':
        g_needed = np.sqrt(BT * 1e6 / (gam ** 2 * d_flat ** 2 * (Delta - d_flat / 3)))
        scale[v] = g_needed * 42.576e6 / G_d
    seq = make_seq(scale)
else:
    for it in range(3):
        b = realized_b(seq)
        for i, v in enumerate(vols):
            if v != 'b0':
                scale[v] = scale.get(v, 1.0) * np.sqrt((BT - b[0] * 0) / b[i]) if b[i] > 0 else 1.0
        seq = make_seq(scale, nodummy=(V == 'neg_no_dummy_volume'))
ok, err = seq.check_timing(); assert ok, err[:4]
b = realized_b(seq)
seq.set_definition('FOV', [FOV, FOV, THK]); seq.set_definition('Name', 'sedwi_' + V)
seq.write(a.out)
json.dump({'b_trace_s_per_mm2': b.tolist(), 'volumes': vols}, open('build_info.json', 'w'))
print('wrote', a.out, 'b', np.round(b, 2), 'diff dur', d_dur, 'fills', fill1, fill2, 'G_d mT/m', G_d / 42.576e3 * max(scale.values() or [1]))

