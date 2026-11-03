#!/usr/bin/env python3
"""Reference solution for heldout-v5-spiralb0; builds a complete mock workspace.
Usage: python reference_solution.py [ws_dir] [variant]"""
import json, platform, shutil, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; TASK = HERE.parent; PY = sys.executable
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'refsol'))

def erode_labels(lab):
    out = lab.copy(); n = lab.shape[0]; pad = np.pad(lab, 1, mode='edge')
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out[pad[1 + dy:1 + dy + n, 1 + dx:1 + dx + n] != lab] = 0
    return out

def run(cmd, cwd):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(' '.join(map(str, cmd)) + '\n' + r.stderr[-2000:])
    return r.stdout

RECON_VARIANTS = {'no_correction': 'none', 'field_sign': 'sign', 'time_from_adc_start': 'te0', 'field_transposed': 'transpose',
                  'delta_te_ms': 'tems', 'kxy_swapped': 'swapk', 'time_segmented': 'tseg'}

def make_workspace(ws, variant='ref'):
    ws = Path(ws).resolve(); ws.mkdir(parents=True, exist_ok=True); (ws / 'inputs').mkdir(exist_ok=True)
    for f in ('phantom.npz', 'fieldmap_scan.npz'):
        shutil.copy2(TASK / 'public/inputs' / f, ws / 'inputs' / f)
    for f in ('build_sequence.py', 'simulate.py', 'reconstruct.py'):
        shutil.copy2(HERE / 'refsol' / f, ws / f)
    for f in ('seqtools.py', 'koma_replay.py'):
        shutil.copy2(HERE / f, ws / f)
    s = (ws / 'simulate.py').read_text().replace("sys.path.insert(0, str(Path(__file__).resolve().parents[1]))",
                                                 "sys.path.insert(0, str(Path(__file__).resolve().parent))")
    (ws / 'simulate.py').write_text(s)
    rv = RECON_VARIANTS.get(variant, 'ref')
    (ws / 'reconstruct.py').write_text((ws / 'reconstruct.py').read_text().replace("VARIANT = 'ref'", f"VARIANT = '{rv}'"))
    import build_sequence as bs
    kw = {}
    if variant == 'slew_violation': kw.update(smax_design=195.0, smax_frac=0.95)
    if variant == 'undersampled_spiral': kw.update(turn_spacing=1.7)
    if variant == 'alt_sequence': kw.update(dwell=2e-6, gmax_frac=0.85, smax_frac=0.8, exc_dur=0.5e-3)
    info = bs.build(str(ws / 'sequence.seq'), **kw)
    cmd = [PY, 'simulate.py', '--seq', 'sequence.seq', '--phantom', 'inputs/phantom.npz', '--out', 'simulation.npz']
    if variant == 'hz_as_rad': cmd.append('--hz-as-rad')
    run(cmd, ws)
    run([PY, 'reconstruct.py', '--input', 'simulation.npz', '--fieldmap', 'inputs/fieldmap_scan.npz', '--output', 'image.npz'], ws)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    import seqtools as st
    seq = st.read(ws / 'sequence.seq'); gw = st.gradient_waveforms(seq)
    fig, ax = plt.subplots(2, 1, figsize=(8, 4), sharex=True)
    for ch in range(2):
        t, g = gw[ch]; ax[ch].plot(t * 1e3, g / 42.576e3); ax[ch].set_ylabel('G%s (mT/m)' % 'xy'[ch])
    fig.savefig(ws / 'waveforms.png', dpi=80); plt.close(fig)
    im = np.load(ws / 'image.npz')
    fig, ax = plt.subplots(1, 2, figsize=(8, 4)); ax[0].imshow(np.abs(im['image']), origin='lower'); ax[1].imshow(im['field_map_hz'], origin='lower')
    fig.savefig(ws / 'comparison.png', dpi=80); plt.close(fig)
    ph = np.load(ws / 'inputs/phantom.npz'); er = erode_labels(ph['labels'])
    img = im['image']; ref = np.abs(img[er == 1]).mean()
    sim = np.load(ws / 'simulation.npz'); hw = st.hardware(seq)
    rep = dict(scope='simulation-only single-shot spiral with field-map-based off-resonance correction', bloch_simulation_performed=True,
               scanner_ready=False, realized_echo_time_ms=float(sim['echo_time_s']) * 1e3, readout_duration_ms=info['readout_ms'],
               max_gradient_mT_per_m=hw['max_grad_mT_per_m'], max_slew_T_per_m_per_s=hw['max_slew_T_per_m_per_s'], max_b1_uT=hw['max_b1_uT'],
               off_resonance_model='exp(-2*pi*i*df*t), t from the excitation RF centre',
               signal_ratio_by_label={str(k): float(np.abs(img[er == k]).mean() / ref) for k in range(2, int(ph['labels'].max()) + 1)},
               software=dict(python=platform.python_version(), numpy=np.__version__), validation_summary='reference', limitations=['simulation only'])
    (ws / 'report.json').write_text(json.dumps(rep, indent=1))
    (ws / 'README.md').write_text('# reference\n')
    (ws / 'environment.txt').write_text(run([PY, '-m', 'pip', 'freeze'], ws))
    return rep

if __name__ == '__main__':
    ws = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'validation/ws_ref')
    v = sys.argv[2] if len(sys.argv) > 2 else 'ref'
    print(json.dumps(make_workspace(ws, v)['signal_ratio_by_label']))

