#!/usr/bin/env python3
"""Deterministic grader for the pilot repeatability and study-design task."""
import json, math, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pilot_stats as S
TASK = json.loads((HERE.parent / 'public' / 'task.json').read_text())
KEY = json.loads((HERE / 'key.json').read_text())
SCHEMA = 'mrfoundry.heldout-v6.pilotdesign.grade.v1'
REQ = ['design.json', 'plan.md']


def locate(ws):
    ws = Path(ws)
    if all((ws / f).exists() for f in REQ):
        return ws, 'root'
    subs = [d for d in sorted(ws.iterdir()) if d.is_dir() and not d.name.startswith('.')] if ws.exists() else []
    c = [d for d in subs if all((d / f).exists() for f in REQ)]
    if c:
        d = max(c, key=lambda p: (p / REQ[0]).stat().st_mtime); return d, 'subfolder:' + d.name
    return ws, 'incomplete'


def f(x):
    try:
        if isinstance(x, bool) or x is None: return None
        v = float(x); return v if math.isfinite(v) else None
    except Exception:
        return None


def pair(x):
    if isinstance(x, (list, tuple)) and len(x) == 2 and all(f(v) is not None for v in x):
        return sorted([f(x[0]), f(x[1])])
    if isinstance(x, dict):
        lo = f(x.get('lower', x.get('lo'))); hi = f(x.get('upper', x.get('hi')))
        if lo is not None and hi is not None: return [lo, hi]
    return None


