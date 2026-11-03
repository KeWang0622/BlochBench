"""Simulate the exported EPI with KomaMRI; write simulation.npz in the task schema."""
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
ns = len(adcs[0]); na = len(adcs)
raw = sig.reshape(na, ns)
k = kt.T.reshape(na, ns, 3)
times = np.concatenate(adcs).reshape(na, ns)
nav = np.zeros(na, bool); nav[:3] = True
# effective TE: time where the ky=0 imaging echo crosses kx=0 (interpolated on the sampled trajectory)
img = np.nonzero(~nav)[0]
j0 = img[int(np.argmin(np.abs(k[img, ns // 2, 1])))]
kx = k[j0, :, 0]; tt = times[j0]
order = np.argsort(kx)
t_cross = float(np.interp(0.0, kx[order], tt[order]))
crossings = []
for j in img:
    o = np.argsort(k[j, :, 0]); crossings.append(np.interp(0.0, k[j, o, 0], times[j, o]))
esp = float(np.median(np.diff(crossings)))
np.savez(a.out, raw_signal=raw, kxy_cycles_per_m=k[:, :, :2], adc_times_s=times, is_navigator=nav, fov_m=0.21, matrix=np.array([24, 24]),
         effective_echo_time_s=t_cross - rfs[0][0], echo_spacing_s=esp, sequence_sha256=R.sha256(a.seq), phantom_sha256=R.sha256(a.phantom))
print('simulated', raw.shape, 'TE', t_cross - rfs[0][0], 'ESP', esp)

