#!/usr/bin/env python3
"""Grader for heldout-v5-t2study (multi-coil T2 mapping -> subject-level study statistics).
Library: grade(ws, eval_dir, python); CLI: python grade_t2study.py <workspace> <eval_dir> [python]"""
import csv, hashlib, json, math, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent; TASK = HERE.parent
N = 72
REQUIRED = ['map_t2.py', 'study_stats.py', 'roi_t2_by_scan.csv', 'study_stats.json', 'summary.png', 'report.json', 'README.md']
TOL_ROI = 0.03          # relative, per scan ROI mean T2
TOL_VOX = 0.06          # median absolute relative voxel error (labels 1,2)
TOL_DIFF_MS = 1.0       # group difference vs truth-based difference

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def _dirs(ws):
    return [ws] + sorted(q for q in ws.iterdir() if q.is_dir() and not q.name.startswith('.') and q.name not in ('__pycache__', 'node_modules'))

def _is_env(name):
    n = name.lower()
    return n.startswith('env') or n.startswith('requirements') or 'freeze' in n or n.startswith('versions') or n in ('pyproject.toml', 'uv.lock', 'conda.yml', 'conda.yaml')

def locate(ws):
    ws = Path(ws); F = {}
    for name in REQUIRED:
        hits = [d / name for d in _dirs(ws) if (d / name).is_file()]
        F[name] = hits[0] if hits and all(sha(h) == sha(hits[0]) for h in hits) else None
    tm = [d / 't2maps' for d in _dirs(ws) if (d / 't2maps').is_dir()]
    F['t2maps'] = tm[0] if len(tm) == 1 else None
    env = [p for d in _dirs(ws) for p in d.iterdir() if p.is_file() and _is_env(p.name)]
    F['environment_record'] = env[0] if env else None
    return F, None

def analyse(rows):
    subj = {}
    for r in rows:
        s = subj.setdefault(str(r['subject_id']).strip(), {'group': str(r['group']).strip(), 'vals': {}})
        s['vals'][int(float(r['session']))] = float(r['roi_t2_ms'])
    m = {g: np.array([np.mean(list(s['vals'].values())) for s in subj.values() if s['group'] == g]) for g in ('control', 'patient')}
    c, p = m['control'], m['patient']; n1, n2 = len(c), len(p)
    v1, v2 = c.var(ddof=1), p.var(ddof=1); diff = p.mean() - c.mean(); se = math.sqrt(v1 / n1 + v2 / n2)
    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)); t = diff / se
    q = stats.t.ppf(0.975, df); sp = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    pairs = [(s['vals'][1], s['vals'][2]) for s in subj.values() if 1 in s['vals'] and 2 in s['vals']]
    d = np.array([b - a for a, b in pairs]); mm = np.array([(a + b) / 2 for a, b in pairs]); wsd = math.sqrt(np.mean(d ** 2) / 2)
    return dict(n_control=n1, n_patient=n2, mean_control_ms=c.mean(), mean_patient_ms=p.mean(), difference_ms=diff,
                ci95_low_ms=diff - q * se, ci95_high_ms=diff + q * se, welch_t=t, welch_df=df, p_value_two_sided=2 * stats.t.sf(abs(t), df),
                hedges_g=diff / sp * (1 - 3 / (4 * (n1 + n2) - 9)),
                repeatability=dict(n_subjects_with_two_scans=len(pairs), within_subject_sd_ms=wsd, repeatability_coefficient_ms=2.77 * wsd,
                                   within_subject_cv_percent=math.sqrt(np.mean((d / mm) ** 2) / 2) * 100))

def flat(d, pre=''):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, pre + k + '.'))
        else:
            out[pre + k] = v
    return out

def compare_stats(got, exp, rel=1e-3, abs_=1e-6):
    fg, fe = flat(got), flat(exp); bad = {}
    for k, v in fe.items():
        g = fg.get(k)
        try:
            g = float(g)
        except Exception:
            bad[k] = [g, v]; continue
        if not (abs(g - v) <= abs_ + rel * abs(v)):
            bad[k] = [g, v]
    return bad