def rel(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol * abs(b)


def g(d, *path):
    for p in path:
        if not isinstance(d, dict): return None
        d = d.get(p)
    return d


def grade(ws, ev=None, *_):
    src, where = locate(ws)
    checks, meas = {}, {'deliverable_dir': str(src), 'located': where}
    def put(n, ok, d): checks[n] = {'pass': bool(ok), 'detail': d}
    present = all((src / f_).exists() for f_ in REQ)
    D, md = None, ''
    if present:
        try:
            D = json.loads((src / 'design.json').read_text())
        except Exception as e:
            meas['json_error'] = str(e)[:300]
        md = (src / 'plan.md').read_text(errors='replace')
    put('deliverables_present', present and isinstance(D, dict), f'located={where}; files={[x for x in REQ if (src / x).exists()]}')
    if not isinstance(D, dict): D = {}
    R = KEY['ref']; C = KEY['cfg']; V = TASK['design_vocabulary']
    rep = D.get('repeatability') if isinstance(D.get('repeatability'), dict) else {}
    pg = D.get('pilot_group_comparison') if isinstance(D.get('pilot_group_comparison'), dict) else {}
    A = g(D, 'designs', 'acute_challenge') or {}; G = g(D, 'designs', 'group_difference') or {}
    if not isinstance(A, dict): A = {}
    if not isinstance(G, dict): G = {}

    errs = []
    for nm, obj, keys in [('repeatability', rep, ['n_participants', 'within_subject_sd', 'within_subject_sd_ci95', 'repeatability_coefficient', 'icc_form', 'icc', 'icc_ci95']),
                          ('pilot_group_comparison', pg, ['n_patients', 'n_controls', 'mean_difference', 'mean_difference_ci95', 'pooled_sd']),
                          ('acute_challenge', A, ['design', 'unit_of_analysis', 'sd_type', 'sd_used', 'n_evaluable', 'n_enrol']),
                          ('group_difference', G, ['design', 'unit_of_analysis', 'sd_type', 'sd_used', 'n_evaluable_per_group', 'n_enrol_per_group'])]:
        for k in keys:
            if k not in obj: errs.append(f'{nm}.{k} missing')
    for nm, obj in [('acute_challenge', A), ('group_difference', G)]:
        if obj.get('design') not in V['design']: errs.append(f'{nm}.design {obj.get("design")!r}')
        if obj.get('unit_of_analysis') not in V['unit_of_analysis']: errs.append(f'{nm}.unit {obj.get("unit_of_analysis")!r}')
        if obj.get('sd_type') not in V['sd_type']: errs.append(f'{nm}.sd_type {obj.get("sd_type")!r}')
    if D.get('endpoint_unit_of_analysis') not in V['unit_of_analysis']: errs.append('endpoint_unit_of_analysis')
    put('schema_valid', present and not errs, '; '.join(errs[:10]) or 'ok')

    qx = D.get('qc_exclusions') if isinstance(D.get('qc_exclusions'), dict) else {}
    tr_ex = set(map(str, qx.get('test_retest') or [])) if isinstance(qx.get('test_retest'), list) else None
    gr_ex = set(map(str, qx.get('groups') or [])) if isinstance(qx.get('groups'), list) else None
    ok = (tr_ex == set(KEY['excluded_tr']) and gr_ex == set(KEY['excluded_groups']) and f(rep.get('n_participants')) == R['n_tr'] and
          f(pg.get('n_patients')) == R['group']['n_patients'] and f(pg.get('n_controls')) == R['group']['n_controls'])
    put('qc_exclusions_applied', present and ok, f"excluded tr={sorted(tr_ex) if tr_ex is not None else None} groups={sorted(gr_ex) if gr_ex is not None else None}; n={rep.get('n_participants')}/{pg.get('n_patients')}/{pg.get('n_controls')}")

    units = [D.get('endpoint_unit_of_analysis'), A.get('unit_of_analysis'), G.get('unit_of_analysis')]
    put('unit_of_analysis_participant', present and all(u == 'participant' for u in units), f'units={units}')

    w = f(rep.get('within_subject_sd')); wci = pair(rep.get('within_subject_sd_ci95'))
    variants = [(R['wsd'], R['wsd_ci']), (R['wsd_centered'], R['wsd_centered_ci'])]
    okw = any(rel(w, rv, 0.03) and wci is not None and rel(wci[0], rc[0], 0.05) and rel(wci[1], rc[1], 0.05) for rv, rc in variants)
    put('within_subject_sd_correct', present and okw, f'wsd={w} ci={wci}; reference {R["wsd"]:.3f} {[round(x, 3) for x in R["wsd_ci"]]} (centered variant {R["wsd_centered"]:.3f})')
    rc = f(rep.get('repeatability_coefficient'))
    okrc = any(rel(rc, 1.96 * math.sqrt(2) * rv, 0.03) for rv, _ in variants)
    put('repeatability_coefficient_correct', present and okrc, f'rc={rc}; reference {R["rc"]:.3f}')
    icc = f(rep.get('icc')); ici = pair(rep.get('icc_ci95'))
    form = str(rep.get('icc_form', '')).replace(' ', '').upper()
    okicc = (icc is not None and abs(icc - R['icc']) <= 0.01 and ici is not None and abs(ici[0] - R['icc_ci'][0]) <= 0.02 and abs(ici[1] - R['icc_ci'][1]) <= 0.02
             and ('2,1' in form or 'A,1' in form))
    put('icc_correct', present and okicc, f'icc={icc} ci={ici} form={rep.get("icc_form")}; reference {R["icc"]:.3f} {[round(x, 3) for x in R["icc_ci"]]}')

    Gr = R['group']
    md_ = f(pg.get('mean_difference')); mci = pair(pg.get('mean_difference_ci95')); sp = f(pg.get('pooled_sd'))
    okg = (md_ is not None and abs(md_ - Gr['diff']) <= 0.05 and mci is not None and
           any(abs(mci[0] - c[0]) <= 0.1 and abs(mci[1] - c[1]) <= 0.1 for c in [Gr['ci_pooled'], Gr['ci_welch']]) and rel(sp, Gr['sd_pooled'], 0.03))
    put('pilot_group_estimates_correct', present and okg, f'diff={md_} ci={mci} sd={sp}; reference {Gr["diff"]:.3f} {[round(x, 2) for x in Gr["ci_pooled"]]} sd {Gr["sd_pooled"]:.3f}')

    a = KEY['cfg']['alpha']; p = KEY['cfg']['power']; ne = KEY['cfg']['nonevaluable']
    # acute challenge
    sdA = f(A.get('sd_used')); sd_refs = [math.sqrt(2) * R['wsd'], math.sqrt(2) * R['wsd_centered']]
    okAd = A.get('design') == 'paired_crossover' and A.get('sd_type') == 'sd_of_within_participant_differences' and any(rel(sdA, s_, 0.04) for s_ in sd_refs)
    put('acute_design_correct', present and okAd, f"design={A.get('design')} sd_type={A.get('sd_type')} sd={sdA}; reference sd of differences {sd_refs[0]:.3f}")
    lo = min(S.n_paired_z(s_ * 0.96, C['delta_acute'], a, p) for s_ in sd_refs); hi = max(S.n_paired_t(s_ * 1.04, C['delta_acute'], a, p) for s_ in sd_refs) + 1
    nA, eA = f(A.get('n_evaluable')), f(A.get('n_enrol'))
    own = sdA is not None and sdA > 0 and nA is not None and S.n_paired_z(sdA, C['delta_acute'], a, p) - 1 <= nA <= S.n_paired_t(sdA, C['delta_acute'], a, p) + 1
    okAn = nA is not None and lo <= nA <= hi and own and eA is not None and math.ceil(nA / (1 - ne)) <= eA <= math.ceil(nA / (1 - ne)) + 1
    put('acute_sample_size_correct', present and okAn, f'n_evaluable={nA} (accepted {lo}-{hi}, consistent with own sd={own}); n_enrol={eA} (expected {math.ceil(nA / (1 - ne)) if nA else None})')
    # group difference
    sdG = f(G.get('sd_used'))
    okGd = G.get('design') == 'parallel_groups' and G.get('sd_type') == 'between_participant_sd' and rel(sdG, Gr['sd_pooled'], 0.03)
    put('group_design_correct', present and okGd, f"design={G.get('design')} sd_type={G.get('sd_type')} sd={sdG}; reference pooled sd {Gr['sd_pooled']:.3f}")
    lo2 = S.n_two_z(Gr['sd_pooled'] * 0.97, C['delta_group'], a, p); hi2 = S.n_two_t(Gr['sd_pooled'] * 1.03, C['delta_group'], a, p) + 1
    nG, eG = f(G.get('n_evaluable_per_group')), f(G.get('n_enrol_per_group'))
    own2 = sdG is not None and sdG > 0 and nG is not None and S.n_two_z(sdG, C['delta_group'], a, p) - 1 <= nG <= S.n_two_t(sdG, C['delta_group'], a, p) + 1
    okGn = nG is not None and lo2 <= nG <= hi2 and own2 and eG is not None and math.ceil(nG / (1 - ne)) <= eG <= math.ceil(nG / (1 - ne)) + 1
    put('group_sample_size_correct', present and okGn, f'n_evaluable_per_group={nG} (accepted {lo2}-{hi2}, consistent with own sd={own2}); n_enrol_per_group={eG}')

    words = len(re.findall(r'\S+', md))
    nums = set(re.findall(r'(?<![\d.])\d+(?!\.?\d)', md))
    okm = 0 < words <= 1000 and eA is not None and eG is not None and str(int(eA)) in nums and str(int(eG)) in nums
    put('plan_md_consistent', present and okm, f'words={words}; n_enrol values present={eA is not None and str(int(eA)) in nums}/{eG is not None and str(int(eG)) in nums}')
    asum, lim = D.get('assumptions'), D.get('limitations')
    put('assumptions_and_limitations_present', present and isinstance(asum, list) and len(asum) >= 1 and isinstance(lim, list) and len(lim) >= 1, f'assumptions={len(asum) if isinstance(asum, list) else None}; limitations={len(lim) if isinstance(lim, list) else None}')
    meas.update({'acute_window': [lo, hi], 'group_window': [lo2, hi2]})
    return {'schema': SCHEMA, 'all_automated_checks_pass': all(v['pass'] for v in checks.values()), 'checks': checks, 'measurements': meas}


if __name__ == '__main__':
    gg = grade(Path(sys.argv[1]))
    print(json.dumps({'pass': gg['all_automated_checks_pass'], 'failed': [k for k, v in gg['checks'].items() if not v['pass']]}))

