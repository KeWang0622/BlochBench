"""Finish MP-RAGE reference deliverables."""
import argparse, json, platform, subprocess, sys, numpy as np
from pathlib import Path
import refkit as R
ap = argparse.ArgumentParser(); ap.add_argument('--phantom', required=True); ap.add_argument('--variant', default='reference')
a = ap.parse_args()
subprocess.run([sys.executable, 'reconstruct.py', '--input', 'simulation.npz', '--output', 'image.npz'], check=True)
ph = np.load(a.phantom); lab = ph['labels']; img = np.abs(np.load('image.npz')['image'])
def interior(k):
    m = lab == k
    for ax in range(3):
        for s in (1, -1):
            m = m & (np.roll(lab, s, ax) == k)
    return m
r1 = np.median(img[interior(1)])
ratios = {str(k): float(np.median(img[interior(k)]) / r1) for k in np.unique(lab) if k > 1}
sim = np.load('simulation.npz'); seq = R.read_seq('sequence.seq'); rfs, adcs = R.rf_table(seq)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
wd = seq.waveforms_and_times()[0]
t0 = adcs[0][0] - 0.6; t1 = adcs[11][-1] + 0.01
fig, ax = plt.subplots(5, 1, figsize=(10, 9))
for i, nm in enumerate(['Gx', 'Gy', 'Gz']):
    w = wd[i]; m = (w[0] >= t0) & (w[0] <= t1); ax[i + 1].plot(w[0][m] * 1e3, w[1][m] / 42.576e3); ax[i + 1].set_ylabel(nm)
for (tc, fl, phs) in rfs:
    if t0 <= tc <= t1: ax[0].bar(tc * 1e3, fl, width=1.0, color='C3')
ax[4].imshow(np.concatenate(list(img[1:5]), axis=1), cmap='gray', aspect='auto'); fig.tight_layout(); fig.savefig('waveforms.png', dpi=80)
rep = {'scope': 'Simulation-only 3D MP-RAGE with a T1 = 0.78 s null: Pulseq export, KomaMRI replay, 3D Cartesian reconstruction',
       'bloch_simulation_performed': True, 'simulator': 'KomaMRI ' + R.koma_version() + ' via juliacall', 'scanner_ready': False,
       'realized_inversion_time_ms': float(sim['inversion_time_s']) * 1e3, 'realized_echo_time_ms': float(sim['echo_time_s']) * 1e3,
       'realized_readout_tr_ms': float(sim['readout_tr_s']) * 1e3, 'realized_cycle_period_ms': float(sim['cycle_period_s']) * 1e3,
       'ti_derivation': 'TI found by bisection on the cycle steady state of the longitudinal magnetization through inversion, recovery, the 12-pulse readout train (6 pulses before ky = 0) and the remainder of the 2.3 s cycle',
       'steady_state_preparation': 'five non-acquired dummy cycles: the cycle-to-cycle recursion of Mz decays by about 0.29 per cycle for T1 = 1.9 s, and the first readouts of the train (small |Mz|) amplify any residual',
       'signal_ratio_by_label': ratios,
       'software': {'python': platform.python_version(), 'numpy': np.__version__, 'pypulseq': __import__('pypulseq').__version__},
       'validation_summary': 'TI, TE, TR, flips and k-space measured on the exported file; nulled vial checked on the reconstructed image',
       'limitations': ['noise-free, single coil, no B1 or B0 errors', 'not scanner validated']}
Path('report.json').write_text(json.dumps(rep, indent=1))
Path('environment.txt').write_text('python ' + sys.version + '\nnumpy ' + np.__version__ + '\npypulseq ' + __import__('pypulseq').__version__ + '\nKomaMRI ' + R.koma_version() + '\n')
Path('README.md').write_text('# MP-RAGE reference\nbuild_sequence.py -> sequence.seq; simulate.py -> simulation.npz; reconstruct.py -> image.npz.\n\nratios: ' + json.dumps(ratios) + '\n')
print(json.dumps(ratios))

