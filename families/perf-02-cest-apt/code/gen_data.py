"""Generate (sealed round-4 sibling) CEST (APT) datasets with Bloch-McConnell Z-spectra, B0 inhomogeneity and WASSR (heldout-v7-cestapt)."""
import json
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
CLASSES = ['csf', 'gm', 'wm', 'lesion_a', 'lesion_b']


def tissue_pools(cls, field, apt_scale=1.0, mt_scale=1.0):
    hi = field > 5
    w = {'csf': (3.6 if not hi else 4.2, 1.2), 'gm': (1.4 if not hi else 2.0, 0.08 if not hi else 0.05),
         'wm': (0.9 if not hi else 1.3, 0.065 if not hi else 0.045), 'lesion_a': (1.6 if not hi else 2.2, 0.11 if not hi else 0.07),
         'lesion_b': (1.7 if not hi else 2.3, 0.12 if not hi else 0.08)}[cls]
    amide = {'csf': 0.0002, 'gm': 0.0009, 'wm': 0.0009, 'lesion_a': 0.0015, 'lesion_b': 0.0022}[cls] * apt_scale
    noe = {'csf': 0.0002, 'gm': 0.003, 'wm': 0.004, 'lesion_a': 0.0025, 'lesion_b': 0.002}[cls]
    mt = {'csf': 0.0, 'gm': 0.08, 'wm': 0.14, 'lesion_a': 0.05, 'lesion_b': 0.04}[cls] * mt_scale
    pools = [dict(M0=1.0, ppm=0.0, R1=1 / w[0], R2=1 / w[1], k=0),
             dict(M0=amide, ppm=3.5, R1=1.0, R2=1 / 0.003, k=30.0),
             dict(M0=0.001 if cls != 'csf' else 0.0002, ppm=2.0, R1=1.0, R2=1 / 0.01, k=500.0),
             dict(M0=noe, ppm=-3.5, R1=1.0, R2=1 / 0.0006, k=16.0)]
    if mt > 0:
        pools.append(dict(M0=mt, ppm=-2.5, R1=1.0, R2=1 / 1e-5, k=40.0))
    return pools


def zspec(pools, offsets_ppm, b1_uT, ts, f0_mhz):
    n = len(pools)
    w1 = 2 * np.pi * 42.577e6 * b1_uT * 1e-6
    out = np.zeros(len(offsets_ppm))
    m0 = np.zeros(3 * n)
    for i, p in enumerate(pools):
        m0[3 * i + 2] = p['M0']
    for j, off in enumerate(offsets_ppm):
        A = np.zeros((3 * n, 3 * n))
        b = np.zeros(3 * n)
        for i, p in enumerate(pools):
            dw = 2 * np.pi * f0_mhz * (p['ppm'] - off)
            x, y, z = 3 * i, 3 * i + 1, 3 * i + 2
            A[x, x] = -p['R2']; A[x, y] = -dw
            A[y, y] = -p['R2']; A[y, x] = dw; A[y, z] = -w1
            A[z, z] = -p['R1']; A[z, y] = w1
            b[z] = p['R1'] * p['M0']
        for i in range(1, n):
            kba = pools[i]['k']
            kab = kba * pools[i]['M0'] / pools[0]['M0']
            for c in range(3):
                A[3 * i + c, 3 * i + c] -= kba
                A[c, c] -= kab
                A[3 * i + c, c] += kab
                A[c, 3 * i + c] += kba
        mss = -np.linalg.solve(A, b)
        m = expm(A * ts) @ (m0 - mss) + mss
        out[j] = m[2] / pools[0]['M0']
    return out


def phantom(ny, nx, rng):
    yy, xx = np.mgrid[0:ny, 0:nx].astype(float)
    cy, cx = (ny - 1) / 2, (nx - 1) / 2
    r = np.sqrt(((yy - cy) / (0.45 * ny)) ** 2 + ((xx - cx) / (0.38 * nx)) ** 2)
    lab = np.zeros((ny, nx), int)
    lab[r < 1] = 2
    lab[r < 0.62] = 3
    for sx in (-1, 1):
        d = np.sqrt(((yy - cy) / (0.2 * ny)) ** 2 + ((xx - cx - sx * 0.06 * nx) / (0.035 * nx)) ** 2)
        lab[d < 1] = 1
    for (oy, ox, rr, l) in ((-0.2, 0.2, 0.09, 4), (0.22, -0.18, 0.08, 5), (0.18, 0.2, 0.06, 4), (-0.22, -0.2, 0.06, 5)):
        d = np.sqrt((yy - cy - oy * ny) ** 2 + (xx - cx - ox * nx) ** 2) / (rr * nx)
        lab[d < 1] = l
    return lab


def smooth(shape, rng, sigma):
    f = gaussian_filter(rng.standard_normal(shape), sigma)
    f -= f.mean()
    return f / np.abs(f).max()


