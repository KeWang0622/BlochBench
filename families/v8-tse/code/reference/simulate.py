"""Simulate the exported TSE sequence with KomaMRI and write simulation.npz in the task schema."""
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
N = 18
assert len(adcs) == N and all(len(x) == N for x in adcs)
raw = sig.reshape(N, N)
kxy = kt[:2].T.reshape(N, N, 2)
times = np.concatenate(adcs).reshape(N, N)
exc = [r for r in rfs if r[1] < 120]; ref = [r for r in rfs if r[1] >= 120]
ex_t = np.array([r[0] for r in exc]); ref_t = np.array([r[0] for r in ref])
echo_idx = []; shot_idx = []
acq_shots = sorted(set(int(np.searchsorted(ex_t, t[0]) - 1) for t in times))
for t in times:
    e = int(np.searchsorted(ex_t, t[0]) - 1)
    n_ref = int(np.sum((ref_t > ex_t[e]) & (ref_t < t[0])))
    echo_idx.append(n_ref); shot_idx.append(acq_shots.index(e) + 1)
esp = float(np.median(np.diff(ref_t)[np.diff(ref_t) < 0.1]))
j0 = int(np.argmin(np.abs(kxy[:, N // 2, 1]))); e0 = int(np.searchsorted(ex_t, times[j0, 0]) - 1)
teff = float(times[j0, N // 2] - ex_t[e0])
np.savez(a.out, raw_signal=raw, kxy_cycles_per_m=kxy, adc_times_s=times, echo_index=np.array(echo_idx), shot_index=np.array(shot_idx),
         echo_spacing_s=esp, effective_echo_time_s=teff, sequence_sha256=R.sha256(a.seq), phantom_sha256=R.sha256(a.phantom))
print('simulated', raw.shape, 'ESP', esp, 'TEeff', teff)