def run_entry(py, script, args, cwd, timeout=900):
    r = subprocess.run([str(py), script] + [str(a) for a in args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stderr[-1500:]

def map_scores(t2, truth):
    lab = truth['labels']; tt = truth['t2_ms']
    m = (lab == 1) | (lab == 2)
    rel = np.abs(np.asarray(t2, float)[m] / tt[m] - 1); rel = np.where(np.isfinite(rel), rel, np.inf)
    roi = float(np.mean(np.asarray(t2, float)[lab == 1]))
    return dict(roi_mean=roi, roi_true=float(tt[lab == 1].mean()), roi_rel_err=roi / float(tt[lab == 1].mean()) - 1,
                voxel_median_abs_rel_err=float(np.median(rel)), finite_fraction=float(np.isfinite(np.asarray(t2, float)[m]).mean()))

def grade(ws, ev_dir, python=None):
    ws = Path(ws); ev_dir = Path(ev_dir); ev_dir.mkdir(parents=True, exist_ok=True)
    py = Path(python) if python else Path(sys.executable)
    F, _ = locate(ws); C = {}; M = {}
    def chk(n, ok, det):
        C[n] = {'pass': bool(ok), 'detail': det}
    missing = [k for k, v in F.items() if v is None]
    chk('deliverables_present', not missing, {'missing': missing})
    truth = json.loads((HERE / 'hidden/truth.json').read_text())
    parts = {r['subject_id']: r['group'] for r in csv.DictReader(open(TASK / 'public/inputs/participants.tsv'), delimiter='\t')}
    rows = None
    try:
        rows = list(csv.DictReader(open(F['roi_t2_by_scan.csv'])))
        keys = [(r['subject_id'].strip(), int(float(r['session']))) for r in rows]
        exp = {(v['subject_id'], v['session']) for v in truth['scans'].values()}
        okg = all(parts.get(r['subject_id'].strip()) == r['group'].strip() for r in rows)
        chk('per_scan_table_schema', set(keys) == exp and len(keys) == len(exp) and okg, {'n_rows': len(rows), 'groups_match_participants': okg})
    except Exception as e:
        chk('per_scan_table_schema', False, repr(e)[:400])
    try:
        errs = {}
        for r in rows:
            sid = f"{r['subject_id'].strip()}_ses-{int(float(r['session']))}"
            errs[sid] = float(r['roi_t2_ms']) / truth['scans'][sid]['roi_true_t2_ms'] - 1
        mx = max(abs(v) for v in errs.values()); M['per_scan_rel_err'] = errs
        chk('per_scan_roi_accuracy', mx <= TOL_ROI and len(errs) == len(truth['scans']),
            {'max_abs_rel_err': mx, 'mean_rel_err': float(np.mean(list(errs.values()))), 'tolerance': TOL_ROI})
    except Exception as e:
        chk('per_scan_roi_accuracy', False, repr(e)[:400])
    try:
        meds = []; inc = []
        for sid in truth['scans']:
            f = F['t2maps'] / f'{sid}.npz'
            d = np.load(f); t2 = np.asarray(d['t2_ms'], float)
            tr = np.load(HERE / f'hidden/truth_{sid}.npz')
            sc = map_scores(t2, tr); meds.append(sc['voxel_median_abs_rel_err'])
            row = [r for r in rows if f"{r['subject_id'].strip()}_ses-{int(float(r['session']))}" == sid][0]
            inc.append(abs(float(d['roi_mean_t2_ms']) - sc['roi_mean']) <= 0.05 and abs(float(row['roi_t2_ms']) - sc['roi_mean']) <= 0.05
                       and t2.shape == (N, N) and str(d['input_sha256']) == sha(TASK / 'public/inputs/scans' / f'{sid}.npz'))
        chk('t2map_files_consistent', all(inc) and max(meds) <= TOL_VOX,
            {'n_consistent': int(sum(inc)), 'n': len(inc), 'max_voxel_median_abs_rel_err': max(meds)})
    except Exception as e:
        chk('t2map_files_consistent', False, repr(e)[:400])
    # hidden rerun of the mapping entrypoint
    try:
        d = ev_dir / 'hidden_map'; d.mkdir(exist_ok=True); res = {}
        shutil.copy2(F['map_t2.py'], d / 'map_t2.py'); ok = True
        for sid in truth['hidden_scans']:
            shutil.copy2(HERE / f'hidden/{sid}.npz', d / f'{sid}.npz')
            rc, e = run_entry(py, 'map_t2.py', ['--input', f'{sid}.npz', '--output', f'{sid}_t2map.npz'], d)
            if rc != 0:
                res[sid] = {'rc': rc, 'stderr': e}; ok = False; continue
            o = np.load(d / f'{sid}_t2map.npz'); sc = map_scores(o['t2_ms'], np.load(HERE / f'hidden/truth_{sid}.npz'))
            sc['reported_roi_mean'] = float(o['roi_mean_t2_ms']); res[sid] = sc
            ok = ok and abs(sc['roi_rel_err']) <= TOL_ROI and sc['voxel_median_abs_rel_err'] <= TOL_VOX and sc['finite_fraction'] >= 0.99 \
                and abs(sc['reported_roi_mean'] - sc['roi_mean']) <= 0.05
        M['hidden_map'] = res
        chk('hidden_rerun_mapping', ok, res)
    except Exception as e:
        chk('hidden_rerun_mapping', False, repr(e)[:400])
    # statistics: own table reproduces, equals grader computation of the same table
    try:
        got = json.loads(Path(F['study_stats.json']).read_text())
        exp = analyse(rows)
        bad = compare_stats(got, exp)
        d = ev_dir / 'stats_own'; d.mkdir(exist_ok=True)
        shutil.copy2(F['study_stats.py'], d / 'study_stats.py'); shutil.copy2(F['roi_t2_by_scan.csv'], d / 'table.csv')
        rc, e = run_entry(py, 'study_stats.py', ['--input', 'table.csv', '--output', 'out.json'], d)
        bad2 = compare_stats(json.loads((d / 'out.json').read_text()), exp) if rc == 0 else {'rc': [rc, e]}
        chk('stats_reproduce_own_table', not bad and not bad2, {'mismatch_in_submitted_json': bad, 'mismatch_on_rerun': bad2})
    except Exception as e:
        chk('stats_reproduce_own_table', False, repr(e)[:400]); got = {}
    # statistics vs truth-based analysis
    try:
        trows = [dict(subject_id=v['subject_id'], group=v['group'], session=v['session'], roi_t2_ms=v['roi_true_t2_ms']) for v in truth['scans'].values()]
        te = analyse(trows); M['truth_stats'] = te
        okk = (int(got['n_control']) == te['n_control'] and int(got['n_patient']) == te['n_patient'] and abs(float(got['difference_ms']) - te['difference_ms']) <= TOL_DIFF_MS
               and (float(got['p_value_two_sided']) < 0.05) == (te['p_value_two_sided'] < 0.05)
               and float(got['ci95_low_ms']) < te['difference_ms'] < float(got['ci95_high_ms']))
        chk('stats_vs_truth', okk, {'submitted_difference_ms': got.get('difference_ms'), 'truth_difference_ms': te['difference_ms'],
                                    'submitted_p': got.get('p_value_two_sided'), 'truth_p': te['p_value_two_sided'], 'n': [got.get('n_control'), got.get('n_patient')]})
    except Exception as e:
        chk('stats_vs_truth', False, repr(e)[:400])
    # hidden rerun of the statistics entrypoint
    try:
        res = {}; ok = True
        d = ev_dir / 'stats_hidden'; d.mkdir(exist_ok=True); shutil.copy2(F['study_stats.py'], d / 'study_stats.py')
        for tname in truth['hidden_tables']:
            shutil.copy2(HERE / 'hidden' / tname, d / tname)
            rc, e = run_entry(py, 'study_stats.py', ['--input', tname, '--output', tname + '.json'], d)
            if rc != 0:
                res[tname] = {'rc': rc, 'stderr': e}; ok = False; continue
            exp = analyse(list(csv.DictReader(open(HERE / 'hidden' / tname))))
            bad = compare_stats(json.loads((d / (tname + '.json')).read_text()), exp)
            res[tname] = {'mismatches': bad}; ok = ok and not bad
        chk('hidden_rerun_stats', ok, res)
    except Exception as e:
        chk('hidden_rerun_stats', False, repr(e)[:400])
    try:
        rep = json.loads(Path(F['report.json']).read_text())
        okr = all(k in rep for k in ('reconstruction_method', 'fit_model', 'unit_of_analysis', 'software', 'validation_summary', 'limitations')) and bool(rep['limitations'])
        chk('report_schema', okr, {'keys': sorted(rep)})
    except Exception as e:
        chk('report_schema', False, repr(e)[:300])
    return dict(schema='heldout-v5-t2study-r4-grade-1', all_automated_checks_pass=all(v['pass'] for v in C.values()), checks=C,
                measurements=json.loads(json.dumps(M, default=float)), located={k: (str(v) if v else None) for k, v in F.items()})

if __name__ == '__main__':
    ws = Path(sys.argv[1]); ev = Path(sys.argv[2]); py = sys.argv[3] if len(sys.argv) > 3 else None
    g = grade(ws, ev, py); ev.mkdir(parents=True, exist_ok=True)
    (ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

