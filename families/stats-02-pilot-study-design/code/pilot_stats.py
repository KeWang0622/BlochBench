#!/usr/bin/env python3
"""Statistics used to build the key for the pilot-design task (also imported by the grader and controls)."""
import csv, math
import numpy as np
from scipy import stats
from scipy.stats import norm, nct, t as tdist

SIDE = 'knee'
VALUE = 'cartilage_t2_ms'
G1, G0 = 'early_oa', 'control'


def read_csv(p):
    with open(p) as f:
        return list(csv.DictReader(f))


def endpoint_tr(rows, qc=True, unit='participant'):
    out = {}
    for r in rows:
        if qc and r['qc_pass'].strip().lower() != 'true':
            continue
        sid = r['subject_id'] if unit == 'participant' else (r['subject_id'], r[SIDE])
        out.setdefault(sid, {}).setdefault(int(r['session']), []).append(float(r[VALUE]))
    res = {sid: {s: float(np.mean(v)) for s, v in d.items()} for sid, d in out.items()}
    return {k: v for k, v in res.items() if len(v) == 2}


def wsd(ep, centered=False):
    y = np.array([[v[1], v[2]] for v in ep.values()])
    n = len(y); d = y[:, 1] - y[:, 0]
    if centered:
        s2 = np.sum((d - d.mean()) ** 2) / (2 * (n - 1)); df = n - 1
    else:
        s2 = np.sum(d ** 2) / (2 * n); df = n
    s = math.sqrt(s2)
    lo = math.sqrt(df * s2 / stats.chi2.ppf(0.975, df)); hi = math.sqrt(df * s2 / stats.chi2.ppf(0.025, df))
    return s, (lo, hi), df, n


def icc21(ep, alpha=0.05):
    Y = np.array([[v[1], v[2]] for v in ep.values()])
    n, k = Y.shape
    gm = Y.mean(); rm = Y.mean(1); cm = Y.mean(0)
    msr = k * np.sum((rm - gm) ** 2) / (n - 1)
    msc = n * np.sum((cm - gm) ** 2) / (k - 1)
    mse = np.sum((Y - rm[:, None] - cm[None, :] + gm) ** 2) / ((n - 1) * (k - 1))
    icc = (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)
    fj = msc / mse
    vn = (k - 1) * (n - 1) * (k * icc * fj + n * (1 + (k - 1) * icc) - k * icc) ** 2
    vd = (n - 1) * k ** 2 * icc ** 2 * fj ** 2 + (n * (1 + (k - 1) * icc) - k * icc) ** 2
    v = vn / vd
    fs = stats.f.ppf(1 - alpha / 2, n - 1, v); fs2 = stats.f.ppf(1 - alpha / 2, v, n - 1)
    lo = n * (msr - fs * mse) / (fs * (k * msc + (k * n - k - n) * mse) + n * msr)
    hi = n * (fs2 * msr - mse) / (k * msc + (k * n - k - n) * mse + n * fs2 * msr)
    return float(icc), (float(lo), float(hi))


def endpoint_groups(rows, qc=True, unit='participant'):
    out = {}
    for r in rows:
        if qc and r['qc_pass'].strip().lower() != 'true':
            continue
        sid = r['subject_id'] if unit == 'participant' else (r['subject_id'], r[SIDE])
        out.setdefault((r['group'], sid), []).append(float(r[VALUE]))
    g = {G1: [], G0: []}
    for (grp, sid), v in out.items():
        g[grp].append(float(np.mean(v)))
    return g


def group_diff(g):
    a, b = np.array(g[G1]), np.array(g[G0])
    na, nb = len(a), len(b)
    sp = math.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    d = a.mean() - b.mean(); se = sp * math.sqrt(1 / na + 1 / nb); q = tdist.ppf(0.975, na + nb - 2)
    sw = math.sqrt(a.var(ddof=1) / na + b.var(ddof=1) / nb)
    dfw = sw ** 4 / ((a.var(ddof=1) / na) ** 2 / (na - 1) + (b.var(ddof=1) / nb) ** 2 / (nb - 1))
    qw = tdist.ppf(0.975, dfw)
    return {'diff': float(d), 'ci_pooled': (float(d - q * se), float(d + q * se)), 'ci_welch': (float(d - qw * sw), float(d + qw * sw)), 'sd_pooled': sp, 'n_patients': na, 'n_controls': nb}


def zsum(alpha=0.05, power=0.9):
    return norm.ppf(1 - alpha / 2) + norm.ppf(power)


def n_paired_z(sd, delta, alpha=0.05, power=0.9):
    return math.ceil((zsum(alpha, power) * sd / delta) ** 2)


def n_paired_t(sd, delta, alpha=0.05, power=0.9):
    n = 2
    while True:
        df = n - 1; nc = delta / (sd / math.sqrt(n)); q = tdist.ppf(1 - alpha / 2, df)
        if 1 - nct.cdf(q, df, nc) + nct.cdf(-q, df, nc) >= power:
            return n
        n += 1


def n_two_z(sd, delta, alpha=0.05, power=0.9):
    return math.ceil(2 * (zsum(alpha, power) * sd / delta) ** 2)


def n_two_t(sd, delta, alpha=0.05, power=0.9):
    n = 2
    while True:
        df = 2 * n - 2; nc = delta / (sd * math.sqrt(2 / n)); q = tdist.ppf(1 - alpha / 2, df)
        if 1 - nct.cdf(q, df, nc) + nct.cdf(-q, df, nc) >= power:
            return n
        n += 1

