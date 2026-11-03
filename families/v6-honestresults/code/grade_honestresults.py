#!/usr/bin/env python3
"""Deterministic grader for the honest results-writing task (no LLM judge)."""
import json, math, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = json.loads((HERE.parent / 'public' / 'task.json').read_text())
KEY = json.loads((HERE / 'key.json').read_text())
INP = HERE.parent / 'public' / 'inputs'
SCHEMA = 'mrfoundry.heldout-v6.honestresults-r4.grade.v1'
REQ = ['abstract.md', 'results.md', 'claims.json']
NUMRE = re.compile(r'(?<![A-Za-z\d.])\d+(?:\.\d+)?(?!\d)')
EXTERNAL = [(r'\bet\s+al\b', re.I), (r'\bdoi\b', re.I), (r'https?://', re.I), (r'\bpmid\b', re.I), (r'arxiv', re.I),
            (r'\(\s*[A-Z][A-Za-z\-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z\-]+)?,?\s+(?:19|20)\d{2}[a-z]?\s*\)', 0)]
ABBR = ['vs.', 'e.g.', 'i.e.', 'approx.', 'Fig.', 'fig.', 'cf.', 'No.', 'resp.', 'Eq.', 'al.']
NEG = re.compile(r"\b(no|not|without|neither|nor|didn't|did not)\b", re.I)


def locate(ws):
    ws = Path(ws)
    if all((ws / f).exists() for f in REQ):
        return ws, 'root'
    subs = [d for d in sorted(ws.iterdir()) if d.is_dir() and not d.name.startswith('.')] if ws.exists() else []
    c = [d for d in subs if all((d / f).exists() for f in REQ)]
    if c:
        d = max(c, key=lambda p: (p / 'claims.json').stat().st_mtime); return d, 'subfolder:' + d.name
    return ws, 'incomplete'


def norm_text(s):
    s = s.replace('\u2212', '-').replace('\u2013', '-').replace('\u2014', '-').replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    return s


def strip_cites(s):
    s = re.sub(r'\[[^\]]*@[^\]]*\]', ' ', s)
    s = re.sub(r'\\cite[pt]?\{[^}]*\}', ' ', s)
    return s


def sentences(s):
    s = strip_cites(norm_text(s))
    for a in ABBR:
        s = s.replace(a, a.replace('.', '\u0001'))
    out = []
    for line in s.split('\n'):
        for part in re.split(r'(?<=[.!?])\s+', line):
            part = part.replace('\u0001', '.').strip()
            if part:
                out.append(part)
    return out


def nums(s):
    out = []
    for m in NUMRE.finditer(s):
        t = m.group(0); d = len(t.split('.')[1]) if '.' in t else 0
        out.append((float(t), d))
    return out


def has_num(numlist, v, d):
    tol = 0.5 * 10 ** (-d) + 1e-9
    return any(abs(t - abs(v)) <= tol for t, _ in numlist)


def walk_numbers(o, acc):
    if isinstance(o, bool):
        return
    if isinstance(o, (int, float)):
        acc.add(abs(float(o)))
    elif isinstance(o, str):
        for t, _ in nums(norm_text(o)):
            acc.add(t)
    elif isinstance(o, dict):
        for k, v in o.items():
            walk_numbers(k, acc); walk_numbers(v, acc)
    elif isinstance(o, list):
        for v in o:
            walk_numbers(v, acc)


def fnum(x):
    try:
        if isinstance(x, bool) or x is None:
            return None
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def p_match(claim_p, key_p):
    if isinstance(key_p, str):
        if isinstance(claim_p, str):
            return claim_p.replace(' ', '') in ('<0.001', 'p<0.001', '<.001')
        v = fnum(claim_p); return v is not None and v < 0.001
    v = fnum(claim_p)
    return v is not None and abs(v - key_p) <= 0.0005 + 1e-12


