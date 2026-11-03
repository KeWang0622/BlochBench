"""Build the single-shot gradient-echo EPI with ramp sampling and navigator echoes (reference + variants)."""
import argparse, numpy as np, pypulseq as pp
ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq'); ap.add_argument('--variant', default='reference')
a = ap.parse_args(); V = a.variant
sysd = pp.Opts(max_grad=28, grad_unit='mT/m', max_slew=140, slew_unit='T/m/s', rf_dead_time=100e-6, rf_ringdown_time=20e-6,
               adc_dead_time=10e-6, grad_raster_time=1e-5, rf_raster_time=1e-6, adc_raster_time=1e-7, block_duration_raster=1e-5)
N = 24; FOV = 0.21; DK = 1 / FOV; THK = 0.0045; TE = 0.024
S = 140 * 42.576e6 * 0.999
rise = 140e-6 if V == 'pos_alt_design' else 120e-6
flat = {'pos_alt_design': 100e-6, 'neg_flat_top_only': 200e-6}.get(V, 120e-6)
G = rise * S
dwell = 3e-6 if V == 'pos_alt_design' else 4e-6
lobe_dur = 2 * rise + flat
A_lobe = G * (rise + flat)
blip_t = 40e-6
if V == 'neg_flat_top_only':
    adc_delay = rise; ns = int(round(flat / dwell))
else:
    adc_delay = 10e-6; ns = int((lobe_dur - 2 * blip_t - adc_delay) // dwell)
rf, gz, gzr = pp.make_sinc_pulse(flip_angle=np.pi / 2, duration=1.5e-3, slice_thickness=THK, apodization=0.5, time_bw_product=4,
                                 system=sysd, return_gz=True, use='excitation')
gzr = pp.make_trapezoid('z', area=0.0 if V == 'neg_no_slice_rephaser' else gzr.area, duration=1.0e-3, system=sysd)
gx_pre = pp.make_trapezoid('x', area=-A_lobe / 2, duration=1.0e-3, system=sysd)
def lobe(sign):
    return pp.make_trapezoid('x', amplitude=sign * G, rise_time=rise, flat_time=flat, fall_time=rise, system=sysd)
amp_b = DK / blip_t
blip_delay = 0.0 if V == 'neg_blip_during_adc' else lobe_dur - 2 * blip_t
def blip():
    return pp.make_extended_trapezoid('y', times=np.array([0, blip_t, 2 * blip_t]) + blip_delay, amplitudes=np.array([0, amp_b, 0]), system=sysd)
adc = pp.make_adc(ns, dwell=dwell, delay=adc_delay, system=sysd)
gx_rew = pp.make_trapezoid('x', area=-A_lobe, duration=1.0e-3, system=sysd)
gy_pre = pp.make_trapezoid('y', area=-(N // 2) * DK, duration=1.0e-3, system=sysd)
NNAV = 3
B0 = pp.calc_duration(rf, gz); tc = rf.delay + rf.center
B1 = pp.calc_duration(gzr, gx_pre); Brew = pp.calc_duration(gx_rew, gy_pre)
k_echo = N // 2 - 1 if V == 'neg_te_wrong_echo' else N // 2
fill = TE - ((B0 - tc) + B1 + NNAV * lobe_dur + Brew + k_echo * lobe_dur + lobe_dur / 2)
fill = round(fill / 1e-5) * 1e-5
assert fill > 0, fill
seq = pp.Sequence(sysd)
seq.add_block(rf, gz); seq.add_block(gzr, gx_pre); seq.add_block(pp.make_delay(fill))
for n in range(NNAV):
    seq.add_block(lobe(1 if n % 2 == 0 else -1), adc)
seq.add_block(gx_rew, gy_pre)
for j in range(N):
    ev = [lobe(1 if j % 2 == 0 else -1), adc]
    if V == 'neg_blip_during_adc':
        if j > 0: ev.append(blip())
    elif j < N - 1:
        ev.append(blip())
    seq.add_block(*ev)
seq.add_block(pp.make_trapezoid('z', area=4000, system=sysd))
ok, err = seq.check_timing(); assert ok, err[:4]
seq.set_definition('FOV', [FOV, FOV, THK]); seq.set_definition('Name', 'epi_' + V)
seq.write(a.out)
print('wrote', a.out, 'ns', ns, 'ESP', lobe_dur, 'peak mT/m', G / 42.576e3, 'fill', fill)

