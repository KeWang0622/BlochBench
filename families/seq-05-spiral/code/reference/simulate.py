"""Simulate the exported spiral sequence with KomaMRI; write simulation.npz in the task schema."""
import argparse, numpy as np
import refkit as R
ap = argparse.ArgumentParser()
ap.add_argument('--seq', default='sequence.seq'); ap.add_argument('--phantom', required=True); ap.add_argument('--out', default='simulation.npz')
a = ap.parse_args()
iso = R.expand_columns(dict(np.load(a.phantom)))
sig = R.koma(a.seq, iso)
seq = R.read_seq(a.seq)
rfs, adcs = R.rf_table(seq)
kt = seq.calculate_kspace()[0]
na = len(adcs); ns = len(adcs[0])
k = kt.T.reshape(na, ns, 3)
times = np.concatenate(adcs).reshape(na, ns)
exc = np.array([r[0] for r in rfs])
te = float(np.median([t[0] - exc[exc < t[0]].max() for t in times]))
np.savez(a.out, raw_signal=sig.reshape(na, ns), kxy_cycles_per_m=k[:, :, :2], adc_times_s=times, fov_m=0.234, matrix=np.array([36, 36]),
         gradient_delay_s=0.0, echo_time_s=te, sequence_sha256=R.sha256(a.seq), phantom_sha256=R.sha256(a.phantom))
print('simulated', na, ns, 'TE', te)

