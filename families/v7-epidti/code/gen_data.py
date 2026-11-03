"""Generate (sealed round-4 sibling) raw single-shot EPI diffusion k-space with Nyquist ghost errors, B0 distortion and gradient nonlinearity (heldout-v7-epidti)."""
import json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
N = 64


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def tensor(e1, l1, l2):
    e1 = unit(e1)
    a = np.array([1.0, 0, 0]) if abs(e1[0]) < 0.9 else np.array([0, 1.0, 0])
    e2 = unit(np.cross(e1, a)); e3 = np.cross(e1, e2)
    return l1 * np.outer(e1, e1) + l2 * np.outer(e2, e2) + l2 * np.outer(e3, e3)


def phantom(nz, rng, p):
    yy, xx = np.mgrid[0:N, 0:N].astype(float)
    sy, sx = p.get('shift', (0.0, 0.0))
    yy, xx = yy - sy, xx - sx
    c = (N - 1) / 2
    D = np.zeros((nz, N, N, 3, 3)); S0 = np.zeros((nz, N, N)); lab = np.zeros((nz, N, N), int)
    for z in range(nz):
        brain = (((yy - c) / 23.5) ** 2 + ((xx - c) / 25.5) ** 2) < 1
        D[z][brain] = np.eye(3) * 0.8e-3; S0[z][brain] = 900; lab[z][brain] = 1
        for (cy, cx) in ((c + 9, c - 7), (c + 9, c + 7)):
            v = (((yy - cy) / 5.0) ** 2 + ((xx - cx) / 3.0) ** 2) < 1
            D[z][v] = np.eye(3) * 3.0e-3; S0[z][v] = 1500; lab[z][v] = 2
        band = (np.abs(yy - (c - 9 + 2 * z)) <= 3.5) & brain & (np.abs(xx - c) < 20)
        D[z][band] = tensor(p['dir_a'], 1.7e-3, 0.3e-3); S0[z][band] = 700; lab[z][band] = 3
        vb = (np.abs(xx - (c + 13)) <= 3.5) & brain & (yy > c - 4) & (yy < c + 19)
        D[z][vb] = tensor(p['dir_b'], 1.6e-3, 0.35e-3); S0[z][vb] = 700; lab[z][vb] = 4
        dc = ((yy - (c + 12)) ** 2 + (xx - (c - 12)) ** 2) < 6.0 ** 2
        D[z][dc] = tensor(p['dir_c'], 1.5e-3, 0.4e-3); S0[z][dc] = 750; lab[z][dc] = 5
        dd = ((yy - (c - 14)) ** 2 + (xx - (c + 10)) ** 2) < 5.5 ** 2
        D[z][dd] = tensor(p['dir_d'], 1.8e-3, 0.3e-3); S0[z][dd] = 700; lab[z][dd] = 6
    return D * p.get('dscale', 1.0), S0, lab


