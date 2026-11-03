#!/usr/bin/env python3
"""Deterministic grader for the methodological-review task (no LLM judge)."""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = json.loads((HERE.parent / 'public' / 'task.json').read_text())
KEY = json.loads((HERE / 'key.json').read_text())
SCHEMA = 'mrfoundry.heldout-v6.methodreview.grade.v1'
REQ = ['review.json', 'review.md']


def locate(ws):
    ws = Path(ws)
    if all((ws / f).exists() for f in REQ):
        return ws, 'root'
    subs = [d for d in sorted(ws.iterdir()) if d.is_dir() and not d.name.startswith('.')] if ws.exists() else []
    c = [d for d in subs if all((d / f).exists() for f in REQ)]
    if c:
        d = max(c, key=lambda p: (p / REQ[0]).stat().st_mtime); return d, 'subfolder:' + d.name
    return ws, 'incomplete'


def normq(s):
    s = str(s)
    for a, b in [('\u2212', '-'), ('\u2013', '-'), ('\u2014', '-'), ('\u00b1', '+/-'), ('\u00d7', 'x'), ('\u2009', ' '), ('\u00a0', ' '), ('\u202f', ' '),
                 ('\u2018', "'"), ('\u2019', "'"), ('\u201c', '"'), ('\u201d', '"'), ('\u00b2', '2'), ('\u207b\u00b3', '^-3'), ('\u2264', '<='), ('\u2265', '>='),
                 ('**', ''), ('\x60', ''), ('\u2026', '...')]:
        s = s.replace(a, b)
    s = re.sub(r'^\s*\[(?:P|T)\d+\]\s*', '', s)
    s = s.strip().strip('"').strip("'").strip()
    s = re.sub(r'^\.\.\.|\.\.\.$', '', s).strip()
    return re.sub(r'\s+', ' ', s).lower()


def grade(ws, ev=None, *_):
    src, where = locate(ws)
    checks, meas = {}, {'deliverable_dir': str(src), 'located': where}
    def put(n, ok, d): checks[n] = {'pass': bool(ok), 'detail': d}
    present = all((src / f).exists() for f in REQ)
    R, md = None, ''
    if present:
        try:
            R = json.loads((src / 'review.json').read_text())
        except Exception as e:
            meas['json_error'] = str(e)[:300]
        md = (src / 'review.md').read_text(errors='replace')
    put('deliverables_present', present and isinstance(R, dict), f'located={where}; files={[f for f in REQ if (src / f).exists()]}')
    if not isinstance(R, dict):
        R = {}
    paras = KEY['paragraphs']
    cats = list(TASK['issue_categories'])
    issues = R.get('issues') if isinstance(R.get('issues'), list) else []
    issues_d = [i for i in issues if isinstance(i, dict)]
    def pid_of(i):
        return str(i.get('paragraph_id', '')).strip().strip('[]')

    errs = []
    if not issues_d: errs.append('no issues')
    if len(issues_d) != len(issues): errs.append('non-object issue entries')
    for i in issues_d:
        if pid_of(i) not in paras: errs.append(f"unknown paragraph_id {i.get('paragraph_id')!r}")
        if i.get('category') not in cats: errs.append(f"category {i.get('category')!r} not in list")
        for k in ['quote', 'justification']:
            if not isinstance(i.get(k), str) or not i.get(k).strip(): errs.append(f"{i.get('issue_id')}: missing {k}")
    if R.get('recommendation') not in ['accept', 'minor_revision', 'major_revision', 'reject']: errs.append(f"recommendation {R.get('recommendation')!r}")
    if len(issues_d) > KEY['max_issues']: errs.append(f'{len(issues_d)} issues > max {KEY["max_issues"]}')
    put('schema_valid', present and not errs, '; '.join(errs[:10]) or 'ok')

    bad_q = []
    for i in issues_d:
        pid = pid_of(i); q = normq(i.get('quote', ''))
        if pid not in paras or len(q) < KEY['quote_min_chars'] or q not in normq(paras[pid]):
            bad_q.append(f"{i.get('issue_id')}@{pid}")
    put('quotes_verbatim', present and bool(issues_d) and not bad_q, f'not verbatim: {bad_q[:10]}' if bad_q else 'all quotes found in their paragraphs')

    found = {}
    for pl in KEY['planted']:
        found[pl['issue']] = any(pid_of(i) in pl['paragraphs'] and i.get('category') in pl['categories'] for i in issues_d)
    nrec = sum(found.values())
    put('recall_planted_issues', present and nrec >= KEY['recall_min'], f'{nrec}/{len(found)} planted problems found (min {KEY["recall_min"]}); missed={[k for k, v in found.items() if not v]}')
    fa = [f"{i.get('paragraph_id')}:{i.get('category')}" for i in issues_d if pid_of(i) in KEY['sound']]
    put('false_accusations_limited', present and bool(issues_d) and len(fa) <= KEY['false_accusations_max'], f'{len(fa)} issues on sound paragraphs (max {KEY["false_accusations_max"]}): {fa[:10]}')
    put('recommendation_consistent', present and R.get('recommendation') in KEY['recommendation_ok'], f"recommendation={R.get('recommendation')}")
    words = len(re.findall(r'\S+', md))
    md_ids = set(re.findall(r'\b[PT]\d{1,2}\b', md))
    need = {pid_of(i) for i in issues_d}
    put('review_md_consistent', present and 0 < words <= KEY['md_max_words'] and need <= md_ids, f'words={words}; ids_missing_from_md={sorted(need - md_ids)}')
    lim = R.get('limitations')
    put('limitations_present', present and isinstance(lim, list) and any(str(x).strip() for x in lim), f'limitations={len(lim) if isinstance(lim, list) else None}')
    meas.update({'recall': nrec, 'planted_found': found, 'false_accusations': fa, 'n_issues': len(issues_d)})
    return {'schema': SCHEMA, 'all_automated_checks_pass': all(v['pass'] for v in checks.values()), 'checks': checks, 'measurements': meas}


if __name__ == '__main__':
    import sys
    g = grade(Path(sys.argv[1]))
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

