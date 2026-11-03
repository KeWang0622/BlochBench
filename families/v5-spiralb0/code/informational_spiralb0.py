#!/usr/bin/env python3
"""Informational (not a control): conjugate-phase reconstruction with Voronoi density compensation, scored with the grader's metrics."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import grade_spiralb0 as G, koma_replay as kr
from scipy.spatial import Voronoi

def voronoi_dcf(k):
    k = k + 1e-9 * np.random.default_rng(0).standard_normal(k.shape)
    vor = Voronoi(k); w = np.zeros(len(k))
    for i, reg in enumerate(vor.point_region):
        v = vor.regions[reg]
        if -1 in v or len(v) == 0:
            w[i] = np.nan; continue
        p = vor.vertices[v]; x, y = p[:, 0], p[:, 1]
        w[i] = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
    cap = np.nanpercentile(w, 95); w = np.where(np.isfinite(w), np.minimum(w, cap), cap)
    return w

def pipe_dcf(k, iters=12):
    N, FOV = G.N, G.FOV; idx = np.arange(N) - N // 2
    Y, X = np.meshgrid(idx * FOV / N, idx * FOV / N, indexing='ij'); r = np.stack([X.ravel(), Y.ravel()], 1)
    Es = [np.exp(-2j * np.pi * (k[s:s + 1500] @ r.T)) for s in range(0, len(k), 1500)]
    w = np.ones(len(k))
    for _ in range(iters):
        img = sum(E.conj().T @ w[s * 1500:(s + 1) * 1500] for s, E in enumerate(Es))
        c = np.concatenate([E @ img for E in Es]).real
        w = w / np.maximum(np.abs(c), 1e-12)
    return w

def cp(raw, k, t, field, dcf='voronoi'):
    N, FOV = G.N, G.FOV; idx = np.arange(N) - N // 2
    Y, X = np.meshgrid(idx * FOV / N, idx * FOV / N, indexing='ij'); r = np.stack([X.ravel(), Y.ravel()], 1)
    w = voronoi_dcf(k) if dcf == 'voronoi' else pipe_dcf(k); x = np.zeros(N * N, complex)
    for s in range(0, len(raw), 1500):
        E = np.exp(-2j * np.pi * (k[s:s + 1500] @ r.T + np.outer(t[s:s + 1500], field.ravel())))
        x += E.conj().T @ (w[s:s + 1500] * raw[s:s + 1500])
    return x.reshape(N, N)

out = {}
ws = HERE / 'validation/ws_ref'
A = G.analyse_sequence(ws / 'sequence.seq')
for name, php, fmp in (('public', HERE.parent / 'public/inputs/phantom.npz', HERE.parent / 'public/inputs/fieldmap_scan.npz'),
                       ('hidden', HERE / 'hidden/phantom_hidden.npz', HERE / 'hidden/fieldmap_scan_hidden.npz')):
    ph = dict(np.load(php)); rs = kr.simulate(ws / 'sequence.seq', ph)
    t = A['t_adc'] - A['t_exc']
    oracle = G.explicit_recon(rs, A['K'], t, ph['B0_Hz'])
    fm = np.load(fmp); im = fm['images']; dte = np.diff(fm['echo_times_s'])[0]
    f = -np.angle(im[1] * np.conj(im[0])) / (2 * np.pi * dte)
    img = cp(rs, A['K'], t, f)
    imgp = cp(rs, A['K'], t, f, dcf='pipe')
    scp = G.image_scores(imgp, f, ph, oracle, A['det']['te_ms'] * 1e-3)
    print(name, 'CP(Pipe DCF) nrmse %.3f ratio %.3f phase %.3f pass %s' % (scp['nrmse_vs_oracle'], scp['max_abs_ratio_err'], scp['phase_circ_sd_vs_oracle_rad'], G.scores_ok(scp)), flush=True)
    sc = G.image_scores(img, f, ph, oracle, A['det']['te_ms'] * 1e-3)
    sc0 = G.image_scores(G.explicit_recon(rs, A['K'], t, np.zeros_like(f)), f, ph, oracle, A['det']['te_ms'] * 1e-3)
    out[name] = dict(conjugate_phase_pipe_dcf=scp, conjugate_phase=sc, uncorrected_exact_ls=sc0, cp_passes=G.scores_ok(sc))
    print(name, 'CP nrmse %.3f ratio %.3f phase %.3f pass %s | uncorrected nrmse %.3f ratio %.3f phase %.3f' % (
        sc['nrmse_vs_oracle'], sc['max_abs_ratio_err'], sc['phase_circ_sd_vs_oracle_rad'], G.scores_ok(sc),
        sc0['nrmse_vs_oracle'], sc0['max_abs_ratio_err'], sc0['phase_circ_sd_vs_oracle_rad']), flush=True)
(HERE / 'validation/informational_conjugate_phase.json').write_text(json.dumps(out, indent=1, default=float))

