"""Generate (sealed round-4 sibling) public and hidden pCASL datasets for heldout-v7-pcasl (fixed seeds)."""
import json, shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
TASK = HERE.parent


def phantom(nz, ny, nx, rng):
    lab = np.zeros((nz, ny, nx), np.int16)
    yy, xx = np.mgrid[0:ny, 0:nx].astype(float)
    for z in range(nz):
        s = 1 - 0.22 * abs(z - (nz - 1) / 2) / ((nz - 1) / 2)
        ry, rx = 0.44 * ny * s, 0.37 * nx * s
        cy, cx = (ny - 1) / 2 + rng.normal(0, 0.4), (nx - 1) / 2 + rng.normal(0, 0.4)
        r = np.sqrt(((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2)
        th = np.arctan2(yy - cy, xx - cx)
        wob = 1 + 0.07 * np.sin(6 * th + 0.7 * z)
        lab[z][r < 1] = 1
        lab[z][r < 0.70 * wob] = 2
        for sx in (-1, 1):
            d = np.sqrt(((yy - cy - 0.08 * ry) / (0.17 * ry)) ** 2 + ((xx - cx - sx * 0.33 * rx) / (0.11 * rx)) ** 2)
            lab[z][d < 1] = 1
            d = np.sqrt(((yy - cy + 0.12 * ry) / (0.26 * ry)) ** 2 + ((xx - cx - sx * 0.11 * rx) / (0.06 * rx)) ** 2)
            lab[z][d < 1] = 3
    return lab


def smooth_field(shape, rng, sigma, amp):
    f = gaussian_filter(rng.standard_normal(shape), sigma)
    f /= np.abs(f).max() + 1e-12
    return 1 + amp * f


def make(case_dir, seed, p, public):
    rng = np.random.default_rng(seed)
    nz, ny, nx = p['shape']
    lab = phantom(nz, ny, nx, rng)
    gm, wm, csf = lab == 1, lab == 2, lab == 3
    cbf = np.zeros(lab.shape)
    mod = smooth_field(lab.shape, rng, (1.5, 5, 5), 0.15)
    cbf[gm] = p['cbf_gm'] * mod[gm]
    cbf[wm] = p['cbf_wm'] * mod[wm]
    m0t = np.zeros(lab.shape)
    m0mod = smooth_field(lab.shape, rng, (2, 8, 8), 0.04)
    m0t[gm], m0t[wm], m0t[csf] = p.get('m0_tissue', (860.0, 720.0, 1000.0))
    m0t *= m0mod
    t1 = np.full(lab.shape, 0.5)
    t1mod = smooth_field(lab.shape, rng, (2, 6, 6), 0.04)
    t1[gm], t1[wm], t1[csf] = p.get('t1_tissue', (1.35, 0.85, 4.2))
    t1 = np.where(lab > 0, t1 * t1mod, 0.0)
    a = p['acq']
    pld = np.zeros(nz)
    for i, z in enumerate(a['slice_order']):
        pld[z] = a['pld_s'] + i * a['slice_interval_s']
    alpha = a['labeling_efficiency'] * a['bs_inversion_efficiency'] ** a['n_bs_pulses']
    T1b, lam, tau = a['t1_blood_s'], a['partition_coefficient_mL_per_g'], a['label_duration_s']
    dm = cbf * 2 * alpha * T1b * m0t * (1 - np.exp(-tau / T1b)) * np.exp(-pld[:, None, None] / T1b) / (6000 * lam)
    static = 0.08 * m0t * (1 + 0.4 * np.arange(nz)[:, None, None] / nz)
    npairs = p['npairs']
    sig = p['noise_sd']
    vols = []
    drift = 1 + 0.0004 * rng.standard_normal(2 * npairs)
    for k in range(2 * npairs):
        is_label = (k % 2 == 1) if a['first_volume'] == 'control' else (k % 2 == 0)
        img = static * drift[k] - (dm if is_label else 0)
        vols.append(img + sig * rng.standard_normal(lab.shape))
    asl = np.abs(np.array(vols, np.float32))
    m0meas = m0t * (1 - np.exp(-a['m0_tr_s'] / np.where(lab > 0, t1, 1.0)))
    m0meas = np.where(lab > 0, m0meas, 0) + sig * rng.standard_normal(lab.shape)
    m0meas = np.abs(m0meas).astype(np.float32)
    inp = case_dir / 'inputs'
    inp.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(inp / 'asl.npz', asl=asl)
    np.savez_compressed(inp / 'm0.npz', m0=m0meas)
    np.savez_compressed(inp / 't1.npz', t1_s=t1.astype(np.float32))
    (inp / 'acq.json').write_text(json.dumps(a, indent=1) + '\n')
    return dict(cbf=cbf.astype(np.float32), labels=lab, pld_by_slice=pld, alpha_eff=alpha)


CASES = {
    'public': (37101, dict(shape=(11, 64, 64), cbf_gm=56.0, cbf_wm=21.5, npairs=26, noise_sd=2.1, t1_tissue=(1.30, 0.80, 4.1), m0_tissue=(880.0, 740.0, 1000.0), acq=dict(
        label_duration_s=1.6, pld_s=1.9, slice_order=(list(range(1, 11, 2)) + list(range(0, 11, 2)))[::-1], slice_interval_s=0.052, labeling_efficiency=0.81,
        n_bs_pulses=3, bs_inversion_efficiency=0.91, m0_tr_s=2.8, first_volume='label', t1_blood_s=1.58,
        partition_coefficient_mL_per_g=0.9))),
    'case1': (38211, dict(shape=(17, 64, 64), cbf_gm=66.0, cbf_wm=25.5, npairs=24, noise_sd=1.9, t1_tissue=(1.25, 0.78, 4.3), m0_tissue=(865.0, 725.0, 1000.0), acq=dict(
        label_duration_s=1.9, pld_s=1.75, slice_order=list(range(17)), slice_interval_s=0.038,
        labeling_efficiency=0.89, n_bs_pulses=2, bs_inversion_efficiency=0.97, m0_tr_s=1.9, first_volume='control', t1_blood_s=1.68,
        partition_coefficient_mL_per_g=0.9))),
    'case2': (38322, dict(shape=(10, 64, 64), cbf_gm=46.0, cbf_wm=18.0, npairs=40, noise_sd=2.15, t1_tissue=(1.15, 0.70, 3.7), m0_tissue=(845.0, 710.0, 1000.0), acq=dict(
        label_duration_s=1.45, pld_s=2.1, slice_order=list(range(1, 10, 2)) + list(range(0, 10, 2)), slice_interval_s=0.07, labeling_efficiency=0.79,
        n_bs_pulses=4, bs_inversion_efficiency=0.945, m0_tr_s=2.4, first_volume='label', t1_blood_s=1.42,
        partition_coefficient_mL_per_g=0.9))),
}

if __name__ == '__main__':
    for name, (seed, p) in CASES.items():
        d = TASK / 'public' if name == 'public' else HERE / 'hidden' / name
        tr = make(d, seed, p, name == 'public')
        tdir = HERE / 'truth' if name == 'public' else d
        tdir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(tdir / ('public_truth.npz' if name == 'public' else 'truth.npz'), **tr)
        print(name, 'alpha_eff', round(tr['alpha_eff'], 4), 'pld', np.round(tr['pld_by_slice'], 3))

