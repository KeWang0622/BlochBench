#!/usr/bin/env python3
"""Deterministic grader for the research-gap and study-proposal task (no LLM judge).

grade(ws, ev) -> dict with schema, all_automated_checks_pass, checks, measurements.
All planted structure is read from key.json next to this file; vocabularies from public/task.json.
"""
import json, math, re
from pathlib import Path
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
TASK = json.loads((HERE.parent / 'public' / 'task.json').read_text())
KEY = json.loads((HERE / 'key.json').read_text())
SCHEMA = 'mrfoundry.heldout-v6.gapproposal-r4.grade.v1'
REQ = ['proposal.json', 'proposal.md']
EXTERNAL = [(r'\bet\s+al\b', re.I), (r'\bdoi\b', re.I), (r'https?://', re.I), (r'\bpmid\b', re.I), (r'arxiv', re.I),
            (r'\(\s*[A-Z][A-Za-z\-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z\-]+)?,?\s+(?:19|20)\d{2}[a-z]?\s*\)', 0)]
IDRE = re.compile(KEY.get('id_regex', r'\bR\d{2,3}\b'))


def locate(ws):
    ws = Path(ws)
    if all((ws / f).exists() for f in REQ):
        return ws, 'root'
    cands = [d for d in sorted(ws.iterdir()) if d.is_dir() and not d.name.startswith('.') and all((d / f).exists() for f in REQ)] if ws.exists() else []
    if cands:
        d = max(cands, key=lambda p: (p / REQ[0]).stat().st_mtime)
        return d, 'subfolder:' + d.name
    part = [d for d in [ws] + ([x for x in sorted(ws.iterdir()) if x.is_dir() and not x.name.startswith('.')] if ws.exists() else []) if (d / REQ[0]).exists()]
    return (part[0] if part else ws), 'incomplete'


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def _num(x):
    try:
        if isinstance(x, bool):
            return None
        v = float(str(x).strip().rstrip('%')) if isinstance(x, str) else float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def _ids(x):
    return [str(i).strip() for i in x] if isinstance(x, list) else None