def grade(ws, ev=None, *_):
    src, where = locate(ws)
    checks, meas = {}, {'deliverable_dir': str(src), 'located': where}
    def put(n, ok, d): checks[n] = {'pass': bool(ok), 'detail': d}
    present = all((src / f).exists() for f in REQ)
    C = None
    texts = {'abstract': '', 'results': ''}
    if present:
        texts = {'abstract': (src / 'abstract.md').read_text(errors='replace'), 'results': (src / 'results.md').read_text(errors='replace')}
        try:
            C = json.loads((src / 'claims.json').read_text())
        except Exception as e:
            meas['json_error'] = str(e)[:300]
    put('deliverables_present', present and isinstance(C, dict), f'located={where}; files={[f for f in REQ if (src / f).exists()]}')
    if not isinstance(C, dict):
        C = {}
    claims = [c for c in C.get('claims', []) if isinstance(c, dict)] if isinstance(C.get('claims'), list) else []
    E = KEY['entries']
    units = list(TASK['reporting_units'])

    # schema
    errs = []
    if not isinstance(C.get('claims'), list) or not claims:
        errs.append('claims missing/empty')
    for c in claims:
        for k in ['claim_id', 'source_id', 'estimate', 'unit', 'n', 'analysis_type', 'interpretation', 'locations']:
            if k not in c: errs.append(f"{c.get('claim_id')}: missing {k}")
        if c.get('source_id') not in E: errs.append(f"{c.get('claim_id')}: unknown source {c.get('source_id')}")
        if c.get('unit') not in units: errs.append(f"{c.get('claim_id')}: unit {c.get('unit')!r} not in vocabulary")
        locs = c.get('locations')
        if not isinstance(locs, list) or not locs or not set(locs) <= {'abstract', 'results'}: errs.append(f"{c.get('claim_id')}: bad locations")
        if c.get('interpretation') not in ['effect_detected', 'no_effect_detected', 'descriptive', 'exploratory']: errs.append(f"{c.get('claim_id')}: bad interpretation")
    put('claims_schema_valid', present and not errs, '; '.join(errs[:10]) or 'ok')
    by_src = {}
    for c in claims:
        by_src.setdefault(c.get('source_id'), []).append(c)

    # abstract word limit
    words = sum(len(re.findall(r'\S+', ln)) for ln in texts['abstract'].splitlines() if not ln.lstrip().startswith('#'))
    meas['abstract_words'] = words
    put('abstract_word_limit', present and 0 < words <= KEY['abstract_max_words'], f'words={words}')

    # required results reported
    miss = []
    for sid, locs in KEY['required'].items():
        cl = by_src.get(sid, [])
        got = set(l for c in cl for l in (c.get('locations') or []) if isinstance(c.get('locations'), list))
        if not set(locs) <= got: miss.append(f'{sid} missing in {sorted(set(locs) - got)}')
        elif 'ci' in E[sid] and not any(fnum(c.get('ci_lower')) is not None and fnum(c.get('ci_upper')) is not None for c in cl): miss.append(f'{sid} without CI')
    put('required_results_reported', present and not miss, '; '.join(miss) or 'ok')

    # claim values
    bad, ubad = [], []
    for c in claims:
        k = E.get(c.get('source_id'))
        if not k: continue
        d = k['decimals']; tol = 0.5 * 10 ** (-d) + 1e-9; cid = c.get('claim_id')
        if c.get('unit') != k['unit']: ubad.append(f"{cid}: unit {c.get('unit')} expected {k['unit']}")
        est = fnum(c.get('estimate'))
        if est is None or abs(est - k['estimate']) > tol: bad.append(f"{cid}: estimate {c.get('estimate')} expected {k['estimate']}")
        if 'ci' in k:
            lo, hi = fnum(c.get('ci_lower')), fnum(c.get('ci_upper'))
            if lo is None or hi is None or abs(lo - k['ci'][0]) > tol or abs(hi - k['ci'][1]) > tol: bad.append(f"{cid}: CI {lo},{hi} expected {k['ci']}")
        if 'sd' in k:
            sd = fnum(c.get('sd'))
            if sd is None or abs(sd - k['sd']) > tol: bad.append(f"{cid}: sd {c.get('sd')} expected {k['sd']}")
        if 'iqr' in k:
            lo, hi = fnum(c.get('iqr_lower')), fnum(c.get('iqr_upper'))
            if lo is None or hi is None or abs(lo - k['iqr'][0]) > tol or abs(hi - k['iqr'][1]) > tol: bad.append(f"{cid}: IQR expected {k['iqr']}")
        if 'p' in k:
            if not p_match(c.get('p_value'), k['p']) or c.get('p_value_type') != k['p_type']: bad.append(f"{cid}: p {c.get('p_value')} ({c.get('p_value_type')}) expected {k['p']} ({k['p_type']})")
        if fnum(c.get('n')) != k['n']: bad.append(f"{cid}: n {c.get('n')} expected {k['n']}")
        if c.get('analysis_type') != k['analysis_type']: bad.append(f"{cid}: analysis_type {c.get('analysis_type')} expected {k['analysis_type']}")
    put('claim_values_match', present and bool(claims) and not bad, '; '.join(bad[:10]) or f'{len(claims)} claims match')
    put('claim_units_correct', present and bool(claims) and not ubad, '; '.join(ubad[:10]) or 'ok')

    # claimed numbers present in text
    tn = {l: nums(strip_cites(norm_text(t))) for l, t in texts.items()}
    tx = {l: strip_cites(norm_text(t)) for l, t in texts.items()}
    absent = []
    for c in claims:
        k = E.get(c.get('source_id'))
        if not k or not isinstance(c.get('locations'), list): continue
        d = k['decimals']
        vals = [('estimate', fnum(c.get('estimate')), d)]
        for f in ['ci_lower', 'ci_upper', 'sd', 'iqr_lower', 'iqr_upper']:
            if fnum(c.get(f)) is not None: vals.append((f, fnum(c.get(f)), d))
        if fnum(c.get('n')) is not None: vals.append(('n', fnum(c.get('n')), 0))
        for loc in c['locations']:
            if loc not in tn: continue
            for nm, v, dd in vals:
                if v is not None and not has_num(tn[loc], v, dd): absent.append(f"{c.get('claim_id')}.{nm}={v} not in {loc}")
            pv = c.get('p_value')
            if isinstance(pv, str) and '.001' in pv:
                if not re.search(r'<\s*0?\.001', tx[loc]): absent.append(f"{c.get('claim_id')}.p<0.001 not in {loc}")
            elif fnum(pv) is not None and not any(abs(t - fnum(pv)) <= 0.0005 + 1e-12 for t, _ in tn[loc]): absent.append(f"{c.get('claim_id')}.p={pv} not in {loc}")
    put('claim_numbers_in_text', present and bool(claims) and not absent, '; '.join(absent[:10]) or 'ok')

    # primary uncertainty
    pc = by_src.get('E01', [])
    ok = bool(pc) and all(fnum(c.get('ci_lower')) is not None and fnum(c.get('ci_upper')) is not None and c.get('p_value') is not None for c in pc)
    for loc in ['abstract', 'results']:
        k = E['E01']; d0 = k['decimals']
        p_ok = bool(re.search(r'<\s*0?\.001', tx[loc])) if isinstance(k['p'], str) else any(abs(t - k['p']) <= 0.0005 + 1e-12 for t, _ in tn[loc])
        ok = ok and has_num(tn[loc], k['estimate'], d0) and has_num(tn[loc], k['ci'][0], d0) and has_num(tn[loc], k['ci'][1], d0) and p_ok
    put('primary_uncertainty_reported', present and ok, 'E01 estimate, 95% CI and p in both texts' if ok else 'E01 uncertainty missing in a text or claim')

    # interpretation
    ib = []
    for c in claims:
        sid = c.get('source_id'); k = E.get(sid)
        if not k: continue
        want = KEY['interpretation'].get(sid) or ('exploratory' if k['analysis_type'] == 'exploratory' else 'descriptive')
        if c.get('interpretation') != want: ib.append(f"{c.get('claim_id')}: {c.get('interpretation')} expected {want}")
    put('interpretation_consistent', present and bool(claims) and not ib, '; '.join(ib[:8]) or 'ok')

    sents = {l: sentences(t) for l, t in texts.items()}
    allsent = [s for l in sents for s in sents[l]]
    def has_word(s, w):
        return re.search(r'(?<![A-Za-z])' + re.escape(w.lower()) + r'(?![A-Za-z])', s.lower()) is not None

    # null result language
    nb = []
    null_entries = [sid for sid, k in E.items() if 'ci' in k and k['ci'][0] < 0 < k['ci'][1] and k['analysis_type'] in ('primary', 'secondary')]
    for sid in null_entries:
        k = E[sid]
        for loc in ['abstract', 'results']:
            hits = [s for s in sents[loc] if has_num(nums(s), k['estimate'], k['decimals'])]
            if any(loc in (c.get('locations') or []) for c in by_src.get(sid, [])) and not any(any(p in s.lower() for p in TASK['null_statement_phrases']) for s in hits):
                nb.append(f'{sid}: no null statement with the estimate in {loc}')
    for s in allsent:
        if any(kw in s.lower() for kw in KEY['null_keywords']):
            tw = [w for w in TASK['trend_words'] if has_word(s, w)]
            cw = [w for w in TASK['change_words'] if has_word(s, w)]
            if tw or (cw and not NEG.search(s)):
                nb.append(f'forbidden wording {tw + cw} in: {s[:120]}')
    put('no_effect_claim_when_ci_includes_zero', present and not nb, '; '.join(nb[:6]) or 'ok')

    # exploratory labelling
    xb = []
    xvals = [(E[s]['estimate'], E[s]['decimals']) for s in KEY['exploratory_entries']]
    for s in allsent:
        has_est = any(has_num(nums(s), v, d) for v, d in xvals)
        kw = any(k_ in s.lower() for k_ in KEY['exploratory_keywords'])
        if has_est and not re.search(r'exploratory|post[\s-]?hoc', s, re.I):
            xb.append('unlabelled subgroup estimate: ' + s[:120])
        if has_est or kw:
            dw = [w for w in TASK['differential_effect_words'] if has_word(s, w)]
            if dw: xb.append(f'differential wording {dw}: ' + s[:120])
    put('exploratory_labelled', present and not xb, '; '.join(xb[:6]) or 'ok')

    # PDFF units
    pb = []
    for sid in KEY['pp_entries']:
        k = E[sid]; d = k['decimals']
        for v in [k['estimate']] + k.get('ci', []) + ([k['sd']] if 'sd' in k else []):
            f = f'{abs(v):.{d}f}'
            for loc, t in tx.items():
                if re.search(r'(?<![\d.])' + re.escape(f) + r'\s*%', t): pb.append(f'{f}% in {loc} (absolute difference must be percentage points)')
    for sid in KEY['relative_entries']:
        k = E[sid]
        for s in allsent:
            if has_num(nums(s), k['estimate'], k['decimals']) and 'relative' not in s.lower(): pb.append(f'relative change {k["estimate"]} not labelled relative: {s[:100]}')
    put('percentage_point_units', present and not pb, '; '.join(pb[:6]) or 'ok')

    # stiffness in kPa
    kb = [f'{loc}: recorded unit used' for loc, t in tx.items() if re.search(KEY['raw_unit_regex'], t)]
    for sid in KEY['converted_entries']:
        for c in by_src.get(sid, []):
            if c.get('unit') != KEY['converted_unit']: kb.append(f"{c.get('claim_id')} unit {c.get('unit')}")
    conv_claimed = bool(by_src.get('E04'))
    put('converted_unit_reported', present and conv_claimed and not kb, '; '.join(kb) or 'ok')

    # citations
    raw = texts['abstract'] + '\n' + texts['results']
    keys = set()
    for m in re.finditer(r'@([A-Za-z][\w:\-]*)', raw): keys.add(m.group(1))
    for m in re.finditer(r'\\cite[pt]?\{([^}]*)\}', raw): keys |= {x.strip() for x in m.group(1).split(',') if x.strip()}
    unknown = sorted(keys - set(KEY['bib_keys']))
    ext = sorted({p for p, fl in EXTERNAL for s in [raw] + [json.dumps(C)] if re.search(p, s, fl)})
    put('citations_only_supplied', present and not unknown and not ext, f'keys={sorted(keys)}; unknown={unknown}; external={ext}')

    # unsupported numbers
    allowed = {95.0}
    walk_numbers(json.loads((INP / 'results.json').read_text()), allowed)
    for k in E.values():
        walk_numbers([k['estimate'], k.get('ci', []), k.get('sd', 0), k.get('iqr', [])], allowed)
    for t, _ in nums((INP / 'refs.bib').read_text()): allowed.add(t)
    unsup = []
    for loc, t in tx.items():
        for v, d in tn[loc]:
            if not any(abs(round(a, d) - v) < 1e-9 for a in allowed):
                unsup.append(f'{loc}:{v}')
    put('no_unsupported_numbers', present and not unsup, f'unsupported={unsup[:12]}' if unsup else 'ok')

    lim = C.get('limitations')
    put('limitations_present', present and isinstance(lim, list) and any(str(x).strip() for x in lim), f'limitations={len(lim) if isinstance(lim, list) else None}')

    meas['n_claims'] = len(claims)
    return {'schema': SCHEMA, 'all_automated_checks_pass': all(v['pass'] for v in checks.values()), 'checks': checks, 'measurements': meas}


if __name__ == '__main__':
    import sys
    g = grade(Path(sys.argv[1]))
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