def make(d, seed, p):
    rng = np.random.default_rng(seed)
    nz = p['nz']
    D, S0, lab = phantom(nz, rng, p)
    yy, xx = np.mgrid[0:N, 0:N].astype(float)
    c = (N - 1) / 2
    fmap = np.zeros((nz, N, N))
    for z in range(nz):
        f = gaussian_filter(rng.standard_normal((N, N)), 9)
        fmap[z] = p['fmap_amp'] * f / np.abs(f).max() + p['fmap_lin'][0] * (yy - c) / N + p['fmap_lin'][1] * (xx - c) / N + p['fmap_off'] * (z - (nz - 1) / 2)
    # gradient nonlinearity: actual gradient = (I + L(r)) nominal gradient
    L = np.zeros((nz, N, N, 3, 3))
    for z in range(nz):
        zc = z - (nz - 1) / 2
        L[z, :, :, 0, 0] = p['gnl'][0] + p['gnl_g'] * (xx - c) / N
        L[z, :, :, 1, 1] = p['gnl'][1] - p['gnl_g'] * (yy - c) / N
        L[z, :, :, 2, 2] = p['gnl'][2] + 0.03 * zc
        L[z, :, :, 0, 1] = L[z, :, :, 1, 0] = 0.02 * (xx - c) / N
        L[z, :, :, 0, 2] = 0.015 * (yy - c) / N
        L[z, :, :, 2, 1] = -0.02 * (xx - c) / N
    nd = p['n_dirs']
    g = rng.standard_normal((nd, 3)); g /= np.linalg.norm(g, axis=1, keepdims=True)
    g[:, 2] = np.abs(g[:, 2])
    bvals = np.r_[np.zeros(p['n_b0']), np.full(nd, p['b'])]
    bvecs = np.vstack([np.zeros((p['n_b0'], 3)), g])
    nv = len(bvals)
    imgs = np.zeros((nv, nz, N, N), complex)
    for v in range(nv):
        ge = np.einsum('zyxij,j->zyxi', L, bvecs[v]) + bvecs[v]
        att = np.exp(-bvals[v] * np.einsum('zyxi,zyxij,zyxj->zyx', ge, D, ge))
        th = 1.5 * rng.standard_normal() + 0.8 * rng.standard_normal() * (xx - c) / N + 0.8 * rng.standard_normal() * (yy - c) / N
        imgs[v] = S0 * att * np.exp(1j * th)[None]
    esp, te = p['esp_ms'] * 1e-3, p['te_ms'] * 1e-3
    dwell = esp / N
    pe = p['pe_sign']
    ky_line = (np.arange(N) - N // 2) if pe > 0 else (N // 2 - 1 - np.arange(N))
    l0 = int(np.where(ky_line == 0)[0][0])
    tref = te - l0 * esp
    nnav = 3
    pol = np.array([1 if r % 2 == 0 else -1 for r in range(nnav + N)])
    rows_kx, rows_ky, rows_t, rows_neg = [], [], [], []
    for r in range(nnav + N):
        tc = tref + (r - nnav) * esp
        ky = 0 if r < nnav else ky_line[r - nnav]
        j = np.arange(N)
        kx = (j - N // 2).astype(float) if pol[r] > 0 else (N // 2 - 1 - j) + p['delta_samples']
        rows_kx.append(kx); rows_ky.append(np.full(N, ky, float)); rows_t.append(tc + (j - N // 2) * dwell); rows_neg.append(np.full(N, pol[r] < 0))
    kx, ky, ts, neg = map(np.concatenate, (rows_kx, rows_ky, rows_t, rows_neg))
    xv = (xx - N // 2).ravel(); yv = (yy - N // 2).ravel()
    raw = np.zeros((nv, nz, nnav + N, N), np.complex64)
    sig = p['noise']
    for z in range(nz):
        E = np.exp(-2j * np.pi * (np.outer(kx, xv) + np.outer(ky, yv)) / N + 2j * np.pi * np.outer(ts, fmap[z].ravel()))
        E[neg] *= np.exp(1j * p['phi0'])
        E = E.astype(np.complex64)
        data = (E @ imgs[:, z].reshape(nv, -1).T.astype(np.complex64)).T / N
        data += sig * (rng.standard_normal(data.shape) + 1j * rng.standard_normal(data.shape)) / np.sqrt(2)
        raw[:, z] = data.reshape(nv, nnav + N, N)
    inp = d / 'inputs'
    inp.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(inp / 'epi_raw.npz', raw=raw, readout_polarity=pol, ky_index_of_imaging_line=ky_line)
    np.savez_compressed(inp / 'fieldmap.npz', fieldmap_hz=fmap.astype(np.float32))
    np.savez_compressed(inp / 'grad_nonlin.npz', L=L.astype(np.float32))
    np.savetxt(inp / 'bvals.txt', bvals[None], fmt='%g')
    np.savetxt(inp / 'bvecs.txt', bvecs.T, fmt='%.6f')
    (inp / 'params.json').write_text(json.dumps(dict(matrix=[N, N], n_slices=nz, n_navigators=nnav, echo_spacing_ms=p['esp_ms'],
        dwell_time_ms=p['esp_ms'] / N, te_ms=p['te_ms'], pe_direction_sign=pe, bvalue_units='s/mm^2'), indent=1) + '\n')
    ev, evec = np.linalg.eigh(D.reshape(-1, 3, 3))
    md = ev.mean(1)
    fa = np.sqrt(1.5 * ((ev - md[:, None]) ** 2).sum(1) / np.maximum((ev ** 2).sum(1), 1e-30))
    v1 = evec[:, :, 2]
    return dict(fa=fa.reshape(nz, N, N), md=md.reshape(nz, N, N), v1=v1.reshape(nz, N, N, 3), labels=lab, s0=S0, fieldmap=fmap)


CASES = {
    'public': (37901, dict(nz=3, n_b0=4, n_dirs=36, b=950.0, esp_ms=0.66, te_ms=64.0, pe_sign=-1, delta_samples=0.27, phi0=1.2, fmap_amp=58.0, fmap_lin=(-50.0, -60.0), fmap_off=-6.0,
                          gnl=(0.05, 0.08, 0.06), gnl_g=0.11, dir_a=(1, -0.1, 0.3), dir_b=(0.25, 1, 0.15), dir_c=(-1, -0.9, 0.2), dir_d=(0.2, 0.3, 1), noise=1.15,
                          shift=(1.2, -1.5), dscale=1.03)),
    'case1': (39001, dict(nz=2, n_b0=3, n_dirs=32, b=1050.0, esp_ms=0.54, te_ms=66.0, pe_sign=-1, delta_samples=-0.32, phi0=-1.3, fmap_amp=62.0, fmap_lin=(70.0, 45.0), fmap_off=12.0,
                         gnl=(0.07, 0.05, 0.07), gnl_g=-0.10, dir_a=(1, 0.15, -0.25), dir_b=(-0.3, 1, 0.05), dir_c=(1, -0.85, -0.25), dir_d=(-0.15, 0.25, 1), noise=1.15,
                         shift=(-1.2, 0.8), dscale=0.95)),
    'case2': (39002, dict(nz=3, n_b0=2, n_dirs=27, b=800.0, esp_ms=0.60, te_ms=57.0, pe_sign=1, delta_samples=0.24, phi0=0.3, fmap_amp=48.0, fmap_lin=(-70.0, 55.0), fmap_off=-11.0,
                         gnl=(0.06, 0.07, 0.05), gnl_g=0.09, dir_a=(1, -0.2, 0.15), dir_b=(0.15, 1, -0.3), dir_c=(-1, 1.05, 0.15), dir_d=(0.25, -0.15, 1), noise=1.1,
                         shift=(0.8, -0.6), dscale=1.06)),
}

if __name__ == '__main__':
    for name, (seed, p) in CASES.items():
        d = TASK / 'public' if name == 'public' else HERE / 'hidden' / name
        tr = make(d, seed, p)
        tdir = HERE / 'truth' if name == 'public' else d
        tdir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(tdir / ('public_truth.npz' if name == 'public' else 'truth.npz'), **tr)
        print(name, 'fmap range', np.round([tr['fieldmap'].min(), tr['fieldmap'].max()], 1))

