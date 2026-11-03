#!/usr/bin/env python3
"""Reference solution for heldout-v5-irt1. Builds a complete mock workspace.
Usage: python reference_solution.py [ws_dir] [variant]  (default ws: private/validation/ws_ref, variant 'ref')"""
import json, shutil, subprocess, sys, hashlib, platform
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
PY = sys.executable
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / 'refsol'))

def erode_labels(lab):
    out = lab.copy(); N = lab.shape[0]
    pad = np.pad(lab, 1, mode='edge')
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nb = pad[1 + dy:1 + dy + N, 1 + dx:1 + dx + N]
            out[nb != lab] = 0
    return out

def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(' '.join(map(str, cmd)) + '\n' + r.stderr[-2000:])
    return r.stdout

def make_workspace(ws, variant='ref'):
    ws = Path(ws).resolve(); ws.mkdir(parents=True, exist_ok=True)
    (ws / 'inputs').mkdir(exist_ok=True)
    shutil.copy2(TASK / 'public/inputs/phantom.npz', ws / 'inputs/phantom.npz')
    for f in ['build_sequence.py', 'simulate.py', 'reconstruct.py', 'fit_t1.py']:
        shutil.copy2(HERE / 'refsol' / f, ws / f)
    for f in ['seqtools.py', 'koma_replay.py']:
        shutil.copy2(HERE / f, ws / f)
    # make simulate.py import helpers from the workspace
    s = (ws / 'simulate.py').read_text().replace("sys.path.insert(0, str(Path(__file__).resolve().parents[1]))",
                                                 "sys.path.insert(0, str(Path(__file__).resolve().parent))")
    (ws / 'simulate.py').write_text(s)
    import build_sequence as bs
    kw = {}
    if variant == 'no_half_shift': kw['half_shift'] = False
    if variant == 'b1_violation': kw['inv_dur'] = 1.0e-3
    if variant == 'no_dummy': kw['dummy'] = False
    if variant == 'alt_sequence': kw.update(inv_dur=2.4e-3, exc_dur=1.3e-3, dwell=16e-6)
    info = bs.build(str(ws / 'sequence.seq'), **kw)
    sim_cmd = [PY, 'simulate.py', '--seq', 'sequence.seq', '--phantom', 'inputs/phantom.npz', '--out', 'simulation.npz']
    if variant == 'swap_xy_sim': sim_cmd.append('--swap-xy')
    run(sim_cmd, ws)
    rec = (ws / 'reconstruct.py').read_text()
    if variant == 'recon_swap':
        rec = rec.replace("ap.add_argument('--swap', action='store_true')", "ap.add_argument('--swap', action='store_false')")
    if variant == 'dcf_gridding':
        rec = rec.replace("ap.add_argument('--method', default='cg')", "ap.add_argument('--method', default='dcf')")
    if variant == 'direct_recon':
        rec = rec.replace("ap.add_argument('--method', default='cg')", "ap.add_argument('--method', default='direct')")
        rec = rec.replace("    if method == 'dcf':", """    if method == 'direct':
        idx = np.arange(N) - N // 2
        Y, X = np.meshgrid(idx, idx, indexing='ij')
        E = np.exp(-2j * np.pi * (coord[:, :1] * Y.reshape(1, -1) + coord[:, 1:] * X.reshape(1, -1)) / N)
        lam = 1e-6 * np.trace(E.conj().T @ E).real / E.shape[1]
        x = np.linalg.solve(E.conj().T @ E + lam * np.eye(E.shape[1]), E.conj().T @ y.reshape(-1))
        return x.reshape(N, N)
    if method == 'dcf':""")
    (ws / 'reconstruct.py').write_text(rec)
    fit = (ws / 'fit_t1.py').read_text()
    mode = {'twoparam': 'twoparam', 'naive_mag': 'naive', 'magnitude_fit': 'magnitude'}.get(variant, 'signed')
    fit = fit.replace("ap.add_argument('--mode', default='signed')", f"ap.add_argument('--mode', default='{mode}')")
    (ws / 'fit_t1.py').write_text(fit)
    run([PY, 'reconstruct.py', '--input', 'simulation.npz', '--output', 'images.npz'], ws)
    run([PY, 'fit_t1.py', '--input', 'images.npz', '--output', 't1map.npz'], ws)
    # figures, report
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    import seqtools as st
    seq = st.read(ws / 'sequence.seq'); gw = st.gradient_waveforms(seq); ev = st.events(seq)
    t0 = ev['rf'][1]['t_start'] - 1e-3 if len(ev['rf']) > 1 else 0; t1 = t0 + 0.06
    fig, ax = plt.subplots(3, 1, figsize=(8, 6), sharex=True)
    for r in ev['rf']:
        if t0 <= r['t_center'] <= t1:
            ax[0].bar(r['t_center'] * 1e3, r['peak_uT'], width=(r['t_end'] - r['t_start']) * 1e3)
    for ch, (t, g) in enumerate(gw[:2]):
        m = (t >= t0) & (t <= t1); ax[ch + 1].plot(t[m] * 1e3, g[m] / 42.576e3)
    ax[0].set_ylabel('B1 (uT)'); ax[1].set_ylabel('Gx (mT/m)'); ax[2].set_ylabel('Gy (mT/m)'); ax[2].set_xlabel('time (ms)')
    fig.savefig(ws / 'waveforms.png', dpi=80); plt.close(fig)
    t1m = np.load(ws / 't1map.npz')['t1_s']
    plt.figure(); plt.imshow(t1m, origin='lower', vmin=0, vmax=2); plt.colorbar(label='T1 (s)'); plt.savefig(ws / 't1map.png', dpi=80); plt.close()
    ph = np.load(ws / 'inputs/phantom.npz'); er = erode_labels(ph['labels'])
    sim = np.load(ws / 'simulation.npz')
    hw = st.hardware(seq)
    rep = dict(scope='simulation-only IR radial T1 mapping', bloch_simulation_performed=True, scanner_ready=False,
               realized_inversion_times_ms=[float(v) * 1e3 for v in sim['inversion_times_s']],
               realized_recovery_delay_ms=float(sim['recovery_delay_s']) * 1e3, realized_echo_time_ms=float(sim['echo_time_s']) * 1e3,
               realized_excitation_flip_deg=float(sim['excitation_flip_deg']), realized_inversion_flip_deg=float(sim['inversion_flip_deg']),
               max_gradient_mT_per_m=hw['max_grad_mT_per_m'], max_slew_T_per_m_per_s=hw['max_slew_T_per_m_per_s'], max_b1_uT=hw['max_b1_uT'],
               preparation='one non-acquired 90 deg excitation followed by the recovery delay before the first inversion',
               t1_by_label_ms={str(k): float(np.nanmedian(t1m[er == k]) * 1e3) for k in range(2, int(ph['labels'].max()) + 1)},
               software=dict(python=platform.python_version(), numpy=np.__version__), validation_summary='reference',
               limitations=['simulation only'])
    (ws / 'report.json').write_text(json.dumps(rep, indent=1))
    (ws / 'README.md').write_text('# Reference IR radial T1 mapping\n')
    (ws / 'environment.txt').write_text(run([PY, '-m', 'pip', 'freeze'], ws))
    return rep

if __name__ == '__main__':
    ws = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'validation/ws_ref')
    v = sys.argv[2] if len(sys.argv) > 2 else 'ref'
    print(json.dumps(make_workspace(ws, v)['t1_by_label_ms']))

