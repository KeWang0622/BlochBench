"""Generate (sealed round-4 sibling) event-related BOLD datasets for heldout-v7-fmriglm."""
import json
from pathlib import Path
import numpy as np
from scipy.stats import gamma
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
TASK = HERE.parent


def event_response(dt=0.01):
    t = np.arange(0, 32, dt)
    h = gamma.pdf(t, 6) - gamma.pdf(t, 16) / 6.0
    box = np.ones(int(round(1.0 / dt)))
    g = np.convolve(h, box)[:len(t)] * dt
    return t, g / g.max()


def response(times, onsets):
    t, g = event_response()
    r = np.zeros_like(times, dtype=float)
    for o in onsets:
        r += np.interp(times - o, t, g, left=0.0, right=0.0)
    return r


def make(d, seed, p):
    rng = np.random.default_rng(seed)
    nz, ny, nx = p['shape']
    TR, nd, nv = p['tr_s'], p['n_dummy'], p['n_vol']
    yy, xx = np.mgrid[0:ny, 0:nx].astype(float)
    brain2d = (((yy - (ny - 1) / 2) / (0.46 * ny)) ** 2 + ((xx - (nx - 1) / 2) / (0.42 * nx)) ** 2) < 1
    brain = np.repeat(brain2d[None], nz, 0)
    amp = np.zeros((nz, ny, nx))
    for z in range(nz):
        for _ in range(2):
            cy, cx = rng.uniform(0.3, 0.7) * ny, rng.uniform(0.3, 0.7) * nx
            blob = ((yy - cy) ** 2 + (xx - cx) ** 2) < (0.13 * ny) ** 2
            amp[z][blob & brain2d] = rng.uniform(*p['amp_range'])
    # onsets relative to the start of stored volume 0 (a dummy volume)
    onsets = []
    t = nd * TR + rng.uniform(4, 8)
    end = (nv - 1) * TR - 20
    while t < end:
        onsets.append(round(t, 2))
        t += rng.uniform(*p['isi_range'])
    st = np.array(p['slice_times_s'])
    times = np.arange(nv)[:, None] * TR + st[None, :]  # [vol, slice]
    r = response(times.ravel(), np.array(onsets)).reshape(nv, nz)
    # motion parameters: slow random walk plus stimulus-locked transients
    mp = np.cumsum(rng.normal(0, 1, (nv, 6)), 0)
    mp = gaussian_filter(mp, (3, 0))
    mp = (mp - mp.mean(0)) / mp.std(0)
    lock = response(np.arange(nv) * TR, np.array(onsets) - 2.0)
    mp[:, 0] += p['motion_lock'] * (lock - lock.mean()) / lock.std()
    mp[:, 4] += 0.6 * p['motion_lock'] * (lock - lock.mean()) / lock.std()
    scale = np.array([0.15, 0.2, 0.25, 0.002, 0.0015, 0.002])
    motion = mp * scale
    base = 1000 * (1 + 0.2 * gaussian_filter(rng.standard_normal((nz, ny, nx)), 2) / 0.1)
    base = np.clip(base, 500, 1600) * brain
    coef = rng.standard_normal((6, nz, ny, nx)) * brain
    mot_sig = np.einsum('tj,jzyx->tzyx', mp, coef) / np.sqrt(6) * p['motion_signal_pct'] / 100
    tt = np.arange(nv) * TR / ((nv - 1) * TR)
    dr = rng.uniform(-1, 1, (3, nz, ny, nx))
    drift = (p['drift_pct'] / 100) * (dr[0] * (tt - 0.5)[:, None, None, None] * 2 + dr[1] * np.cos(2 * np.pi * tt * 1.3)[:, None, None, None]
                                      + dr[2] * ((2 * tt - 1) ** 2 - 1 / 3)[:, None, None, None])
    rho, sig = p['ar1'], p['noise_pct'] / 100
    e = np.zeros((nv, nz, ny, nx))
    w = rng.standard_normal((nv, nz, ny, nx)) * sig * np.sqrt(1 - rho ** 2)
    e[0] = rng.standard_normal((nz, ny, nx)) * sig
    for k in range(1, nv):
        e[k] = rho * e[k - 1] + w[k]
    trans = np.ones(nv)
    trans[:nd] = p['dummy_factors']
    S = base[None] * trans[:, None, None, None] * (1 + drift + mot_sig + (amp[None] / 100) * r[:, :, None, None] + e)
    S = np.where(brain[None], S, rng.normal(0, 2, S.shape))
    inp = d / 'inputs'
    inp.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(inp / 'bold.npz', data=S.astype(np.float32))
    np.savetxt(inp / 'motion.txt', motion, fmt='%.6f', header='trans_x_mm trans_y_mm trans_z_mm rot_x_rad rot_y_rad rot_z_rad (one row per stored volume)')
    (inp / 'events.json').write_text(json.dumps({'onsets_s': onsets, 'duration_s': 1.0}, indent=1) + '\n')
    (inp / 'acq.json').write_text(json.dumps({'tr_s': TR, 'n_dummy_volumes': nd, 'slice_times_s': list(map(float, st))}, indent=1) + '\n')
    return dict(amp_pct=amp, brain=brain, slice_times_s=st)


def interleaved(nz, TR, descending=False):
    order = list(range(0, nz, 2)) + list(range(1, nz, 2))
    if descending:
        order = order[::-1]
    st = np.zeros(nz)
    for i, z in enumerate(order):
        st[z] = i * TR / nz
    return list(st)


def odd_first(nz, TR):
    order = list(range(1, nz, 2)) + list(range(0, nz, 2))
    st = np.zeros(nz)
    for i, z in enumerate(order):
        st[z] = i * TR / nz
    return list(st)


def descending(nz, TR):
    return [float((nz - 1 - z) * TR / nz) for z in range(nz)]


CASES = {
    'public': (37501, dict(shape=(13, 24, 24), tr_s=2.3, n_dummy=3, n_vol=220, slice_times_s=interleaved(13, 2.3, True), amp_range=(0.9, 2.0),
                          isi_range=(4.5, 9.0), motion_lock=1.05, motion_signal_pct=0.85, drift_pct=1.9, ar1=0.58, noise_pct=0.5,
                          dummy_factors=[2.45, 1.5, 1.15])),
    'case1': (38601, dict(shape=(16, 24, 24), tr_s=1.9, n_dummy=5, n_vol=262, slice_times_s=odd_first(16, 1.9), amp_range=(0.75, 1.9),
                         isi_range=(3.5, 8.5), motion_lock=0.95, motion_signal_pct=0.9, drift_pct=2.1, ar1=0.62, noise_pct=0.5,
                         dummy_factors=[2.65, 1.6, 1.22, 1.07, 1.02])),
    'case2': (38602, dict(shape=(11, 24, 24), tr_s=2.7, n_dummy=4, n_vol=188, slice_times_s=descending(11, 2.7), amp_range=(0.95, 2.15),
                         isi_range=(5.0, 10.5), motion_lock=1.15, motion_signal_pct=0.8, drift_pct=1.7, ar1=0.52, noise_pct=0.5,
                         dummy_factors=[2.85, 1.75, 1.28, 1.09])),
}

if __name__ == '__main__':
    for name, (seed, p) in CASES.items():
        d = TASK / 'public' if name == 'public' else HERE / 'hidden' / name
        tr = make(d, seed, p)
        tdir = HERE / 'truth' if name == 'public' else d
        tdir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(tdir / ('public_truth.npz' if name == 'public' else 'truth.npz'), **tr)
        print(name, 'active voxels', int((tr['amp_pct'] > 0).sum()), 'brain', int(tr['brain'].sum()))

