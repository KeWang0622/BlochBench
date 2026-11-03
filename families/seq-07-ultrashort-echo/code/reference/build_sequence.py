"""Build the 2D UTE half-pulse radial sequence (reference design and control variants)."""
import argparse, numpy as np, pypulseq as pp
ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq'); ap.add_argument('--variant', default='reference')
a = ap.parse_args(); V = a.variant
GAM = 42.576e6; S = 135 * GAM * 0.95
sysd = pp.Opts(max_grad=34, grad_unit='mT/m', max_slew=135, slew_unit='T/m/s', rf_dead_time=100e-6, rf_ringdown_time=20e-6,
               adc_dead_time=10e-6, grad_raster_time=1e-5, rf_raster_time=1e-6, adc_raster_time=1e-7, block_duration_raster=1e-5)
N = 26; FOV = 0.208; THK = 0.0055; TR = 0.0065; FA = 11.0
NSP = {'pos_alt_design': 96, 'pos_alt_design2': 88, 'neg_too_few_spokes': 44}.get(V, 80)
G_RO = (14e-3 if V == 'pos_alt_design' else 10e-3) * GAM
dwell = 3e-6 if V == 'pos_alt_design2' else 2e-6
kmax = (N / 2) / FOV + 1.2 / FOV
inc = 117.0; NDUM = 240
q = lambda v: round(v / 1e-5) * 1e-5
qc = lambda v: np.ceil(v / 1e-5 - 1e-6) * 1e-5
# half sinc: the second half of the RF (after the peak) is omitted; RF ends at its peak
rf_dur = 0.8e-3 if V == 'pos_alt_design2' else 0.6e-3; tbw = 2.0
t = (np.arange(int(round(rf_dur / 1e-6))) + 0.5) * 1e-6 - rf_dur            # full-pulse time with peak at 0
bw = tbw / (2 * rf_dur)
env = np.sinc(bw * t) * (0.5 + 0.5 * np.cos(np.pi * t / rf_dur))    # main lobe only: first zero at the pulse start
G = bw / THK                                                                  # slice gradient, Hz/m
sig = env / (np.sum(env) * 1e-6) * (FA / 360.0)
rise = qc(G / S)
# ramp-down rephasing: after the RF ends, go G -> -G2 -> 0 with zero net area
def tail(G):
    for t1n in range(1, 200):
        t1 = t1n * 1e-5
        G2 = G - S * t1                                                       # value reached after t1 at slew S (may be negative)
        if G2 > 0: continue
        G2 = -G2; t2 = qc(G2 / S)
        a1 = (G - G2) * t1 / 2; a2 = -G2 * t2 / 2
        if a1 + a2 <= 0:
            # scale G2 so the net area is exactly zero with these raster times
            G2 = G * t1 / (t1 + t2)
            return t1, t2, G2
    raise RuntimeError
t1, t2, G2 = tail(G)
rf_delay = max(100e-6, rise)
def exc(pol):
    rf = pp.make_arbitrary_rf(sig.astype(complex), flip_angle=np.deg2rad(FA), system=sysd, delay=rf_delay, use='excitation', center=rf_dur)
    if V == 'neg_no_ramp_compensation':
        times = np.array([rf_delay - rise, rf_delay, rf_delay + rf_dur, rf_delay + rf_dur + rise])
        amps = pol * np.array([0, G, G, 0])
    else:
        times = np.array([rf_delay - rise, rf_delay, rf_delay + rf_dur, rf_delay + rf_dur + t1, rf_delay + rf_dur + t1 + t2])
        amps = pol * np.array([0, G, G, -G2, 0])
    gz = pp.make_extended_trapezoid('z', times=times, amplitudes=amps, system=sysd)
    return rf, gz
r_ro = qc(G_RO / S)
area_ramp = G_RO * r_ro / 2
flat = qc((kmax - area_ramp) / G_RO)
late = 1.0e-3 if V == 'neg_late_te' else 0.0
adc_delay = r_ro if V == 'neg_adc_on_flat_top' else 10e-6
ns = int((r_ro + flat - adc_delay) // dwell)
seq = pp.Sequence(sysd)
n_rf = 0
gsp = pp.make_trapezoid("z", area=300 if V != "pos_alt_design" else 450, system=sysd)
def add_tr(i_sp, pol, acq):
    global n_rf
    ph = (inc * n_rf * (n_rf + 1) / 2.0) % 360.0; n_rf += 1
    rf, gz = exc(pol)
    rf.phase_offset = np.deg2rad(ph)
    seq.add_block(rf, gz)
    if late > 0: seq.add_block(pp.make_delay(late))
    phi = 2 * np.pi * i_sp / NSP
    gx = pp.make_trapezoid('x', amplitude=G_RO * np.cos(phi), rise_time=r_ro, flat_time=flat, fall_time=r_ro, system=sysd)
    gy = pp.make_trapezoid('y', amplitude=G_RO * np.sin(phi), rise_time=r_ro, flat_time=flat, fall_time=r_ro, system=sysd)
    adc = pp.make_adc(ns, dwell=dwell, delay=adc_delay, system=sysd, phase_offset=np.deg2rad(ph))
    if acq: seq.add_block(gx, gy, adc)
    else: seq.add_block(gx, gy)
    seq.add_block(gsp)
    used = sum(seq.block_durations[k] for k in list(seq.block_durations)[-(3 + (late > 0)):])
    seq.add_block(pp.make_delay(q(TR - used)))
for d in range(NDUM):
    add_tr(0, 1 if d % 2 == 0 else -1, False)
for i in range(NSP):
    add_tr(i, 1, True)
    add_tr(i, 1 if V == 'neg_no_polarity_alternation' else -1, True)
ok, err = seq.check_timing(); assert ok, err[:4]
seq.set_definition('FOV', [FOV, FOV, THK]); seq.set_definition('Name', 'ute_' + V)
seq.write(a.out)
print('wrote', a.out, 'spokes', NSP, 'samples', ns, 'G slice mT/m', G / GAM * 1e3, 'tail us', (t1 + t2) * 1e6, 'readout us', (r_ro + flat) * 1e6)