def make(dirpath, seed, p):
    rng = np.random.default_rng(seed)
    ny, nx = p['shape']
    lab = phantom(ny, nx, rng)
    yy, xx = np.mgrid[0:ny, 0:nx] / ny
    b0 = p['b0_amp_ppm'] * smooth((ny, nx), rng, 9) + p['b0_lin'][0] * (yy - 0.5) + p['b0_lin'][1] * (xx - 0.5)
    b0 = np.where(lab > 0, b0, 0.0)
    f0 = 42.577 * p['field_T']
    fine = np.round(np.arange(-8.0, 8.0001, 0.005), 4)
    zs, zw, truth = {}, {}, {}
    wppm = np.array(p['wassr_offsets_hz']) / f0
    finew = np.round(np.arange(-2.0, 2.0001, 0.002), 4)
    for c, cls in enumerate(CLASSES, start=1):
        pools = tissue_pools(cls, p['field_T'], p.get('apt_scale', 1.0), p.get('mt_scale', 1.0))
        zs[c] = zspec(pools, fine, p['b1_uT'], p['ts_s'], f0)
        zw[c] = zspec(pools, finew, p['wassr_b1_uT'], p['wassr_ts_s'], f0)
        zt = zspec(pools, [-3.5, 3.5], p['b1_uT'], p['ts_s'], f0)
        truth[c] = 100 * (zt[0] - zt[1])
    s0 = np.where(lab > 0, 1000 * (1 + 0.15 * smooth((ny, nx), rng, 6)), 0.0)
    offs = p['offsets_ppm']
    order = np.array(p['order'])
    sig = p['noise'] * 1000
    imgs = [s0 + sig * rng.standard_normal((ny, nx))]
    stored_offsets = [-300.0]
    for k in order:
        o = offs[k]
        img = np.zeros((ny, nx))
        for c in zs:
            m = lab == c
            img[m] = np.interp(o - b0[m], fine, zs[c])
        imgs.append(s0 * img + sig * rng.standard_normal((ny, nx)))
        stored_offsets.append(float(o))
    wimgs = []
    for o in wppm:
        img = np.zeros((ny, nx))
        for c in zw:
            m = lab == c
            img[m] = np.interp(o - b0[m], finew, zw[c])
        wimgs.append(s0 * img + sig * rng.standard_normal((ny, nx)))
    inp = dirpath / 'inputs'
    inp.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(inp / 'cest.npz', images=np.abs(np.array(imgs, np.float32)), offsets_ppm=np.array(stored_offsets))
    np.savez_compressed(inp / 'wassr.npz', images=np.abs(np.array(wimgs, np.float32)), offsets_hz=np.array(p['wassr_offsets_hz'], float))
    (inp / 'params.json').write_text(json.dumps(dict(field_strength_T=p['field_T'], gamma_MHz_per_T=42.577,
        cest_saturation=dict(b1_uT=p['b1_uT'], duration_s=p['ts_s'], shape='continuous wave'),
        wassr_saturation=dict(b1_uT=p['wassr_b1_uT'], duration_s=p['wassr_ts_s'], shape='continuous wave')), indent=1) + '\n')
    tmap = np.zeros((ny, nx))
    for c in truth:
        tmap[lab == c] = truth[c]
    return dict(labels=lab, b0_ppm=b0, mtrasym_percent=tmap, class_truth=np.array([truth[c] for c in range(1, 6)]))


def interleaved(n, rng=None):
    idx = []
    lo, hi = 0, n - 1
    while lo <= hi:
        idx.append(lo)
        if hi != lo:
            idx.append(hi)
        lo += 1; hi -= 1
    return idx


CASES = {}
o_pub = list(np.round(np.arange(-5.2, 5.201, 0.1), 3))
CASES['public'] = (37301, dict(shape=(64, 64), field_T=11.7, b1_uT=1.0, ts_s=3.5, wassr_b1_uT=0.06, wassr_ts_s=1.0,
                              wassr_offsets_hz=list(np.arange(-320, 320.01, 16.0)), offsets_ppm=o_pub,
                              order=list(np.random.default_rng(31).permutation(len(o_pub))), b0_amp_ppm=0.32, b0_lin=(0.28, 0.36), noise=0.002,
                              apt_scale=1.1, mt_scale=1.05))
o1 = list(np.round(np.arange(-6, 6.001, 0.24), 3))
CASES['case1'] = (38401, dict(shape=(64, 64), field_T=3.0, b1_uT=1.6, ts_s=2.2, wassr_b1_uT=0.11, wassr_ts_s=1.0,
                             wassr_offsets_hz=list(np.arange(-140, 140.01, 7.0)), offsets_ppm=o1, order=interleaved(len(o1))[::-1],
                             b0_amp_ppm=0.42, b0_lin=(-0.3, -0.38), noise=0.002, apt_scale=1.0, mt_scale=0.95))
o2 = list(np.round(np.r_[np.arange(-6, -4.39, 0.4), np.arange(-4.3, -2.69, 0.1), np.arange(-2.6, 2.61, 0.2), np.arange(2.7, 4.31, 0.1), np.arange(4.4, 6.01, 0.4)], 3))
CASES['case2'] = (38402, dict(shape=(64, 64), field_T=9.4, b1_uT=0.9, ts_s=2.8, wassr_b1_uT=0.075, wassr_ts_s=1.0,
                             wassr_offsets_hz=list(np.arange(-380, 380.01, 19.0)), offsets_ppm=o2,
                             order=list(np.random.default_rng(32).permutation(len(o2))), b0_amp_ppm=0.36, b0_lin=(0.42, -0.34), noise=0.002,
                             apt_scale=0.9, mt_scale=1.2))

if __name__ == '__main__':
    for name, (seed, p) in CASES.items():
        d = TASK / 'public' if name == 'public' else HERE / 'hidden' / name
        tr = make(d, seed, p)
        tdir = HERE / 'truth' if name == 'public' else d
        tdir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(tdir / ('public_truth.npz' if name == 'public' else 'truth.npz'), **tr)
        print(name, 'class MTRasym %', np.round(tr['class_truth'], 3), 'b0 range ppm', np.round([tr['b0_ppm'].min(), tr['b0_ppm'].max()], 3))

