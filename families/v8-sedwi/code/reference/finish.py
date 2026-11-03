"""Finish DWI reference deliverables."""
import argparse, json, platform, subprocess, sys, numpy as np
from pathlib import Path
import refkit as R
ap = argparse.ArgumentParser(); ap.add_argument('--phantom', required=True); ap.add_argument('--variant', default='reference')
a = ap.parse_args()
subprocess.run([sys.executable, 'fit_adc.py', '--input', 'simulation.npz', '--output', 'adcmap.npz'], check=True)
ph = np.load(a.phantom); lab = ph['labels']; adc = np.load('adcmap.npz')['adc_mm2_per_s']
def interior(k):
    m = lab == k
    for ax in (0, 1):
        for s in (1, -1):
            m = m & (np.roll(lab, s, ax) == k)
    return m
by = {str(k): float(np.median(adc[interior(k)])) for k in np.unique(lab) if k > 0}
sim = np.load('simulation.npz'); seq = R.read_seq('sequence.seq')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
wd = seq.waveforms_and_times()[0]
fig, ax = plt.subplots(4, 1, figsize=(10, 8))
t0, t1 = 3.2 * 2, 3.2 * 2 + 0.1
for i, nm in enumerate(['Gx', 'Gy', 'Gz']):
    w = wd[i]; m = (w[0] >= t0) & (w[0] <= t1); ax[i].plot(w[0][m] * 1e3, w[1][m] / 42.576e3); ax[i].set_ylabel(nm + ' mT/m')
ax[3].imshow(adc, cmap='gray', vmin=0, vmax=3e-3, aspect='auto'); fig.tight_layout(); fig.savefig('waveforms.png', dpi=80)
rep = {'scope': 'Simulation-only single-shot spin-echo EPI diffusion: Pulseq export, KomaMRI replay per tissue with stated exp(-bD) attenuation, ADC fit',
       'bloch_simulation_performed': True, 'simulator': 'KomaMRI ' + R.koma_version() + ' via juliacall', 'scanner_ready': False,
       'realized_effective_echo_time_ms': float(sim['effective_echo_time_s']) * 1e3,
       'realized_b_values_s_per_mm2': [float(v) for v in sim['b_values_s_per_mm2']],
       'b_value_method': 'trace of the b-matrix from the excitation centre to the k-space-centre echo, numerically integrated from the exported gradient waveforms (all gradients, sign flip at the refocusing centre); diffusion amplitudes iterated until each trace is 1200 s/mm2',
       'steady_state_preparation': 'one non-acquired dummy repetition before the b = 0 volume',
       'adc_by_label': by,
       'software': {'python': platform.python_version(), 'numpy': np.__version__, 'pypulseq': __import__('pypulseq').__version__},
       'validation_summary': 'b-values, TE and spin-echo timing measured on the exported file; ADC per label compared with the object truth',
       'limitations': ['diffusion represented by the stated per-volume attenuation, not by spin motion', 'noise-free, single coil, B0 = 0', 'not scanner validated']}
Path('report.json').write_text(json.dumps(rep, indent=1))
Path('environment.txt').write_text('python ' + sys.version + '\nnumpy ' + np.__version__ + '\npypulseq ' + __import__('pypulseq').__version__ + '\nKomaMRI ' + R.koma_version() + '\n')
Path('README.md').write_text('# SE-EPI DWI reference\nbuild_sequence.py -> sequence.seq; simulate.py -> simulation.npz; fit_adc.py -> adcmap.npz.\n\nADC: ' + json.dumps(by) + '\n')
print(json.dumps(by))

