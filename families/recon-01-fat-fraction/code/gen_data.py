"""Generate (sealed round-4 sibling) raw multi-coil multi-echo GRE k-space for fat-water PDFF mapping (heldout-v7-dixonraw)."""
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
FAT_PPM = [5.29, 4.20, 2.75, 2.10, 1.30, 0.90]
FAT_AMP = [0.048, 0.039, 0.004, 0.128, 0.693, 0.087]


def cfft2(x):
    return np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(x, axes=(-2, -1))), axes=(-2, -1))


def spgr(t1, a, tr):
    e1 = np.exp(-tr / t1)
    return np.sin(a) * (1 - e1) / (1 - np.cos(a) * e1)


def make(d, seed, p):
    rng = np.random.default_rng(seed)
    N = p['n']
    nxo = 2 * N
    yy, xx = np.mgrid[0:N, 0:N].astype(float)
    c = (N - 1) / 2
    body = (((yy - c) / (0.46 * N)) ** 2 + ((xx - c) / (0.44 * N)) ** 2) < 1
    ff = np.where(body, p['ff_body'], 0.0)
    r2 = np.where(body, p['r2_body'], 0.0)
    lab = np.zeros((N, N), int)
    k = 0
    for fy in (-0.25, 0.0, 0.25):
        for fx in (-0.24, 0.0, 0.24):
            m = np.sqrt((yy - c - fy * N) ** 2 + (xx - c - fx * N) ** 2) < 0.085 * N
            lab[m] = k + 1
            ff[m], r2[m] = p['vials'][k]
            k += 1
    rho = np.where(body, 1000.0, 0.0)
    f0 = 42.577 * p['field_T']
    fat_hz = (np.array(FAT_PPM) - 4.70) * f0
    fm = gaussian_filter(rng.standard_normal((N, N)), 12)
    fm = p['fmap_amp'] * fm / np.abs(fm).max() + p['fmap_lin'][0] * (xx - c) / N + p['fmap_lin'][1] * (yy - c) / N
    b1 = p['b1_c'] + p['b1_g'][0] * (xx - c) / N + p['b1_g'][1] * (yy - c) / N
    a = np.deg2rad(p['flip_deg']) * b1
    wt = rho * (1 - ff) * spgr(p['t1_water_ms'], a, p['tr_ms'])
    ft = rho * ff * spgr(p['t1_fat_ms'], a, p['tr_ms'])
    ph0 = np.exp(1j * (0.6 + 1.2 * (xx - c) / N))
    tes = p['te1_ms'] + p['dte_ms'] * np.arange(p['n_echo'])
    imgs = []
    for te in tes * 1e-3:
        fat = np.sum(np.array(FAT_AMP)[:, None, None] * np.exp(2j * np.pi * fat_hz[:, None, None] * te), 0)
        s = (wt + ft * fat) * np.exp(2j * np.pi * fm * te - r2 * te) * ph0
        imgs.append(np.where(body, s, 0))
    imgs = np.array(imgs)
    # coil sensitivities on the oversampled grid [N, 2N]
    nc = p['n_coils']
    Y, X = np.mgrid[0:N, 0:nxo].astype(float)
    sens = []
    for j in range(nc):
        th = 2 * np.pi * j / nc
        cy, cx = c + 0.62 * N * np.sin(th), (nxo - 1) / 2 + 0.62 * N * np.cos(th)
        s = np.exp(-((Y - cy) ** 2 + (X - cx) ** 2) / (2 * (0.5 * N) ** 2)) * np.exp(1j * (p['coil_phase'][j] + 0.02 * (X - cx) - 0.015 * (Y - cy)))
        sens.append(s)
    sens = np.array(sens)
    sens /= np.sqrt((np.abs(sens) ** 2).sum(0)).max()
    full = np.zeros((p['n_echo'], N, nxo), complex)
    full[:, :, N // 2:N // 2 + N] = imgs
    L = np.tril(rng.normal(0, 0.35, (nc, nc)), -1) + np.diag(rng.uniform(0.7, 1.6, nc))
    L = L + 1j * np.tril(rng.normal(0, 0.2, (nc, nc)), -1)
    ksp = np.zeros((p['n_echo'], nc, N, nxo), np.complex64)
    sig = p['noise']
    for e in range(p['n_echo']):
        k = cfft2(sens * full[e][None]) / np.sqrt(N * nxo)
        w = (rng.standard_normal((nc, N * nxo)) + 1j * rng.standard_normal((nc, N * nxo))) / np.sqrt(2)
        k = k + sig * (L @ w).reshape(nc, N, nxo)
        if e % 2 == 1:
            k = k[:, :, ::-1]
        ksp[e] = k
    wn = (rng.standard_normal((nc, 4096)) + 1j * rng.standard_normal((nc, 4096))) / np.sqrt(2)
    noise = (sig * 1.7 * (L @ wn)).astype(np.complex64)
    inp = d / 'inputs'
    inp.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(inp / 'kspace.npz', kspace=ksp)
    np.savez_compressed(inp / 'noise.npz', noise=noise)
    np.savez_compressed(inp / 'b1.npz', b1_rel=np.where(body, b1, 0).astype(np.float32))
    prm = dict(field_strength_T=p['field_T'], gamma_MHz_per_T=42.577, echo_times_ms=list(map(float, np.round(tes, 4))), tr_ms=p['tr_ms'],
               flip_angle_deg=p['flip_deg'], t1_water_ms=p['t1_water_ms'], t1_fat_ms=p['t1_fat_ms'],
               fat_spectrum=dict(ppm=FAT_PPM, relative_amplitude=FAT_AMP), water_ppm=4.70,
               matrix=[N, N], readout_oversampling=2)
    (inp / 'params.json').write_text(json.dumps(prm, indent=1) + '\n')
    return dict(pdff_percent=np.where(body, 100 * ff, 0), r2s_per_s=np.where(body, r2, 0), labels=lab, body=body, fieldmap_hz=fm)


CASES = {
    'public': (37801, dict(n=84, n_echo=6, n_coils=7, field_T=1.5, te1_ms=1.7, dte_ms=2.2, tr_ms=12.5, flip_deg=13.0, t1_water_ms=620.0, t1_fat_ms=295.0,
                          ff_body=0.045, r2_body=27.0, vials=[(0.015, 50), (0.07, 40), (0.13, 85), (0.26, 35), (0.39, 70), (0.53, 45), (0.69, 95), (0.84, 40), (0.96, 60)],
                          fmap_amp=55.0, fmap_lin=(-45.0, 35.0), b1_c=1.18, b1_g=(-0.25, 0.30), coil_phase=[1.4, -2.3, 0.1, 2.7, -0.9, -1.8, 2.2], noise=0.58)),
    'case1': (38901, dict(n=104, n_echo=6, n_coils=11, field_T=2.89, te1_ms=1.05, dte_ms=0.98, tr_ms=8.2, flip_deg=17.0, t1_water_ms=880.0, t1_fat_ms=375.0,
                         ff_body=0.055, r2_body=36.0, vials=[(0.025, 75), (0.095, 40), (0.17, 55), (0.29, 95), (0.43, 40), (0.56, 60), (0.71, 35), (0.87, 80), (0.0, 50)],
                         fmap_amp=115.0, fmap_lin=(65.0, -75.0), b1_c=0.84, b1_g=(0.32, 0.18), coil_phase=[-0.4, 1.9, -2.8, 0.7, 2.4, -1.5, 3.0, -0.1, 1.2, -2.2, 0.5], noise=0.62)),
    'case2': (38902, dict(n=90, n_echo=6, n_coils=6, field_T=3.0, te1_ms=1.22, dte_ms=1.08, tr_ms=7.8, flip_deg=19.0, t1_water_ms=980.0, t1_fat_ms=385.0,
                         ff_body=0.065, r2_body=44.0, vials=[(0.045, 40), (0.14, 65), (0.23, 50), (0.37, 100), (0.48, 45), (0.61, 75), (0.76, 55), (0.93, 45), (0.035, 90)],
                         fmap_amp=125.0, fmap_lin=(-60.0, 80.0), b1_c=1.24, b1_g=(-0.28, -0.22), coil_phase=[2.5, -0.6, 1.3, -2.9, 0.4, -1.7], noise=0.6)),
}

if __name__ == '__main__':
    for name, (seed, p) in CASES.items():
        d = TASK / 'public' if name == 'public' else HERE / 'hidden' / name
        tr = make(d, seed, p)
        tdir = HERE / 'truth' if name == 'public' else d
        tdir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(tdir / ('public_truth.npz' if name == 'public' else 'truth.npz'), **tr)
        print(name, 'fieldmap range', np.round([tr['fieldmap_hz'][tr['body']].min(), tr['fieldmap_hz'][tr['body']].max()], 1))

