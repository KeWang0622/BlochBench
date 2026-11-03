#!/usr/bin/env python3
"""Run all public subjects and the group statistics (reference)."""
import json, sys
from pathlib import Path
import numpy as np
from scipy import stats
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import process_subject as ps

def welch(x, y):
    x, y = np.asarray(x), np.asarray(y)
    d = y.mean() - x.mean()
    vx, vy = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = np.sqrt(vx + vy); df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    tq = stats.t.ppf(0.975, df); p = 2 * stats.t.sf(abs(d / se), df)
    return d, [d - tq * se, d + tq * se], p, df

def main(inputs, outroot, opt=None):
    inputs = Path(inputs); outroot = Path(outroot)
    rows = [l.split('\t') for l in (inputs / 'participants.tsv').read_text().strip().splitlines()[1:]]
    allres = {}
    for sid, grp in rows:
        d = inputs / sid
        r = ps.run(d / 'dwi.nii.gz', d / 'dwi.json', d / 'labels.nii.gz', outroot / 'subjects' / sid, opt or ps.OPT)
        allres[sid] = {'group': grp, 'labels': r['labels']}
    (outroot / 'subject_results.json').write_text(json.dumps(allres, indent=1) + '\n')
    grp = {}
    for key, name in [('fa', 'fa_label1'), ('md_um2_per_ms', 'md_label1')]:
        c = [allres[s]['labels']['1'][key] for s in allres if allres[s]['group'] == 'control']
        p = [allres[s]['labels']['1'][key] for s in allres if allres[s]['group'] == 'patient']
        d, ci, pv, df = welch(c, p)
        grp[name] = {'mean_control': float(np.mean(c)), 'mean_patient': float(np.mean(p)), 'n_control': len(c), 'n_patient': len(p),
                     'difference_patient_minus_control': float(d), 'ci95': [float(ci[0]), float(ci[1])], 'p_value': float(pv), 'df': float(df),
                     'test': 'Welch two-sample t-test'}
    (outroot / 'group_results.json').write_text(json.dumps(grp, indent=1) + '\n')
    return allres, grp

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

