"""Simulate the exported 3D MP-RAGE with KomaMRI; write simulation.npz in the task schema."""
import argparse, numpy as np
import refkit as R
ap = argparse.ArgumentParser()
ap.add_argument('--seq', default='sequence.seq'); ap.add_argument('--phantom', required=True); ap.add_argument('--out', default='simulation.npz')
a = ap.parse_args()
ph = dict(np.load(a.phantom))
def expand3d(ph):
    rho = ph['density']; iz, iy, ix = np.nonzero(rho > 0); sub = ph['z_sub_offsets_m']; ns = len(sub); rep = lambda q: np.repeat(q, ns)
    return {'x': rep(ph['x_m'][ix]), 'y': rep(ph['y_m'][iy]), 'z': (ph['z_m'][iz][:, None] + sub[None, :]).ravel(), 'rho': rep(rho[iz, iy, ix] / ns),
            'T1': rep(ph['T1_s'][iz, iy, ix]), 'T2': rep(ph['T2_s'][iz, iy, ix]), 'dw': rep(2 * np.pi * ph['B0_Hz'][iz, iy, ix])}
sig = R.koma(a.seq, expand3d(ph))
seq = R.read_seq(a.seq)
rfs, adcs = R.rf_table(seq)
kt = seq.calculate_kspace()[0]
NX, NY, NZ = 20, 12, 6
assert len(adcs) == NZ * NY
raw = sig.reshape(NZ, NY, NX)
k = kt.T.reshape(NZ, NY, NX, 3)
times = np.concatenate(adcs).reshape(NZ, NY, NX)
rt = np.array([r[0] for r in rfs]); fl = np.array([r[1] for r in rfs])
inv = rt[fl > 90]; ro = rt[fl <= 90]
t9 = ro[ro < times[0, NY // 2, 0]].max(); ti = t9 - inv[inv < t9].max()
te = float(np.median([times.reshape(-1, NX)[n, NX // 2] - ro[ro < times.reshape(-1, NX)[n, 0]].max() for n in range(NZ * NY)]))
np.savez(a.out, raw_signal=raw, kxyz_cycles_per_m=k, adc_times_s=times, inversion_time_s=ti, echo_time_s=te,
         readout_tr_s=float(np.median(np.diff(ro)[np.diff(ro) < 0.05])), cycle_period_s=float(np.median(np.diff(inv))),
         readout_flip_angle_deg=float(np.median(fl[fl <= 90])), sequence_sha256=R.sha256(a.seq), phantom_sha256=R.sha256(a.phantom))
print('simulated', raw.shape, 'TI', ti, 'TE', te)

