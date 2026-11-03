#!/usr/bin/env python3
"""Standalone T2/B1 fit for the exported CPMG (reference): finite-pulse extended phase graph (relaxation during
RF pulses), least squares on echo magnitudes, T1 fixed at 1 s.
Usage: python fit_t2.py --input measurement.npz --output fit.npz"""
import argparse
import numpy as np
from scipy.optimize import least_squares

SEQ = {'alpha_deg': 120.0, 'tau_ref_s': 7.0e-3, 'tau_exc_s': 1.0e-3, 'esp_s': 12e-3}  # must match sequence.seq
OPT = {'finite_pulse': True, 'fit_b1': True, 'model_alpha_deg': None, 'model_esp_s': None, 'mono': False, 'm': 24}
T1_FIXED = 1.0

def _rf(a, phi):
    e = np.exp(1j * phi); c2 = np.cos(a / 2) ** 2; s2 = np.sin(a / 2) ** 2; s = np.sin(a)
    return np.array([[c2, e ** 2 * s2, -1j * e * s], [np.conj(e) ** 2 * s2, c2, 1j * np.conj(e) * s], [-0.5j * np.conj(e) * s, 0.5j * e * s, np.cos(a)]])

def epg(T2, b1, n, T1=None):
    T1 = T1_FIXED if T1 is None else T1
    alpha = OPT['model_alpha_deg'] or SEQ['alpha_deg']; esp = OPT['model_esp_s'] or SEQ['esp_s']
    tr, te = (SEQ['tau_ref_s'], SEQ['tau_exc_s']) if OPT['finite_pulse'] else (0.0, 0.0)
    K = n + 3; m = OPT['m'] if OPT['finite_pulse'] else 1
    Q = np.zeros((3, K), complex); Q[2, 0] = 1
    def relax(Q, t):
        if t <= 0:
            return Q
        E2 = np.exp(-t / T2); E1 = np.exp(-t / T1); Q = Q.copy(); Q[:2] *= E2; Q[2] *= E1; Q[2, 0] += 1 - E1; return Q
    def shift(Q):
        Fp = np.zeros(K, complex); Fm = np.zeros(K, complex); Fp[1:] = Q[0, :-1]; Fm[:-1] = Q[1, 1:]; Fp[0] = np.conj(Fm[0])
        return np.array([Fp, Fm, Q[2]])
    def pulse(Q, ang, phi, dur):
        R = _rf(ang / m, phi)
        for _ in range(m):
            Q = relax(R @ relax(Q, dur / (2 * m)), dur / (2 * m))
        return Q
    Q = pulse(Q, np.pi / 2 * (b1 if OPT.get('exc_b1', True) else 1.0), np.pi / 2, te)
    Q = shift(relax(Q, esp / 2 - te / 2 - tr / 2))
    out = np.empty(n)
    for i in range(n):
        Q = pulse(Q, np.deg2rad(alpha) * b1, 0.0, tr)
        Q = shift(relax(Q, esp / 2 - tr / 2)); out[i] = abs(Q[0, 0])
        Q = shift(relax(Q, esp / 2 - tr / 2))
    return out

def fit_one(y, te):
    n = len(y); y = np.abs(y)
    if OPT['mono']:
        A = np.vstack([np.ones(n - 1), -te[1:]]).T
        c = np.linalg.lstsq(A, np.log(np.maximum(y[1:], 1e-9)), rcond=None)[0]
        return 1 / c[1], 1.0
    best = None
    for T2 in np.geomspace(0.015, 0.6, 18):
        for b1 in (np.linspace(0.70, 1.32, 9) if OPT['fit_b1'] else [1.0]):
            s = epg(T2, b1, n); m0 = (s @ y) / (s @ s); r = np.sum((y - m0 * s) ** 2)
            if best is None or r < best[0]:
                best = (r, T2, b1, m0)
    if OPT['fit_b1']:
        f = lambda p: p[0] * epg(p[1], p[2], n) - y
        # B1 bounded to the stated range (+margin): alpha*B1 and (360-alpha*B1) give identical echo magnitudes
        x0 = [best[3], best[1], best[2]]; lb, ub = [0, 0.005, 0.6], [np.inf, 3.0, 1.35]
    else:
        f = lambda p: p[0] * epg(p[1], 1.0, n) - y
        x0 = [best[3], best[1]]; lb, ub = [0, 0.005], [np.inf, 3.0]
    r = least_squares(f, x0, bounds=(lb, ub), x_scale='jac')
    return float(r.x[1]), float(r.x[2]) if OPT['fit_b1'] else 1.0

def main(inp, outp):
    d = np.load(inp, allow_pickle=True)
    global T1_FIXED
    S = np.asarray(d['signals']); te = np.asarray(d['echo_times_s'], float)
    t1 = np.asarray(d['t1_s'], float) if 't1_s' in d else np.full(S.shape[0], 1.0)
    res = []
    for i in range(S.shape[0]):
        T1_FIXED = float(t1[i]) if OPT.get('use_t1', True) else 1.0
        res.append(fit_one(S[i], te))
    t2, b1 = zip(*res)
    np.savez(outp, t2_s=np.array(t2), b1=np.array(b1), sample_ids=d['sample_ids'] if 'sample_ids' in d else np.arange(len(t2)))
    return np.array(t2), np.array(b1)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    a = ap.parse_args(); main(a.input, a.output)

