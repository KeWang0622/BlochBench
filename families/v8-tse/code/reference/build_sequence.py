"""Build the 2D turbo spin-echo sequence (reference design and control variants)."""
import argparse, numpy as np, pypulseq as pp
ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq'); ap.add_argument('--variant', default='reference')
a = ap.parse_args(); V = a.variant
sysd = pp.Opts(max_grad=26, grad_unit='mT/m', max_slew=150, slew_unit='T/m/s', rf_dead_time=100e-6, rf_ringdown_time=20e-6,
               adc_dead_time=10e-6, grad_raster_time=1e-5, rf_raster_time=1e-6, adc_raster_time=1e-7, block_duration_raster=1e-5)
N = 18; FOV = 0.216; DK = 1 / FOV; THK = 0.0035; ETL = 9; NSH = 2; TE_EFF = 0.044; TR = 2.0
ESP = 0.011 if V == 'pos_alt_ordering' else 0.0088
ref_dur = 1.8e-3 if V == 'pos_alt_ordering' else 2.0e-3
crush_area = 0.0 if V == 'neg_no_crushers' else (1200.0 if V == 'pos_alt_ordering' else 800.0)
dwell = 30e-6
ex_phase = np.pi / 2
ref_phase = ex_phase if V == 'neg_cp_not_cpmg' else 0.0
rf_ex, gz_ex, gzr_ex = pp.make_sinc_pulse(flip_angle=np.pi / 2, duration=2e-3, slice_thickness=THK, apodization=0.5, time_bw_product=4,
                                          phase_offset=ex_phase, system=sysd, return_gz=True, use='excitation')
rf_ref, gz_ref, _ = pp.make_sinc_pulse(flip_angle=np.deg2rad(135), duration=ref_dur, slice_thickness=THK, apodization=0.5, time_bw_product=4,
                                       phase_offset=ref_phase, system=sysd, return_gz=True, use='refocusing')
gx = pp.make_trapezoid('x', flat_area=N * DK, flat_time=N * dwell, system=sysd)
# echo (sample 12) at the centre of the readout gradient: Pulseq samples sit at delay + (i+0.5) dwell
adc_delay = gx.rise_time if V == 'neg_echo_off_readout_centre' else gx.rise_time - dwell / 2
adc = pp.make_adc(N, dwell=dwell, delay=adc_delay, system=sysd, phase_offset=ex_phase)
k0 = gx.amplitude * gx.rise_time / 2 + (adc_delay - gx.rise_time + (N // 2 + 0.5) * dwell) * gx.amplitude
pre_area = -k0 if V == 'neg_prephaser_wrong_sign' else k0   # the refocusing pulse inverts the prephaser moment
gzr = pp.make_trapezoid('z', area=gzr_ex.area, system=sysd)
T_REPH = max(pp.calc_duration(gzr), 0.5e-3)
gzr = pp.make_trapezoid('z', area=0.0 if V == 'neg_no_slice_rephaser' else gzr_ex.area, duration=T_REPH, system=sysd)
gx_pre = pp.make_trapezoid('x', area=pre_area, duration=T_REPH, system=sysd)
gc = pp.make_trapezoid('z', area=crush_area, system=sysd) if crush_area else None
t_pe = 0.5e-3
d_ex_post = pp.calc_duration(rf_ex, gz_ex) - (rf_ex.delay + rf_ex.center)
d_ref_pre = rf_ref.delay + rf_ref.center
d_ref_post = pp.calc_duration(rf_ref, gz_ref) - d_ref_pre
d_c = pp.calc_duration(gc) if gc else 0.0
ro_dur = pp.calc_duration(gx, adc)
t_k0 = adc_delay + (N // 2 + 0.5) * dwell
q = lambda v: round(v / 1e-5) * 1e-5
fill1 = q(ESP / 2 - d_ex_post - T_REPH - d_c - d_ref_pre)
fill2 = q(ESP / 2 - d_ref_post - d_c - t_pe - t_k0)
fill3 = q(ESP / 2 - (ro_dur - t_k0) - t_pe - d_c - d_ref_pre)
assert min(fill1, fill2, fill3) >= 0, (fill1, fill2, fill3)

def line(e, s):
    if V == 'neg_centre_first_echo':
        order = np.argsort(np.abs(np.arange(N) - N // 2), kind='stable')   # centric: ky=0 on the first echo
        return int(order[e * NSH + s])
    if V == 'pos_alt_ordering':
        return int((NSH * e + s + 3) % N)                                    # ky=0 on echo index 3 with ESP 11 ms
    return int(NSH * e + s)                                                  # ky=0 on echo index 4 with ESP 8.8 ms

seq = pp.Sequence(sysd)
gsp = pp.make_trapezoid('z', area=4 * 800.0, system=sysd)
shots = ([-1] if V != 'neg_no_dummy_shot' else []) + list(range(NSH))
for s in shots:
    t_shot = 0.0
    seq.add_block(rf_ex, gz_ex); seq.add_block(gzr, gx_pre); seq.add_block(pp.make_delay(fill1)) if fill1 > 0 else None
    for e in range(ETL):
        j = line(e, max(s, 0)); ky = (j - N // 2) * DK
        if gc: seq.add_block(gc)
        seq.add_block(rf_ref, gz_ref)
        if gc: seq.add_block(gc)
        seq.add_block(pp.make_trapezoid('y', area=ky, duration=t_pe, system=sysd))
        if fill2 > 0: seq.add_block(pp.make_delay(fill2))
        if s >= 0: seq.add_block(gx, adc)
        else: seq.add_block(gx)
        rew = 0.0 if V == 'neg_no_pe_rewinder' else -ky
        seq.add_block(pp.make_trapezoid('y', area=rew, duration=t_pe, system=sysd))
        if fill3 > 0: seq.add_block(pp.make_delay(fill3))
    seq.add_block(gsp)
    # pad to TR measured between excitation centres
    dur_so_far = sum(seq.block_durations[k] for k in list(seq.block_durations)[-(len(seq.block_durations) - (0 if s == shots[0] else 0)):])
    seq_dur = seq.duration()[0]
    t_ex_centre = rf_ex.delay + rf_ex.center
    n_done = shots.index(s) + 1
    pad = q(n_done * TR - seq_dur)
    seq.add_block(pp.make_delay(pad))
ok, err = seq.check_timing(); assert ok, err[:4]
seq.set_definition('FOV', [FOV, FOV, THK]); seq.set_definition('Name', 'tse_' + V)
seq.write(a.out)
print('wrote', a.out, seq.duration()[0], 'fills', fill1, fill2, fill3)

