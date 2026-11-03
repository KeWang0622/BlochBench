"""Generate (sealed round-4 sibling) multi-coil single-voxel PRESS MRS raw data with water reference (heldout-v7-mrsquant)."""
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
PEAKS = {  # name: (ppm, protons, metabolite key)
    'NAA_CH3': (2.008, 3, 'NAA'), 'Cr_CH3': (3.027, 3, 'Cr'), 'Cr_CH2': (3.913, 2, 'Cr'), 'Cho_NCH3': (3.185, 9, 'Cho'),
    'mI_a': (3.522, 2, 'mI'), 'mI_b': (3.614, 2, 'mI'), 'Glx_a': (2.35, 2, 'Glx'), 'Glx_b': (3.75, 1, 'Glx')}
METAB_RELAX = {'NAA': (1.47, 0.247), 'Cr': (1.46, 0.152), 'Cho': (1.30, 0.207), 'mI': (1.23, 0.20), 'Glx': (1.27, 0.18)}
WATER = {'gm': dict(T1=1.33, T2=0.110, content=0.78), 'wm': dict(T1=0.83, T2=0.080, content=0.65), 'csf': dict(T1=3.82, T2=0.503, content=0.97)}


def make(d, seed, p):
    rng = np.random.default_rng(seed)
    f0 = p['f0_MHz']
    n, dt = p['n_points'], p['dwell_s']
    t = np.arange(n) * dt
    TE, TR = p['te_s'], p['tr_s']
    fr = p['fractions']
    K = 1e-3
    lw = p['linewidth_hz']
    ec = p['ecc_amp_rad'] * np.exp(-t / p['ecc_tau_s'])
    gfo = p['global_offset_hz']
    metab = np.zeros(n, complex)
    for name, (ppm, nh, key) in PEAKS.items():
        T1m, T2m = p.get('metab_relax', METAB_RELAX)[key]
        c = p['conc'][key]
        amp = K * nh * c * (fr['gm'] + fr['wm']) * np.exp(-TE / T2m) * (1 - np.exp(-TR / T1m))
        f = (ppm - 4.70) * f0 + gfo
        metab += amp * np.exp(2j * np.pi * f * t - np.pi * lw * t)
    awat = K * 2 * 55510.0 * sum(fr[c] * p.get('water', WATER)[c]['content'] * np.exp(-TE / p.get('water', WATER)[c]['T2']) * (1 - np.exp(-TR / p.get('water', WATER)[c]['T1'])) for c in p.get('water', WATER))
    water = awat * np.exp(2j * np.pi * gfo * t - np.pi * lw * t)
    resid = p['residual_water_frac'] * awat * np.exp(2j * np.pi * (gfo + 1.5) * t - np.pi * (lw * 2.2) * t)
    nc = len(p['coil_mag'])
    sens = np.array(p['coil_mag']) * np.exp(1j * np.array(p['coil_phase']))
    sig = np.array(p['coil_noise']) * p['noise']
    nt = p['n_transients']
    drift = np.linspace(-p['drift_hz'], p['drift_hz'], nt) + np.cumsum(rng.normal(0, p['drift_rw_hz'], nt))
    phs = rng.normal(0, p['phase_jitter_rad'], nt)
    fids = np.zeros((nt, nc, n), np.complex64)
    for k in range(nt):
        s = (metab + resid) * np.exp(1j * (2 * np.pi * drift[k] * t + phs[k] + ec))
        for j in range(nc):
            fids[k, j] = sens[j] * s + sig[j] * (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
    nw = p['n_water']
    wf = np.zeros((nw, nc, n), np.complex64)
    for k in range(nw):
        s = water * np.exp(1j * ec)
        for j in range(nc):
            wf[k, j] = sens[j] * s + sig[j] * (rng.standard_normal(n) + 1j * rng.standard_normal(n)) / np.sqrt(2)
    inp = d / 'inputs'
    inp.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(inp / 'metab.npz', fids=fids)
    np.savez_compressed(inp / 'water.npz', fids=wf)
    prm = dict(spectrometer_frequency_MHz=f0, dwell_time_s=dt, n_points=n, te_s=TE, tr_s=TR, receiver_reference_ppm=4.70,
               tissue_volume_fractions=fr, water=p.get('water', WATER), metabolite_relaxation_s={k: dict(T1=v[0], T2=v[1]) for k, v in p.get('metab_relax', METAB_RELAX).items()},
               pure_water_concentration_mM=55510.0)
    (inp / 'params.json').write_text(json.dumps(prm, indent=1) + '\n')
    return {k: p['conc'][k] for k in ('NAA', 'Cr', 'Cho')}


W15C = {'gm': dict(T1=1.05, T2=0.100, content=0.79), 'wm': dict(T1=0.68, T2=0.078, content=0.68), 'csf': dict(T1=3.90, T2=0.65, content=0.97)}
M15C = {'NAA': (1.38, 0.320), 'Cr': (1.33, 0.200), 'Cho': (1.15, 0.280), 'mI': (1.10, 0.23), 'Glx': (1.18, 0.21)}
W7C = {'gm': dict(T1=1.95, T2=0.050, content=0.79), 'wm': dict(T1=1.25, T2=0.045, content=0.69), 'csf': dict(T1=4.40, T2=0.33, content=0.98)}
M7C = {'NAA': (1.85, 0.140), 'Cr': (1.70, 0.100), 'Cho': (1.45, 0.120), 'mI': (1.55, 0.11), 'Glx': (1.60, 0.10)}
W47 = {'gm': dict(T1=1.70, T2=0.065, content=0.78), 'wm': dict(T1=1.10, T2=0.055, content=0.70), 'csf': dict(T1=4.20, T2=0.40, content=0.97)}
M47 = {'NAA': (1.65, 0.190), 'Cr': (1.58, 0.125), 'Cho': (1.38, 0.160), 'mI': (1.40, 0.14), 'Glx': (1.45, 0.13)}
BASE = dict(n_points=2048, dwell_s=0.00025, n_water=4)
CASES = {
    'public': (37701, dict(BASE, f0_MHz=63.65, coil_mag=[0.85, 1.0, 0.45, 0.7], coil_noise=[1.05, 0.9, 1.4, 1.15], te_s=0.040, tr_s=2.4,
                           fractions=dict(gm=0.57, wm=0.33, csf=0.10), linewidth_hz=3.2, ecc_amp_rad=-2.1, ecc_tau_s=0.042, global_offset_hz=-5.5,
                           residual_water_frac=0.0055, coil_phase=[2.3, -1.1, 0.6, -2.7], noise=0.0021, n_transients=88, drift_hz=2.2, drift_rw_hz=0.4,
                           phase_jitter_rad=0.72, conc=dict(NAA=11.6, Cr=8.0, Cho=1.8, mI=5.3, Glx=9.8), water=W15C, metab_relax=M15C)),
    'case1': (38801, dict(BASE, f0_MHz=298.03, coil_mag=[1.0, 0.55, 0.75, 0.95], coil_noise=[0.95, 1.35, 1.1, 1.0], te_s=0.028, tr_s=5.5,
                          fractions=dict(gm=0.47, wm=0.41, csf=0.12), linewidth_hz=10.5, ecc_amp_rad=2.2, ecc_tau_s=0.025, global_offset_hz=-11.0,
                          residual_water_frac=0.0045, coil_phase=[0.2, -2.4, 1.9, -0.8], noise=0.0023, n_transients=56, drift_hz=3.2, drift_rw_hz=0.45,
                          phase_jitter_rad=0.68, conc=dict(NAA=12.4, Cr=8.7, Cho=2.0, mI=6.2, Glx=11.4), water=W7C, metab_relax=M7C)),
    'case2': (38802, dict(BASE, f0_MHz=200.3, coil_mag=[0.6, 0.8, 1.0, 0.65], coil_noise=[1.25, 1.0, 0.9, 1.2], te_s=0.045, tr_s=3.4,
                          fractions=dict(gm=0.39, wm=0.49, csf=0.12), linewidth_hz=7.5, ecc_amp_rad=-2.5, ecc_tau_s=0.032, global_offset_hz=8.5,
                          residual_water_frac=0.0065, coil_phase=[-1.4, 2.8, -0.3, 1.2], noise=0.0024, n_transients=76, drift_hz=2.8, drift_rw_hz=0.55,
                          phase_jitter_rad=0.78, conc=dict(NAA=9.9, Cr=7.8, Cho=2.4, mI=5.7, Glx=10.8), water=W47, metab_relax=M47)),
}

if __name__ == '__main__':
    for name, (seed, p) in CASES.items():
        d = TASK / 'public' if name == 'public' else HERE / 'hidden' / name
        tr = make(d, seed, p)
        tdir = HERE / 'truth' if name == 'public' else d
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / ('public_truth.json' if name == 'public' else 'truth.json')).write_text(json.dumps(tr) + '\n')
        print(name, tr)

