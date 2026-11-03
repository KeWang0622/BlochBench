"""Finish EPI reference deliverables."""
import argparse, json, platform, subprocess, sys, numpy as np
from pathlib import Path
import refkit as R
ap = argparse.ArgumentParser(); ap.add_argument('--phantom', required=True); ap.add_argument('--variant', default='reference')
a = ap.parse_args()
subprocess.run([sys.executable, 'reconstruct.py', '--input', 'simulation.npz', '--output', 'image.npz'], check=True)
ph = np.load(a.phantom); lab = ph['labels']; img = np.abs(np.load('image.npz')['image'])
def interior(k):
    m = lab == k
    for ax in (0, 1):
        for s in (1, -1):
            m = m & (np.roll(lab, s, ax) == k)
    return m
r1 = np.median(img[interior(1)])
ratios = {str(k): float(np.median(img[interior(k)]) / r1) for k in np.unique(lab) if k > 1}
sim = np.load('simulation.npz')
seq = R.read_seq('sequence.seq'); rfs, adcs = R.rf_table(seq)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
wd = seq.waveforms_and_times()[0]
fig, ax = plt.subplots(5, 1, figsize=(10, 9))
for i, nm in enumerate(['Gx', 'Gy', 'Gz']):
    w = wd[i]; ax[i].plot(w[0] * 1e3, w[1] / 42.576e3); ax[i].set_ylabel(nm + ' mT/m')
for t in adcs:
    ax[0].axvspan(t[0] * 1e3, t[-1] * 1e3, color='C2', alpha=0.2)
k = sim['kxy_cycles_per_m']; ax[3].plot(k[:, :, 0].T, k[:, :, 1].T, '.', ms=1); ax[3].set_ylabel('ky vs kx')
ax[4].imshow(img, cmap='gray', aspect='auto'); fig.tight_layout(); fig.savefig('waveforms.png', dpi=80)
rep = {'scope': 'Simulation-only single-shot ramp-sampled GE-EPI with navigator-based odd/even correction: Pulseq export, KomaMRI replay, NUDFT reconstruction',
       'bloch_simulation_performed': True, 'simulator': 'KomaMRI ' + R.koma_version() + ' via juliacall', 'scanner_ready': False,
       'realized_effective_echo_time_ms': float(sim['effective_echo_time_s']) * 1e3, 'realized_echo_spacing_ms': float(sim['echo_spacing_s']) * 1e3,
       'readout_design': 'triangular-trapezoidal readout lobes at the slew limit, ADC over the ramps, y blips in the lobe tails outside the ADC windows',
       'ghost_correction': 'three non-phase-encoded navigator echoes (+,-,+); the gradient-ADC delay is estimated by matching navigator projections with the trajectory model k(t - delay) and the imaging lines are reconstructed with the corrected trajectory',
       'signal_ratio_by_label': ratios,
       'software': {'python': platform.python_version(), 'numpy': np.__version__, 'pypulseq': __import__('pypulseq').__version__},
       'validation_summary': 'TE, echo spacing, k-space coverage measured on the exported file; reconstruction tested on replays with imposed delays',
       'limitations': ['noise-free, single coil, B0 = 0', 'delay modeled as a single constant gradient-ADC shift', 'not scanner validated']}
Path('report.json').write_text(json.dumps(rep, indent=1))
Path('environment.txt').write_text('python ' + sys.version + '\nnumpy ' + np.__version__ + '\npypulseq ' + __import__('pypulseq').__version__ + '\nKomaMRI ' + R.koma_version() + '\n')
Path('README.md').write_text('# EPI reference\nbuild_sequence.py -> sequence.seq; simulate.py (KomaMRI) -> simulation.npz; reconstruct.py -> image.npz.\n\nratios: ' + json.dumps(ratios) + '\n')
print(json.dumps(ratios))