def grade(ws, ev=None, *_):
    ws = Path(ws)
    src, where = locate(ws)
    checks, meas = {}, {'deliverable_dir': str(src), 'located': where}

    def put(name, ok, detail):
        checks[name] = {'pass': bool(ok), 'detail': detail}

    present = all((src / f).exists() for f in REQ)
    P = None
    md = ''
    if present:
        try:
            P = json.loads((src / 'proposal.json').read_text())
        except Exception as e:
            P = None
            meas['json_error'] = str(e)[:300]
        md = (src / 'proposal.md').read_text(errors='replace')
    put('deliverables_present', present and isinstance(P, dict), f'located={where}; files={[f for f in REQ if (src / f).exists()]}')
    if not isinstance(P, dict):
        P = {}

    V = TASK['codes']
    corpus = set(KEY['record_ids'])
    tests = {k: [tuple(t) for t in v] for k, v in KEY['tests'].items()}

    # ---- schema
    errs = []
    def need(obj, path, typ):
        cur = obj
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                errs.append('missing ' + '.'.join(path)); return None
            cur = cur[p]
        if typ and not isinstance(cur, typ):
            errs.append('type ' + '.'.join(path)); return None
        return cur
    audit = need(P, ['evidence_audit'], dict) or {}
    rep = need(P, ['evidence_audit', 'replicated_findings'], list) or []
    con = need(P, ['evidence_audit', 'contradictions'], list) or []
    und = need(P, ['evidence_audit', 'underpowered_claims'], list) or []
    gap = need(P, ['gap'], dict) or {}
    hyp = need(P, ['hypothesis'], dict) or {}
    ep = need(P, ['primary_endpoint'], dict) or {}
    des = need(P, ['design'], dict) or {}
    ss = need(P, ['sample_size'], dict) or {}
    ctl = need(P, ['controls'], list) or []
    risks = need(P, ['risks'], list) or []
    lim = need(P, ['limitations'], list) or []
    for k in ['technique', 'population', 'reference', 'statement', 'supporting_record_ids']:
        need(P, ['gap', k], None)
    for k in ['alpha', 'power', 'sided', 'target_difference', 'target_difference_source_ids', 'sd', 'sd_source_ids', 'n_per_group',
              'smaller_group_fraction', 'smaller_group_fraction_source_ids', 'nonevaluable_fraction', 'nonevaluable_fraction_source_ids', 'n_total_to_enrol']:
        need(P, ['sample_size', k], None)
    for e in rep + con + und + ctl:
        if not isinstance(e, dict):
            errs.append('non-object list entry')
    def chk_code(val, vocab, label):
        if val not in vocab:
            errs.append(f'{label}={val!r} not in vocabulary')
    for e in [x for x in rep + con if isinstance(x, dict)]:
        chk_code(e.get('technique'), V['technique'], 'technique'); chk_code(e.get('population'), V['population'], 'population'); chk_code(e.get('reference'), V['reference'], 'reference')
    if gap:
        chk_code(gap.get('technique'), V['technique'], 'gap.technique'); chk_code(gap.get('population'), V['population'], 'gap.population'); chk_code(gap.get('reference'), V['reference'], 'gap.reference')
    for e in [x for x in con if isinstance(x, dict)]:
        chk_code(e.get('explaining_factor'), TASK['explaining_factor_vocabulary'], 'explaining_factor')
    for e in [x for x in ctl if isinstance(x, dict)]:
        chk_code(e.get('code'), list(TASK['controls_vocabulary']), 'control')
    if des:
        chk_code(des.get('type'), TASK['design_vocabulary']['type'], 'design.type')
        chk_code(des.get('unit_of_analysis'), TASK['design_vocabulary']['unit_of_analysis'], 'design.unit_of_analysis')
        chk_code(des.get('recruitment'), TASK['design_vocabulary']['recruitment'], 'design.recruitment')
    put('schema_valid', present and not errs, '; '.join(errs[:12]) or 'ok')

    # ---- citations within corpus, no external sources
    all_text = list(_strings(P)) + [md]
    used = set()
    for s in all_text:
        used |= set(IDRE.findall(s))
    bad_ids = sorted(used - corpus)
    ext = sorted({pat for pat, fl in EXTERNAL for s in all_text if re.search(pat, s, flags=fl)})
    put('citations_within_corpus', present and not bad_ids and not ext and len(used) > 0, f'ids_used={len(used)}; unknown_ids={bad_ids}; external_patterns={ext}')
    meas['ids_used'] = sorted(used)

    def tested(rid, t, p, r, res=None, adequate=None):
        for (tt, pp, rr, rs, ad) in tests.get(rid, []):
            if tt == t and (p == 'MULTIPLE' or pp == p) and rr == r and (res is None or rs == res) and (adequate is None or ad == adequate):
                return True
        return False

    # ---- replicated finding
    K = KEY['replicated']
    det = []
    tgt = [e for e in rep if isinstance(e, dict) and (e.get('technique'), e.get('population'), e.get('reference')) == (K['technique'], K['population'], K['reference'])]
    ok = bool(tgt) and set(_ids(tgt[0].get('record_ids')) or []) == set(K['ids'])
    det.append(f"planted entry found={bool(tgt)}; ids={(_ids(tgt[0].get('record_ids')) if tgt else None)}")
    for e in [x for x in rep if isinstance(x, dict)]:
        ids = _ids(e.get('record_ids')) or []
        badr = [i for i in ids if not tested(i, e.get('technique'), e.get('population'), e.get('reference'), 'pos', 1)]
        if badr or len(ids) < 2:
            ok = False
            det.append(f"invalid entry {e.get('technique')}/{e.get('population')}/{e.get('reference')}: unsupported={badr} n={len(ids)}")
    put('replicated_finding_correct', present and ok, '; '.join(det))

    # ---- contradiction
    K = KEY['contradiction']
    tgt = [e for e in con if isinstance(e, dict) and (e.get('technique'), e.get('population'), e.get('reference')) == (K['technique'], K['population'], K['reference'])]
    ok, det = False, 'planted contradiction not listed'
    if tgt:
        e = tgt[0]
        s = set(_ids(e.get('significant_record_ids')) or []); n_ = set(_ids(e.get('null_record_ids')) or [])
        tol = set(K['tolerated_extra_ids'])
        ok = set(K['sig_ids']) <= s <= set(K['sig_ids']) | tol and set(K['null_ids']) <= n_ <= set(K['null_ids']) | tol and e.get('explaining_factor') == K['factor']
        det = f"significant={sorted(s)}; null={sorted(n_)}; factor={e.get('explaining_factor')}"
    put('contradiction_correct', present and ok, det)

    # ---- underpowered claims
    K = KEY['underpowered']
    got = {}
    for e in [x for x in und if isinstance(x, dict)]:
        got[str(e.get('record_id'))] = set(_ids(e.get('dependent_record_ids')) or [])
    ok = set(got) == set(K['ids']) and all(got[i] == set(K['dependents'][i]) for i in K['ids'] if i in got)
    put('underpowered_claims_correct', present and ok, f"flagged={sorted(got)}; dependents={ {k: sorted(v) for k, v in got.items()} }")

    # ---- gap
    K = KEY['gap']
    g_ok = (gap.get('technique'), gap.get('population'), gap.get('reference')) == (K['technique'], K['population'], K['reference'])
    put('gap_identified', present and g_ok, f"proposed={gap.get('technique')}/{gap.get('population')}/{gap.get('reference')}")
    sup = set(_ids(gap.get('supporting_record_ids')) or [])
    cover = {c: bool(sup & set(K[c + '_ids'])) for c in ['G3', 'G4', 'G5']}
    outside = sorted(sup - set(K['allowed_support'])); forb = sorted(sup & set(K['forbidden_support']))
    put('gap_support_valid', present and g_ok and all(cover.values()) and not outside and not forb and isinstance(gap.get('statement'), str) and len(gap.get('statement', '')) > 20,
        f'support={sorted(sup)}; coverage={cover}; not_supporting={outside}; underpowered_used={forb}')

    # ---- hypothesis and endpoint
    unit = str(ep.get('unit', '')).strip().lower().replace('milliseconds', 'ms').replace('millisecond', 'ms').replace('kilopascals', 'kpa').replace('kilopascal', 'kpa')
    e_ok = (hyp.get('direction') == K['direction'] and isinstance(hyp.get('statement'), str) and len(hyp.get('statement', '')) > 10 and
            ep.get('technique') == K['technique'] and ep.get('reference') == K['reference'] and unit in K['units'] and
            K['threshold_token'] in str(ep.get('reference_positive_definition', '')) and isinstance(ep.get('definition'), str) and len(ep.get('definition', '')) > 10)
    put('hypothesis_and_endpoint_measurable', present and e_ok,
        f"direction={hyp.get('direction')}; technique={ep.get('technique')}; reference={ep.get('reference')}; unit={ep.get('unit')}; positive_def={ep.get('reference_positive_definition')}")

    # ---- design
    K = KEY['design']
    d_ok = des.get('type') in K['type'] and des.get('unit_of_analysis') in K['unit_of_analysis'] and des.get('recruitment') in K['recruitment']
    put('design_correct', present and d_ok, f"type={des.get('type')}; unit={des.get('unit_of_analysis')}; recruitment={des.get('recruitment')}")

    # ---- sample size
    K = KEY['sample_size']
    a, pw, sided = _num(ss.get('alpha')), _num(ss.get('power')), _num(ss.get('sided'))
    dl, sd = _num(ss.get('target_difference')), _num(ss.get('sd'))
    dsrc, ssrc = set(_ids(ss.get('target_difference_source_ids')) or []), set(_ids(ss.get('sd_source_ids')) or [])
    in_ok = (a is not None and abs(a - K['alpha']) < 1e-9 and pw is not None and abs(pw - K['power']) < 1e-9 and sided == K['sided'] and
             dl is not None and K['delta_range'][0] - K.get('range_tol', 0.5) <= dl <= K['delta_range'][1] + K.get('range_tol', 0.5) and
             sd is not None and K['sd_range'][0] - K.get('range_tol', 0.5) <= sd <= K['sd_range'][1] + K.get('range_tol', 0.5) and
             dsrc and dsrc <= set(K['delta_sources']) and ssrc and ssrc <= set(K['sd_sources']))
    put('sample_size_inputs_valid', present and in_ok,
        f'alpha={a}; power={pw}; sided={sided}; delta={dl} from {sorted(dsrc)}; sd={sd} from {sorted(ssrc)}; accepted delta {K["delta_range"]}, sd {K["sd_range"]}')
    npg, ntot = _num(ss.get('n_per_group')), _num(ss.get('n_total_to_enrol'))
    fr, nv = _num(ss.get('smaller_group_fraction')), _num(ss.get('nonevaluable_fraction'))
    for nm in ['fr', 'nv']:
        v = fr if nm == 'fr' else nv
        if v is not None and v > 1:   # tolerate percent
            if nm == 'fr': fr = v / 100
            else: nv = v / 100
    frs, nvs = set(_ids(ss.get('smaller_group_fraction_source_ids')) or []), set(_ids(ss.get('nonevaluable_fraction_source_ids')) or [])
    r_ok = (fr is not None and K['frac_range'][0] <= fr <= K['frac_range'][1] and frs and frs <= set(K['frac_sources']) and
            nv is not None and K['nonev_range'][0] <= nv <= K['nonev_range'][1] and nvs & set(K['nonev_sources_mri']) and nvs & set(K['nonev_sources_ref']) and
            nvs <= set(K['nonev_sources_mri']) | set(K['nonev_sources_ref']))
    put('recruitment_inputs_valid', present and r_ok, f'smaller_group_fraction={fr} from {sorted(frs)}; nonevaluable_fraction={nv} from {sorted(nvs)}')
    ar_ok, det = False, 'missing inputs'
    if dl and sd and npg is not None and ntot is not None and fr and nv is not None and fr > 0 and nv < 1:
        z = norm.ppf(1 - K['alpha'] / 2) + norm.ppf(K['power'])
        x = 2 * z * z * sd * sd / (dl * dl)
        y_lo = math.floor(x)
        okn = y_lo <= npg <= math.ceil(x) + 1 and float(npg).is_integer()
        t = npg / (fr * (1 - nv))
        okt = math.ceil(t) - 1 <= ntot <= math.ceil(t) + 1 and float(ntot).is_integer()
        ar_ok = okn and okt
        det = f'n_per_group={npg} (formula with own inputs {x:.2f}); n_total_to_enrol={ntot} (formula {t:.2f})'
        meas.update({'n_per_group_formula': x, 'n_total_formula': t})
    put('sample_size_arithmetic', present and ar_ok, det)
    meas.update({'n_per_group': npg, 'n_total_to_enrol': ntot, 'target_difference': dl, 'sd': sd})

    # ---- controls
    K = KEY['controls']
    have = {}
    for e in [x for x in ctl if isinstance(x, dict)]:
        have.setdefault(e.get('code'), set()).update(_ids(e.get('record_ids')) or [])
    miss = [c for c, req in K['required'].items() if c not in have or (req and not (have[c] & set(req)))]
    put('controls_required_present', present and not miss, f'missing_or_unsupported={miss}; listed={sorted(map(str, have))}')
    badsup = {c: sorted(ids - set(K['support_map'][c])) for c, ids in have.items() if c in K['support_map'] and ids - set(K['support_map'][c])}
    put('controls_support_valid', present and not badsup and bool(have), f'ids_not_supporting={badsup}')

    # ---- risks and limitations
    rl = [e for e in risks if isinstance(e, dict) and str(e.get('risk', '')).strip() and str(e.get('mitigation', '')).strip()]
    put('risks_and_limitations_present', present and len(rl) >= 2 and len([x for x in lim if str(x).strip()]) >= 1, f'risks_with_mitigation={len(rl)}; limitations={len(lim)}')

    # ---- markdown
    words = len(re.findall(r'\S+', md))
    nums = set(re.findall(r'(?<![\d.])\d+(?!\.?\d)', md))
    need_ids = sorted(sup)
    md_ids = set(IDRE.findall(md))
    m_ok = (0 < words <= KEY['md_max_words'] and npg is not None and ntot is not None and str(int(npg)) in nums and str(int(ntot)) in nums and
            need_ids and set(need_ids) <= md_ids)
    put('markdown_consistent', present and m_ok, f'words={words}; n_per_group_in_md={npg is not None and str(int(npg)) in nums}; n_total_in_md={ntot is not None and str(int(ntot)) in nums}; support_ids_missing_from_md={sorted(set(need_ids) - md_ids)}')

    allp = all(v['pass'] for v in checks.values())
    return {'schema': SCHEMA, 'all_automated_checks_pass': allp, 'checks': checks, 'measurements': meas}


if __name__ == '__main__':
    import sys
    g = grade(Path(sys.argv[1]))
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

