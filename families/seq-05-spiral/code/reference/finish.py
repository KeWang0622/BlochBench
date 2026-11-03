"""Finish spiral reference deliverables."""
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
sim = np.load('simulation.npz'); seq = R.read_seq('sequence.seq')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
wd = seq.waveforms_and_times()[0]
fig, ax = plt.subplots(2, 2, figsize=(10, 8)); ax = ax.ravel()
for i, nm in enumerate(['Gx', 'Gy']):
    w = wd[i]; m = w[0] < 3.0; ax[i].plot(w[0][m] * 1e3, w[1][m] / 42.576e3); ax[i].set_xlim(0, 8); ax[i].set_title(nm + ' mT/m (first interleave)')
k = sim['kxy_cycles_per_m']; ax[2].plot(k[:, :, 0].T, k[:, :, 1].T, lw=0.5); ax[2].set_aspect('equal'); ax[2].set_title('trajectory')
ax[3].imshow(img, cmap='gray'); fig.tight_layout(); fig.savefig('waveforms.png', dpi=80)
na, ns = sim['raw_signal'].shape
rep = {'scope': 'Simulation-only interleaved spiral-out GRE: Pulseq export, KomaMRI replay, iterative non-uniform DFT least-squares reconstruction',
       'bloch_simulation_performed': True, 'simulator': 'KomaMRI ' + R.koma_version() + ' via juliacall', 'scanner_ready': False,
       'n_interleaves': int(na), 'readout_duration_ms': float((sim['adc_times_s'][0, -1] - sim['adc_times_s'][0, 0]) * 1e3), 'realized_echo_time_ms': float(sim['echo_time_s']) * 1e3,
       'trajectory_design': 'Glover analytic Archimedean spiral at 85% of the slew limit with a raster-level slew limiter, slew-limited ramp-down; Nyquist turn spacing for the interleave count',
       'delay_handling': 'sample positions recomputed as k_nominal(t - gradient_delay_s) by interpolation along each interleave before the least-squares reconstruction',
       'signal_ratio_by_label': ratios,
       'software': {'python': platform.python_version(), 'numpy': np.__version__, 'pypulseq': __import__('pypulseq').__version__},
       'validation_summary': 'limits, TE, coverage measured on the exported file; reconstruction tested with imposed delays',
       'limitations': ['noise-free, single coil, B0 = 0', 'single constant gradient-ADC delay model', 'not scanner validated']}
Path('report.json').write_text(json.dumps(rep, indent=1))
Path('environment.txt').write_text('python ' + sys.version + '\nnumpy ' + np.__version__ + '\npypulseq ' + __import__('pypulseq').__version__ + '\nKomaMRI ' + R.koma_version() + '\n')
Path('README.md').write_text('# spiral reference\nbuild_sequence.py -> sequence.seq; simulate.py -> simulation.npz; reconstruct.py -> image.npz.\n\nratios: ' + json.dumps(ratios) + '\n')
print(json.dumps(ratios))

