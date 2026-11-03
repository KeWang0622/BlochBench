#!/usr/bin/env python3
"""Pre-specified study statistics. Usage: python study_stats.py --input roi_t2_by_scan.csv --output study_stats.json"""
import argparse, csv, json
import numpy as np
from scipy import stats

def analyse(rows):
    subj = {}
    for r in rows:
        s = subj.setdefault(r['subject_id'], {'group': r['group'], 'vals': {}})
        if s['group'] != r['group']:
            raise ValueError('inconsistent group for ' + r['subject_id'])
        s['vals'][int(r['session'])] = float(r['roi_t2_ms'])
    m = {g: np.array([np.mean(list(s['vals'].values())) for s in subj.values() if s['group'] == g]) for g in ('control', 'patient')}
    c, p = m['control'], m['patient']
    n1, n2 = len(c), len(p)
    v1, v2 = c.var(ddof=1), p.var(ddof=1)
    diff = p.mean() - c.mean()
    se = np.sqrt(v1 / n1 + v2 / n2)
    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    t = diff / se
    pval = 2 * stats.t.sf(abs(t), df)
    q = stats.t.ppf(0.975, df)
    sp = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    g = diff / sp * (1 - 3 / (4 * (n1 + n2) - 9))
    pairs = [(s['vals'][1], s['vals'][2]) for s in subj.values() if 1 in s['vals'] and 2 in s['vals']]
    d = np.array([b - a for a, b in pairs]); mm = np.array([(a + b) / 2 for a, b in pairs])
    wsd = np.sqrt(np.mean(d ** 2) / 2)
    wcv = np.sqrt(np.mean((d / mm) ** 2) / 2) * 100
    return dict(unit_of_analysis='subject', n_control=n1, n_patient=n2, mean_control_ms=c.mean(), mean_patient_ms=p.mean(),
                difference_ms=diff, ci95_low_ms=diff - q * se, ci95_high_ms=diff + q * se, welch_t=t, welch_df=df,
                p_value_two_sided=pval, hedges_g=g,
                repeatability=dict(n_subjects_with_two_scans=len(pairs), within_subject_sd_ms=wsd,
                                   repeatability_coefficient_ms=2.77 * wsd, within_subject_cv_percent=wcv))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    a = ap.parse_args()
    with open(a.input) as f:
        rows = list(csv.DictReader(f))
    res = analyse(rows)
    res = json.loads(json.dumps(res, default=float))
    with open(a.output, 'w') as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))

if __name__ == '__main__':
    main()

