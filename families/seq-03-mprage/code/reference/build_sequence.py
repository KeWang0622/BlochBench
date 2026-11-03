"""Build the 3D MP-RAGE sequence (reference design and control variants)."""
import argparse, json, numpy as np, pypulseq as pp
ap = argparse.ArgumentParser(); ap.add_argument('--out', default='sequence.seq'); ap.add_argument('--variant', default='reference')
a = ap.parse_args(); V = a.variant
sysd = pp.Opts(max_grad=30, grad_unit='mT/m', max_slew=110, slew_unit='T/m/s', rf_dead_time=100e-6, rf_ringdown_time=20e-6,
               adc_dead_time=10e-6, grad_raster_time=1e-5, rf_raster_time=1e-6, adc_raster_time=1e-7, block_duration_raster=1e-5)
NX, NY, NZ = 20, 12, 6; FOVX, FOVY, FOVZ = 0.240, 0.144, 0.054; DKX = 1 / FOVX; DKY = 1 / FOVY; DKZ = 1 / FOVZ
TRG = 0.0065; FA = 7.0; TCYC = 2.3; TE = 0.0028; T1NULL = 0.78
q = lambda v: round(v / 1e-5) * 1e-5
dwell = {'pos_alt_design': 20e-6, 'pos_alt_spoiling': 20e-6}.get(V, 40e-6)
inc = 50.0 if V == 'pos_alt_design' else 117.0
spoil_area = {'pos_alt_design': 400.0, 'pos_alt_spoiling': 500.0}.get(V, 250.0)
ndummy = 2 if V == 'neg_two_dummy_cycles' else {'pos_alt_design': 6, 'pos_alt_spoiling': 7}.get(V, 5)
korder = [3, 2, 4, 1, 5, 0] if V == 'pos_alt_design' else list(range(NZ))
rf_inv = pp.make_block_pulse(flip_angle=np.pi, duration=0.5e-3, system=sysd, use='inversion')
rf = pp.make_block_pulse(flip_angle=np.deg2rad(FA), duration=0.1e-3, system=sysd, use='excitation')
gx = pp.make_trapezoid('x', flat_area=NX * DKX, flat_time=NX * dwell, system=sysd)
adc = pp.make_adc(NX, dwell=dwell, delay=gx.rise_time, system=sysd)
gx_pre = pp.make_trapezoid('x', area=-(gx.amplitude * gx.rise_time / 2 + (NX // 2 + 0.5) * DKX), duration=0.6e-3, system=sysd)
inv_spoil = pp.make_trapezoid('z', area=3000, system=sysd)
t_rf_c = 100e-6 + 0.05e-3; rf_blk = 100e-6 + 0.1e-3 + 20e-6
t_k0 = gx.rise_time if V == 'neg_te_to_adc_start' else gx.rise_time + (NX // 2 + 0.5) * dwell
fill_te = q(TE - (rf_blk - t_rf_c) - 0.6e-3 - t_k0)
ro = pp.calc_duration(gx, adc)
gz_sp = pp.make_trapezoid('z', area=spoil_area, duration=0.8e-3, system=sysd)
rew_dur = 0.8e-3
fill_tr = q(TRG - rf_blk - fill_te - 0.6e-3 - ro - rew_dur)
assert fill_te >= 0 and fill_tr >= 0, (fill_te, fill_tr)
inv_c = 100e-6 + 0.25e-3

def null_ti(T1, centre_pulse=NY // 2):
    """TI (inversion centre -> centre of the readout pulse that acquires ky=0) nulling T1 in the cycle steady state."""
    E = lambda dt: np.exp(-dt / T1); ca = np.cos(np.deg2rad(FA))
    def mz_at_centre(ti):
        mz = 1.0
        for _ in range(30):
            mz = -mz                                      # inversion
            t_first = ti - centre_pulse * TRG
            mz = 1 - (1 - mz) * E(t_first)
            at_c = None
            for p in range(NY):
                if p == centre_pulse: at_c = mz
                mz = mz * ca
                if p < NY - 1: mz = 1 - (1 - mz) * E(TRG)
            t_rest = TCYC - t_first - (NY - 1) * TRG
            mz = 1 - (1 - mz) * E(t_rest)
        return at_c
    lo, hi = centre_pulse * TRG + 0.01, 1.5
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if mz_at_centre(mid) < 0: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)

if V == 'neg_naive_ti':
    TI = T1NULL * np.log(2)                               # textbook single-inversion null, ignores the train and incomplete recovery
elif V == 'neg_ti_to_train_start':
    TI = null_ti(T1NULL, centre_pulse=0) + 0 * 0          # nulls at the first readout instead of the ky = 0 readout
else:
    TI = null_ti(T1NULL)
TI = q(TI)
seq = pp.Sequence(sysd)
dur = lambda: float(sum(seq.block_durations.values()))
n_rf = 0
def phase(n):
    if V == 'neg_no_rf_spoiling':
        return 0.0
    return (inc * n * (n + 1) / 2.0) % 360.0
cycles = [-1] * ndummy + korder
for c in cycles:
    t0 = dur()
    seq.add_block(rf_inv); seq.add_block(inv_spoil)
    t_inv = t0 + inv_c
    t_first = t_inv + TI - (NY // 2) * TRG if V != 'neg_ti_to_train_start' else t_inv + TI
    gap = q(t_first - t_rf_c - dur()); assert gap >= 0, gap
    seq.add_block(pp.make_delay(gap))
    kz = ((c if c >= 0 else NZ // 2) - NZ // 2) * DKZ
    for j in range(NY):
        ky = (j - NY // 2) * DKY
        ph = phase(n_rf); n_rf += 1
        rf.phase_offset = np.deg2rad(ph); adc.phase_offset = np.deg2rad(ph)
        seq.add_block(rf)
        if fill_te > 0: seq.add_block(pp.make_delay(fill_te))
        seq.add_block(gx_pre, pp.make_trapezoid('y', area=ky, duration=0.6e-3, system=sysd), pp.make_trapezoid('z', area=kz, duration=0.6e-3, system=sysd))
        if c >= 0: seq.add_block(gx, adc)
        else: seq.add_block(gx)
        seq.add_block(pp.make_trapezoid('y', area=-ky, duration=rew_dur, system=sysd), pp.make_trapezoid('z', area=-kz + spoil_area, duration=rew_dur, system=sysd))
        if fill_tr > 0: seq.add_block(pp.make_delay(fill_tr))
    seq.add_block(pp.make_delay(q(t0 + TCYC - dur())))
ok, err = seq.check_timing(); assert ok, err[:4]
seq.set_definition('FOV', [FOVX, FOVY, FOVZ]); seq.set_definition('Name', 'mprage_' + V)
seq.write(a.out)
print('wrote', a.out, 'TI', TI, 'duration', dur(), 'fills', fill_te, fill_tr)

