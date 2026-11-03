"""Simulate the exported UTE sequence with KomaMRI; write simulation.npz in the task schema."""
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
k = kt.T.reshape(na, ns, 3); times = np.concatenate(adcs).reshape(na, ns)
# RF end times (last RF sample) from the block table
ends = []; t = 0.0
for kk in sorted(seq.block_events):
    b = seq.get_block(kk)
    if b.rf is not None: ends.append(t + b.rf.delay + b.rf.t[-1] + 0.5e-6)
    t += float(seq.block_durations[kk])
ends = np.array(ends)
te = float(np.median([tt[0] - ends[ends < tt[0]].max() for tt in times]))
np.savez(a.out, raw_signal=sig.reshape(na, ns), kxy_cycles_per_m=k[:, :, :2], adc_times_s=times, pair_index=np.repeat(np.arange(na // 2), 2),
         fov_m=0.208, matrix=np.array([26, 26]), ute_echo_time_s=te, sequence_sha256=R.sha256(a.seq), phantom_sha256=R.sha256(a.phantom))
print('simulated', na, ns, 'TE_ute', te)

