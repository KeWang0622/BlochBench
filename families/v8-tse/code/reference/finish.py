"""Finish TSE reference deliverables."""
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
ref = np.median(img[interior(1)])
ratios = {str(k): float(np.median(img[interior(k)]) / ref) for k in np.unique(lab) if k > 1}
sim = np.load('simulation.npz')
seq = R.read_seq('sequence.seq'); rfs, adcs = R.rf_table(seq)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
wd = seq.waveforms_and_times()[0]
t0, t1 = 2.0, 2.0 + 0.09
fig, ax = plt.subplots(5, 1, figsize=(10, 8), sharex=True)
for i, nm in enumerate(['Gx', 'Gy', 'Gz']):
    w = wd[i]; m = (w[0] >= t0) & (w[0] <= t1)
    ax[i + 1].plot(w[0][m] * 1e3, w[1][m] / 42.576e3); ax[i + 1].set_ylabel(nm + ' mT/m')
for (tc, fl, phs) in rfs:
    if t0 <= tc <= t1:
        ax[0].bar(tc * 1e3, fl, width=0.4, color='C3')
for t in adcs:
    if t0 <= t[0] <= t1:
        ax[0].axvspan(t[0] * 1e3, t[-1] * 1e3, color='C2', alpha=0.4)
ax[0].set_ylabel('RF flip / ADC'); ax[4].imshow(img, cmap='gray', aspect='auto'); fig.tight_layout(); fig.savefig('waveforms.png', dpi=80)
exc = [r[1] for r in rfs if r[1] < 120]; refo = [r[1] for r in rfs if r[1] >= 120]
rep = {'scope': 'Simulation-only 2D multi-shot TSE: Pulseq export, KomaMRI Bloch replay, Cartesian reconstruction',
       'bloch_simulation_performed': True, 'simulator': 'KomaMRI ' + R.koma_version() + ' via juliacall', 'scanner_ready': False,
       'realized_effective_echo_time_ms': float(sim['effective_echo_time_s']) * 1e3, 'realized_echo_spacing_ms': float(sim['echo_spacing_s']) * 1e3,
       'realized_flip_angles_deg': {'excitation': float(np.median(exc)), 'refocusing': float(np.median(refo))},
       'echo_ordering': 'linear segmented: line j acquired on echo floor(j/2)+1 of shot (j mod 2)+1; ky = 0 on echo 5',
       'echo_train_design': 'CPMG: refocusing phase 90 deg from the excitation phase, first refocusing at ESP/2, echo at the centre of a symmetric readout, phase encoding rewound after every echo, symmetric z crushers, slice rephasing lobe',
       'steady_state_preparation': 'one non-acquired dummy shot with identical timing before the acquired shots',
       'signal_ratio_by_label': ratios,
       'software': {'python': platform.python_version(), 'numpy': np.__version__, 'pypulseq': __import__('pypulseq').__version__},
       'validation_summary': 'timing and k-space measured on the exported file; echo phases and shot-to-shot first-echo magnitudes inspected on a test column replay',
       'limitations': ['noise-free single-coil simulation', 'no B0 or B1 imperfections', 'not scanner validated']}
Path('report.json').write_text(json.dumps(rep, indent=1))
Path('environment.txt').write_text('python ' + sys.version + '\nnumpy ' + np.__version__ + '\npypulseq ' + __import__('pypulseq').__version__ + '\nKomaMRI ' + R.koma_version() + '\n')
Path('README.md').write_text('# TSE reference\nbuild_sequence.py -> sequence.seq; simulate.py (KomaMRI) -> simulation.npz; reconstruct.py -> image.npz.\n\nratios: ' + json.dumps(ratios) + '\n')
print(json.dumps(ratios))

