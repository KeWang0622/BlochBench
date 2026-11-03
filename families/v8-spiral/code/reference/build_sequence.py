"""Build the interleaved spiral-out gradient-echo sequence (reference design and control variants)."""
import argparse, numpy as np, pypulseq as pp
ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq'); ap.add_argument('--variant', default='reference')
a = ap.parse_args(); V = a.variant
GAM = 42.576e6
GMAX, SMAX = 22e-3 * GAM, 90.0 * GAM
sysd = pp.Opts(max_grad=22, grad_unit='mT/m', max_slew=90 if V != 'neg_slew_violation' else 125, slew_unit='T/m/s', rf_dead_time=100e-6, rf_ringdown_time=20e-6,
               adc_dead_time=10e-6, grad_raster_time=1e-5, rf_raster_time=1e-6, adc_raster_time=1e-7, block_duration_raster=1e-5)
N = 36; FOV = 0.234; THK = 0.0045; TE = 0.0027; TR = 3.0
NINT = {'pos_alt_design': 12}.get(V, 6)
NACQ = NINT - 1 if V == 'neg_undersampled' else NINT
dwell = 2e-6 if V == 'pos_alt_design' else 4e-6
kmax = (N / 2) / FOV + 1.1 / FOV   # outer envelope of the union of interleaves must still cover the disc
DT = 1e-5
s_design = (120.0 if V == 'neg_slew_violation' else 90.0) * GAM * 0.9
g_design = GMAX * 0.97

def design(nint, s_lim=None, g_lim=None):
    """Archimedean spiral k = lam*theta*exp(i theta), time-optimal along the curve (Lustig-style forward/backward
    pass with curvature-limited speed), resampled on the gradient raster DT."""
    s_lim = s_design if s_lim is None else s_lim; g_lim = g_design if g_lim is None else g_lim
    lam = nint / (2 * np.pi * FOV)
    th = np.linspace(0, kmax / lam, 400000)
    C = lam * th * np.exp(1j * th)
    ds = np.abs(np.diff(C)); sarc = np.concatenate([[0], np.cumsum(ds)])
    d1 = np.gradient(C, sarc); d2 = np.gradient(d1, sarc)
    kap = np.abs(d2) + 1e-9
    vmax = np.minimum(g_lim, np.sqrt(s_lim / kap))
    v = np.zeros_like(sarc); v[0] = 0.0
    for i in range(len(sarc) - 1):
        at2 = max(s_lim ** 2 - (v[i] ** 2 * kap[i]) ** 2, 0.0)
        v[i + 1] = min(vmax[i + 1], np.sqrt(v[i] ** 2 + 2 * ds[i] * np.sqrt(at2)))
    v = np.maximum(v, 1e-3)
    t = np.concatenate([[0], np.cumsum(ds / (0.5 * (v[1:] + v[:-1])))])
    tn = np.arange(0, t[-1], DT)
    kr = np.interp(tn, t, C.real); ki = np.interp(tn, t, C.imag)
    k = kr + 1j * ki
    g = np.diff(k) / DT
    tail = []; gl = g[-1]
    while abs(gl) > 0:
        step = s_lim * DT
        gl = 0j if abs(gl) <= step else gl * (1 - step / abs(gl)); tail.append(gl)
    return np.concatenate([g, np.array(tail)])

g = design(NINT)
rf, gz, gzr = pp.make_sinc_pulse(flip_angle=np.pi / 2, duration=2e-3, slice_thickness=THK, apodization=0.5, time_bw_product=4,
                                 system=sysd, return_gz=True, use='excitation')
gzr = pp.make_trapezoid('z', area=0.0 if V == 'neg_no_slice_rephaser' else gzr.area, duration=1.0e-3, system=sysd)
n_ro = int(np.floor((len(g) * DT - 2 * 10e-6) / dwell))
B0 = pp.calc_duration(rf, gz); tc = rf.delay + rf.center
fill = round((TE - (B0 - tc) - 1.0e-3 - 10e-6) / 1e-5) * 1e-5
seq = pp.Sequence(sysd)
for i in range(NACQ):
    rot = np.exp(2j * np.pi * i / NINT)
    gi = g * rot
    gx = pp.make_arbitrary_grad('x', waveform=np.real(gi), first=0, last=0, system=sysd)
    gy = pp.make_arbitrary_grad('y', waveform=np.imag(gi), first=0, last=0, system=sysd)
    adc = pp.make_adc(n_ro, dwell=dwell, delay=10e-6, system=sysd)
    seq.add_block(rf, gz); seq.add_block(gzr)
    if fill > 0: seq.add_block(pp.make_delay(fill))
    seq.add_block(gx, gy, adc)
    seq.add_block(pp.make_trapezoid('z', area=4000, system=sysd))
    seq.add_block(pp.make_delay(round(((i + 1) * TR - seq.duration()[0]) / 1e-5) * 1e-5))
ok, err = seq.check_timing(); assert ok, err[:4]
seq.set_definition('FOV', [FOV, FOV, THK]); seq.set_definition('Name', 'spiral_' + V)
seq.write(a.out)
print('wrote', a.out, 'nint', NINT, 'readout ms', len(g) * DT * 1e3, 'samples', n_ro, 'max g mT/m', np.abs(g).max() / GAM * 1e3)

