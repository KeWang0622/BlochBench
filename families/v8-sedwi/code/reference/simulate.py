"""Simulate the exported SE-EPI DWI with KomaMRI (one replay per tissue) and apply the stated diffusion attenuation."""
import argparse, json, numpy as np
import refkit as R
from bcalc import bmatrix
ap = argparse.ArgumentParser()
ap.add_argument('--seq', default='sequence.seq'); ap.add_argument('--phantom', required=True); ap.add_argument('--out', default='simulation.npz')
a = ap.parse_args()
ph = dict(np.load(a.phantom))
seq = R.read_seq(a.seq)
rfs, adcs = R.rf_table(seq)
kt = seq.calculate_kspace()[0]
N = 24; na = len(adcs); ns = len(adcs[0]); nvol = na // N
times = np.concatenate(adcs).reshape(na, ns); k = kt.T.reshape(na, ns, 3)
exc = [r[0] for r in rfs if r[1] < 135]; ref = [r[0] for r in rfs if r[1] >= 135]
bvals = []; B_all = []; tes = []
for v in range(nvol):
    j0 = v * N + N // 2; o = np.argsort(k[j0, :, 0]); te = float(np.interp(0.0, k[j0, o, 0], times[j0, o]))
    e = max(t for t in exc if t < te); rr = [t for t in ref if e < t < te]
    B = bmatrix(seq, e, rr, te); B_all.append(B); bvals.append(float(np.trace(B))); tes.append(te - e)
vol = np.repeat(np.arange(nvol), N)
raw = np.zeros((na, ns), complex)
for lab in [l for l in np.unique(ph['labels']) if l > 0]:
    sub = dict(ph); sub['density'] = np.where(ph['labels'] == lab, ph['density'], 0.0)
    D = float(np.median(ph['D_mm2_per_s'][ph['labels'] == lab]))
    s = R.koma(a.seq, R.expand_columns(sub)).reshape(na, ns)
    raw += s * np.exp(-np.array(bvals)[vol] * D)[:, None]
np.savez(a.out, raw_signal=raw, kxy_cycles_per_m=k[:, :, :2], adc_times_s=times, volume_index=vol, b_values_s_per_mm2=np.array(bvals),
         b_matrices_s_per_mm2=np.array(B_all), fov_m=0.204, matrix=np.array([N, N]), effective_echo_time_s=float(np.median(tes)),
         sequence_sha256=R.sha256(a.seq), phantom_sha256=R.sha256(a.phantom))
print('simulated', raw.shape, 'b', np.round(bvals, 2), 'TE', np.median(tes))

