#!/usr/bin/env python3
"""Grader for heldout-v5-safecpmg. grade(ws, ev, python) -> dict."""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import seqcheck
from seqcheck import LIM
PUBS = HERE.parent / 'public' / 'inputs' / 'samples.json'
HIDS = HERE / 'hidden' / 'hidden_samples.json'
TOL = {'t2_rel': 0.03, 'b1_abs': 0.03, 'report_rel': 0.03, 'sim_abs': 0.01, 'timing_s': 2e-6}
SKIP = {'.venv', 'venv', '.git', '__pycache__', 'site-packages', 'node_modules', '_trash'}

def dirs(ws):
    return [ws] + [d for d in sorted(ws.iterdir()) if d.is_dir() and d.name not in SKIP and not d.name.startswith('.')]

def find(ws, pats):
    for d in dirs(ws):
        for p in pats:
            h = sorted(d.glob(p))
            if h:
                return h[0]
    return None

def locate(ws):
    ws = Path(ws); f = find(ws, ['fit_t2.py'])
    return (f.parent if f else ws), f

def chk(c, n, ok, d):
    c[n] = {'pass': bool(ok), 'detail': d}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rel(a, b):
    return abs(float(a) - float(b)) / max(abs(float(b)), 1e-12)

def grade(ws, ev, python):
    ws = Path(ws).resolve(); ev = Path(ev).resolve(); ev.mkdir(parents=True, exist_ok=True)
    C, meas = {}, {}
    F = {'sequence.seq': find(ws, ['sequence.seq']), 'simulation.npz': find(ws, ['simulation.npz']), 'fit_t2.py': find(ws, ['fit_t2.py']),
         'report.json': find(ws, ['report.json']), 'README.md': find(ws, ['README.md']), 'figure': find(ws, ['*.png', 'figures/*.png']),
         'environment record': find(ws, ['environment*.txt', 'environment*.json', 'environment*.yml', 'requirements*.txt', 'env*.txt', 'pip-freeze*.txt', 'environment*.md'])}
    miss = [k for k, v in F.items() if v is None]
    chk(C, 'deliverables_present', not miss, {'missing': miss})
    pub = json.loads(PUBS.read_text())['samples']; hid = json.loads(HIDS.read_text())
    a = None
    try:
        a = seqcheck.analyze(F['sequence.seq']); st = a['cpmg']
        meas['sequence'] = seqcheck.public_summary(a)
        ok_rf = len(a['rf']) >= 3
        chk(C, 'sequence_readable', ok_rf, {'n_rf': len(a['rf']), 'n_adc': len(a['adc'])})
    except Exception as e:
        chk(C, 'sequence_readable', False, {'error': repr(e)[:400]}); st = {}
    if a is not None and st:
        refl = st['ref_flip_deg']
        cond = {
            'n_echo_in_range': LIM['n_echo_min'] <= st['n_echo'] <= LIM['n_echo_max'],
            'esp_le_10ms': st['esp_s'] <= LIM['esp_s'] + 1e-7,
            'refocusing_timing': st['ref_timing_err_s'] <= TOL['timing_s'],
            'excitation_90': abs(st['exc_flip_deg'] - 90) <= 2.0,
            'refocusing_flips_equal': (max(refl) - min(refl)) <= 0.5,
            'cpmg_phase': st['cpmg_phase_err_deg'] <= 2.0 and st['ref_phase_consistent'],
            'on_resonance_rf': st['freq_offsets'] <= 1e-6,
            'x_y_gradients_zero': a['xy_max_abs_Hz_per_m'] <= 1.0,
            'no_gradient_during_rf_or_adc': a['grad_during_rf_Hz_per_m'] <= 100.0 and a['grad_during_adc_Hz_per_m'] <= 100.0,
            'one_adc_per_echo': st['n_adc'] == st['n_echo'],
            'adc_centred_on_echo': st.get('adc_timing_err_s', 1.0) <= TOL['timing_s'],
        }
        chk(C, 'cpmg_structure', all(cond.values()), {**cond, 'esp_s': st['esp_s'], 'n_echo': st['n_echo'], 'exc_flip_deg': st['exc_flip_deg'],
                                                       'ref_flip_deg': refl[0], 'ref_timing_err_s': st['ref_timing_err_s'], 'adc_timing_err_s': st.get('adc_timing_err_s')})
        pre = np.array(st['crusher_pre_cyc_per_m']); post = np.array(st['crusher_post_cyc_per_m'])
        okc = (np.all(np.abs(pre) >= LIM['crusher_min']) and np.all(np.abs(post) >= LIM['crusher_min']) and np.all(np.abs(pre) <= LIM['crusher_max'])
               and np.all(np.abs(post) <= LIM['crusher_max']) and np.all(np.abs(pre - post) <= 0.02 * np.abs(post))
               and np.all(np.abs(post - post[0]) <= 0.02 * abs(post[0])))
        chk(C, 'crusher_moments', bool(okc), {'pre_min_max': [float(pre.min()), float(pre.max())], 'post_min_max': [float(post.min()), float(post.max())]})
        hw = {'max_grad_mT_per_m': a['max_grad_mT_per_m'], 'max_slew_T_per_m_per_s': a['max_slew_T_per_m_per_s'], 'b1_peak_uT': a['b1_peak_uT'], 'tr_s': a['duration_s']}
        okh = (hw['max_grad_mT_per_m'] <= LIM['max_grad_mT_per_m'] * 1.001 and hw['max_slew_T_per_m_per_s'] <= LIM['max_slew_T_per_m_per_s'] * 1.01
               and hw['b1_peak_uT'] <= LIM['b1_peak_uT'] * 1.001 and hw['tr_s'] <= LIM['tr_s'] + 1e-6)
        chk(C, 'hardware_limits', okh, hw)
        chk(C, 'b1_rms_limit', a['b1_rms_uT'] <= LIM['b1_rms_uT'] * 1.0005, {'b1_rms_uT': a['b1_rms_uT'], 'limit': LIM['b1_rms_uT']})
        chk(C, 'pns_limit', a['pns_max_fraction'] <= LIM['pns_fraction'], {'pns_max_fraction': a['pns_max_fraction'], 'worst': a['pns_worst_ramp'], 'limit': LIM['pns_fraction']})
        chk(C, 'gradient_rms_limit', a['gz_rms_mT_per_m'] <= LIM['gz_rms_mT_per_m'], {'gz_rms_mT_per_m': a['gz_rms_mT_per_m']})
    else:
        for n in ['cpmg_structure', 'crusher_moments', 'hardware_limits', 'b1_rms_limit', 'pns_limit', 'gradient_rms_limit']:
            chk(C, n, False, {'error': 'sequence not analysable'})
    # report consistency
    rep = None
    try:
        rep = json.loads(F['report.json'].read_text()); sf = rep['safety']; sq = rep['sequence']
        pairs = {'b1_rms_uT': (sf['b1_rms_uT'], a['b1_rms_uT']), 'b1_peak_uT': (sf['b1_peak_uT'], a['b1_peak_uT']),
                 'pns_max_fraction': (sf['pns_max_fraction'], a['pns_max_fraction']), 'gz_rms_mT_per_m': (sf['gz_rms_mT_per_m'], a['gz_rms_mT_per_m']),
                 'max_grad_mT_per_m': (sf['max_grad_mT_per_m'], a['max_grad_mT_per_m']), 'max_slew_T_per_m_per_s': (sf['max_slew_T_per_m_per_s'], a['max_slew_T_per_m_per_s']),
                 'echo_spacing_ms': (sq['echo_spacing_ms'], st['esp_s'] * 1e3), 'n_echoes': (sq['n_echoes'], st['n_echo']),
                 'refocusing_flip_deg': (sq['refocusing_flip_deg'], st['ref_flip_deg'][0]), 'tr_s': (sq['tr_s'], a['duration_s'])}
        bad = {k: v for k, v in pairs.items() if rel(v[0], v[1]) > TOL['report_rel']}
        chk(C, 'report_matches_sequence', not bad, {'mismatch': {k: [float(x) for x in v] for k, v in bad.items()}})
    except Exception as e:
        chk(C, 'report_matches_sequence', False, {'error': repr(e)[:300]})
    # grader replay of the exported sequence
    replay_ok = a is not None and st and st.get('n_adc') == st.get('n_echo') and st.get('n_echo', 0) > 0
    Spub = Shid = None
    if replay_ok:
        try:
            import komareplay
            ns = [x['n'] for x in a['adc']]
            Spub = komareplay.simulate_samples(F['sequence.seq'], pub, ns)
            Shid = komareplay.simulate_samples(F['sequence.seq'], hid['samples'], ns)
            rng = np.random.default_rng(hid['noise_seed'])
            Shid = Shid + hid['noise_sigma'] * (rng.standard_normal(Shid.shape) + 1j * rng.standard_normal(Shid.shape))
        except Exception as e:
            replay_ok = False; meas['replay_error'] = repr(e)[:400]
    # agent simulation consistency
    try:
        d = np.load(F['simulation.npz'], allow_pickle=True); s = np.asarray(d['signals'])
        shaok = str(np.asarray(d['sequence_sha256']).item()) == sha(F['sequence.seq'])
        ys = np.abs(s); yg = np.abs(Spub)
        k = float((ys * yg).sum() / (ys * ys).sum()); dev = float(np.abs(k * ys - yg).max())
        meas['simulation_scale'] = k; meas['simulation_max_abs_dev'] = dev
        chk(C, 'simulation_matches_replay', shaok and ys.shape == yg.shape and dev <= TOL['sim_abs'] and 0.5 <= k <= 2.0,
            {'sha_ok': shaok, 'shape': list(ys.shape), 'max_abs_dev_after_scale': dev, 'scale': k, 'tol': TOL['sim_abs']})
    except Exception as e:
        chk(C, 'simulation_matches_replay', False, {'error': repr(e)[:300]})
    # public fit
    try:
        fp = rep['fit_public']
        e2 = max(rel(fp[s_['id']]['t2_s'], s_['T2_s']) for s_ in pub); e1 = max(abs(float(fp[s_['id']]['b1']) - s_['B1_scale']) for s_ in pub)
        meas['public_t2_rel_err_max'] = e2; meas['public_b1_abs_err_max'] = e1
        chk(C, 'public_fit_accuracy', e2 <= TOL['t2_rel'] and e1 <= TOL['b1_abs'], {'t2_rel_err_max': e2, 'b1_abs_err_max': e1})
    except Exception as e:
        chk(C, 'public_fit_accuracy', False, {'error': repr(e)[:300]})
    # hidden rerun of fit_t2.py
    run = {}; fit = None
    if replay_ok and F['fit_t2.py'] is not None and python is not None:
        t = ev / 'hidden_fit'
        if t.exists():
            shutil.move(str(t), str(ev / ('_old_hidden_fit_%d' % len(list(ev.glob('_old_*'))))))
        t.mkdir(parents=True)
        shutil.copy2(F['fit_t2.py'], t / 'fit_t2.py'); shutil.copy2(F['sequence.seq'], t / 'sequence.seq')
        np.savez(t / 'measurement.npz', signals=Shid, echo_times_s=np.array(st['echo_times_s']), t1_s=np.array([x['T1_s'] for x in hid['samples']]),
                 sample_ids=np.array([x['id'] for x in hid['samples']]))
        try:
            r = subprocess.run([str(python), 'fit_t2.py', '--input', 'measurement.npz', '--output', 'fit.npz'], cwd=t, capture_output=True, text=True, timeout=1200)
            run = {'returncode': r.returncode, 'stderr': r.stderr[-800:]}
            if r.returncode == 0:
                fit = np.load(t / 'fit.npz', allow_pickle=True)
        except Exception as e:
            run = {'returncode': -1, 'stderr': repr(e)[:300]}
    chk(C, 'hidden_rerun_runs', fit is not None and 't2_s' in fit and 'b1' in fit, {**run, 'python': str(python)})
    e2 = e1 = None
    if fit is not None and 't2_s' in fit and 'b1' in fit:
        try:
            t2 = np.asarray(fit['t2_s'], float).ravel(); b1 = np.asarray(fit['b1'], float).ravel()
            tt = np.array([x['T2_s'] for x in hid['samples']]); bb = np.array([x['B1_scale'] for x in hid['samples']])
            e2 = float(np.max(np.abs(t2 / tt - 1))); e1 = float(np.max(np.abs(b1 - bb)))
            meas['hidden_t2_rel_err'] = (t2 / tt - 1).round(4).tolist(); meas['hidden_b1_err'] = (b1 - bb).round(4).tolist()
        except Exception as e:
            meas['hidden_fit_error'] = repr(e)[:300]
    chk(C, 'hidden_t2_accuracy', e2 is not None and e2 <= TOL['t2_rel'], {'max_rel_err': e2, 'tol': TOL['t2_rel']})
    chk(C, 'hidden_b1_accuracy', e1 is not None and e1 <= TOL['b1_abs'], {'max_abs_err': e1, 'tol': TOL['b1_abs']})
    rd = F['README.md'].read_text(errors='ignore') if F['README.md'] else ''
    chk(C, 'readme_validation_limitations', len(rd) >= 200 and 'limitation' in rd.lower(), {'chars': len(rd)})
    return {'schema': 'heldout-v5-safecpmg-r4-grade-1', 'all_automated_checks_pass': all(v['pass'] for v in C.values()), 'checks': C,
            'measurements': meas, 'located': {k: str(v) if v else None for k, v in F.items()}}

if __name__ == '__main__':
    ws, ev = Path(sys.argv[1]), Path(sys.argv[2]); py = sys.argv[3] if len(sys.argv) > 3 else sys.executable
    g = grade(ws, ev, py); (ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

