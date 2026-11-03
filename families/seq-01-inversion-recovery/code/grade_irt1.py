#!/usr/bin/env python3
"""Grader for heldout-v5-irt1 (IR radial T1 mapping chain).
Library use: grade(ws, eval_dir, python) ; CLI: python grade_irt1.py <workspace> <eval_dir> [python]"""
import json, hashlib, math, shutil, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import seqtools as st

N = 40; FOV = 0.200; NTI = 5; NSP = 40; NS = 40
TI_SPEC = np.array([0.045, 0.13, 0.33, 0.80, 1.60]); TD_SPEC = 2.4
LIM = dict(grad=36.0, slew=150.0, b1=8.0)
REQUIRED = ['sequence.seq', 'waveforms.png', 'simulation.npz', 'images.npz', 't1map.npz', 't1map.png', 'reconstruct.py', 'fit_t1.py',
            'report.json', 'README.md']
TOL_VIAL = 0.06; TOL_VOX = 0.04; TOL_FIT_VOX = 0.015; TOL_FIT_VIAL = 0.03

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def _cands(ws):
    out = []
    for p in [ws] + sorted(q for q in ws.iterdir() if q.is_dir() and not q.name.startswith('.') and q.name not in ('node_modules', '__pycache__')):
        out.append(p)
    return out

_dirs = _cands

def _is_env(name):
    n = name.lower()
    return n.startswith('env') or n.startswith('requirements') or 'freeze' in n or n.startswith('versions') or n in ('pyproject.toml', 'uv.lock', 'conda.yml', 'conda.yaml')

def locate(ws):
    """Return (dict name->path or None, where-list). A file must exist exactly once at root or in one subfolder."""
    ws = Path(ws); found = {}
    for name in REQUIRED:
        hits = [d / name for d in _cands(ws) if (d / name).is_file()]
        found[name] = hits[0] if len(hits) == 1 else (hits[0] if hits and all(sha(h) == sha(hits[0]) for h in hits) else None)
    env = [p for d in _dirs(ws) for p in d.iterdir() if p.is_file() and _is_env(p.name)]
    found['environment_record'] = env[0] if env else None
    pys = [p for d in _cands(ws) for p in d.glob('*.py') if p.name not in ('reconstruct.py', 'fit_t1.py')]
    found['build_or_simulation_script'] = pys[0] if pys else None
    return found, [str(v) for v in found.values()]

def erode_labels(lab):
    out = lab.copy(); n = lab.shape[0]
    pad = np.pad(lab, 1, mode='edge')
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out[pad[1 + dy:1 + dy + n, 1 + dx:1 + dx + n] != lab] = 0
    return out

def analyse_sequence(seq_path):
    seq = st.read(seq_path); ev = st.events(seq); gw = st.gradient_waveforms(seq); hw = st.hardware(seq)
    rfs = ev['rf']
    exc = [r for r in rfs if 60 < r['flip_deg'] < 120]; inv = [r for r in rfs if r['flip_deg'] > 150]
    other = [r for r in rfs if not (60 < r['flip_deg'] < 120 or r['flip_deg'] > 150)]
    adcs = ev['adc']
    rows = []
    for a in adcs:
        e = [r for r in exc if r['t_center'] < a['t'][0]]
        e = e[-1] if e else None
        i = [r for r in inv if e is not None and r['t_center'] < e['t_center']]
        i = i[-1] if i else None
        nxt = [r for r in inv if e is not None and r['t_center'] > e['t_center']]
        k = st.kspace_at(gw, e['t_center'], a['t'])[:, :2] if e is not None else np.full((len(a['t']), 2), np.nan)
        rows.append(dict(t=a['t'], k=k, ti=(e['t_center'] - i['t_center']) if (e and i) else np.nan,
                         td=(nxt[0]['t_center'] - e['t_center']) if (e and nxt) else np.nan,
                         te=(a['t'][len(a['t']) // 2] - e['t_center']) if e else np.nan, inv_t=i['t_center'] if i else np.nan))
    return dict(seq=seq, ev=ev, hw=hw, exc=exc, inv=inv, other=other, rows=rows)

def periodic_state_error(A):
    """Max relative deviation of Mz before each acquired inversion from the periodic value; excitations treated as ideal 90 deg and inversions as ideal 180 deg (flip accuracy is checked separately), T1 in [0.35,2.0] s."""
    rfs = sorted(A['ev']['rf'], key=lambda r: r['t_center'])
    acq_inv = set(round(r['inv_t'], 7) for r in A['rows'] if np.isfinite(r['inv_t']))
    worst = 0.0
    for T1 in (0.35, 0.7, 1.1, 1.5, 2.0):
        mz = 1.0; t = 0.0
        for r in rfs:
            mz = 1 - (1 - mz) * math.exp(-(r['t_center'] - t) / T1); t = r['t_center']
            if round(t, 7) in acq_inv:
                per = 1 - math.exp(-TD_SPEC / T1)
                worst = max(worst, abs(mz - per) / per)
            mz = mz * (0.0 if 60 < r['flip_deg'] < 120 else (-1.0 if r['flip_deg'] > 150 else math.cos(math.radians(r['flip_deg']))))
    return worst

def contract_k():
    i = np.arange(NS) - NS // 2
    th = np.pi * np.arange(NSP) / NSP
    k = np.zeros((NTI, NSP, NS, 2))
    k[..., 0] = (i[None, :] * np.cos(th)[:, None]) / FOV
    k[..., 1] = (i[None, :] * np.sin(th)[:, None]) / FOV
    return k

def build_archive(A, sig, seq_path, phantom_path):
    K = np.array([r['k'] for r in A['rows']]).reshape(NTI, NSP, NS, 2)
    Tm = np.array([r['t'] for r in A['rows']]).reshape(NTI, NSP, NS)
    TI = np.array([r['ti'] for r in A['rows']]).reshape(NTI, NSP).mean(1)
    td = np.nanmean([r['td'] for r in A['rows']])
    return dict(raw_signal=sig.reshape(NTI, NSP, NS), kxy_cycles_per_m=K, adc_times_s=Tm, inversion_times_s=TI,
                recovery_delay_s=float(td), echo_time_s=float(A['rows'][0]['te']),
                excitation_flip_deg=float(np.mean([r['flip_deg'] for r in A['exc']])),
                inversion_flip_deg=float(np.mean([r['flip_deg'] for r in A['inv']])),
                sequence_sha256=sha(seq_path), phantom_sha256=sha(phantom_path))

def t1_scores(t1, ph):
    lab = ph['labels']; er = erode_labels(lab); truth = ph['T1_s']
    t1 = np.asarray(t1, float)
    vial = {}
    for k in sorted(set(np.unique(lab)) - {0, 1}):
        m = er == k
        vial[str(int(k))] = float(np.nanmedian(t1[m]) / truth[m][0] - 1) if np.isfinite(t1[m]).any() else float('inf')
    obj = er > 0
    rel = np.abs(t1[obj] / truth[obj] - 1)
    rel = np.where(np.isfinite(rel), rel, np.inf)
    return dict(vial_rel_err=vial, max_vial_abs_rel_err=max(abs(v) for v in vial.values()), voxel_median_abs_rel_err=float(np.median(rel)),
                finite_fraction=float(np.isfinite(t1[obj]).mean()))

def run_entry(py, script, args, cwd, timeout=1200):
    r = subprocess.run([str(py), script] + args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stderr[-1500:]

def grade(ws, ev_dir, python=None):
    ws = Path(ws); ev_dir = Path(ev_dir); ev_dir.mkdir(parents=True, exist_ok=True)
    py = Path(python) if python else Path(sys.executable)
    F, _ = locate(ws)
    C = {}; M = {}
    def chk(name, ok, detail):
        C[name] = dict(**{'pass': bool(ok)}, detail=detail)
    missing = [k for k, v in F.items() if v is None]
    chk('deliverables_present', not missing, {'missing': missing})
    pub_ph_path = HERE.parent / 'public/inputs/phantom.npz'
    pub_ph = dict(np.load(pub_ph_path))
    A = None
    if F['sequence.seq'] is not None:
        try:
            A = analyse_sequence(F['sequence.seq'])
        except Exception as e:
            chk('sequence_readable', False, repr(e)[:500])
    if A is None:
        for n in ['sequence_hardware_limits', 'sequence_timing_contract', 'trajectory_contract', 'periodic_state_preparation',
                  'simulation_matches_replay', 'archive_metadata', 'hidden_rerun_t1_accuracy']:
            chk(n, False, 'no readable sequence')
    else:
        hw = A['hw']; M['hardware'] = hw
        chk('sequence_hardware_limits', hw['max_grad_mT_per_m'] <= LIM['grad'] * 1.01 and hw['max_slew_T_per_m_per_s'] <= LIM['slew'] * 1.01
            and hw['max_b1_uT'] <= LIM['b1'] * 1.005, hw)
        rows = A['rows']
        nadc = len(rows); ns_ok = all(len(r['t']) == NS for r in rows)
        det = dict(n_adc=nadc, samples_ok=ns_ok, n_excitation=len(A['exc']), n_inversion=len(A['inv']), n_other_rf=len(A['other']))
        ok = nadc == NTI * NSP and ns_ok and not A['other']
        if ok:
            ti = np.array([r['ti'] for r in rows]).reshape(NTI, NSP)
            td = np.array([r['td'] for r in rows])
            te = np.array([r['te'] for r in rows])
            det.update(ti_ms=(ti.mean(1) * 1e3).round(3).tolist(), ti_max_dev_ms=float(np.nanmax(np.abs(ti - TI_SPEC[:, None])) * 1e3),
                       td_ms_range=[float(np.nanmin(td) * 1e3), float(np.nanmax(td) * 1e3)], te_ms_max=float(np.nanmax(te) * 1e3),
                       exc_flip=[min(r['flip_deg'] for r in A['exc']), max(r['flip_deg'] for r in A['exc'])],
                       inv_flip=[min(r['flip_deg'] for r in A['inv']), max(r['flip_deg'] for r in A['inv'])])
            tdf = td[np.isfinite(td)]
            ok = (det['ti_max_dev_ms'] <= 0.5 and len(tdf) >= nadc - 1 and np.all(np.abs(tdf - TD_SPEC) <= 1e-3) and det['te_ms_max'] <= 3.2
                  and abs(det['exc_flip'][0] - 90) <= 2 and abs(det['exc_flip'][1] - 90) <= 2 and abs(det['inv_flip'][0] - 180) <= 3 and abs(det['inv_flip'][1] - 180) <= 3)
        chk('sequence_timing_contract', ok, det)
        if nadc == NTI * NSP and ns_ok:
            K = np.array([r['k'] for r in rows]).reshape(NTI, NSP, NS, 2)
            err = float(np.nanmax(np.abs(K - contract_k()))) if np.isfinite(K).all() else float('inf')
            chk('trajectory_contract', err <= 0.05, {'max_abs_err_cycles_per_m': err, 'tolerance': 0.05})
            pe = periodic_state_error(A)
            chk('periodic_state_preparation', pe <= 0.005, {'max_rel_dev_Mz_before_acquired_inversions': pe})
        else:
            chk('trajectory_contract', False, 'ADC structure does not follow the sampling contract')
            chk('periodic_state_preparation', False, 'ADC structure does not follow the sampling contract')
    # simulation consistency
    import koma_replay as kr
    if A is not None and len(A['rows']) == NTI * NSP and F['simulation.npz'] is not None:
        try:
            rep_sig = kr.simulate(F['sequence.seq'], pub_ph)
            d = np.load(F['simulation.npz'])
            s = np.asarray(d['raw_signal']).reshape(-1)
            c = np.vdot(s, rep_sig) / np.vdot(s, s)
            rel = float(np.linalg.norm(c * s - rep_sig) / np.linalg.norm(rep_sig)); M['sim_rel_err'] = rel
            same_seq = str(d['sequence_sha256']) == sha(F['sequence.seq']) if 'sequence_sha256' in d else False
            same_ph = str(d['phantom_sha256']) == sha(pub_ph_path) if 'phantom_sha256' in d else False
            chk('simulation_matches_replay', rel <= 0.05 and abs(abs(c) - 1) <= 0.05 and same_seq and same_ph,
                {'rel_err_after_global_phase': rel, 'scale': abs(c), 'sequence_sha_match': same_seq, 'phantom_sha_match': same_ph})
            arc = build_archive(A, rep_sig, F['sequence.seq'], pub_ph_path)
            kerr = float(np.max(np.abs(np.asarray(d['kxy_cycles_per_m']) - arc['kxy_cycles_per_m'])))
            tierr = float(np.max(np.abs(np.asarray(d['inversion_times_s']).reshape(-1) - arc['inversion_times_s'])))
            chk('archive_metadata', kerr <= 0.1 and tierr <= 5e-4, {'kxy_max_abs_err': kerr, 'ti_max_abs_err_s': tierr})
        except Exception as e:
            chk('simulation_matches_replay', False, repr(e)[:600]); chk('archive_metadata', False, 'not evaluated')
    else:
        chk('simulation_matches_replay', False, 'missing sequence/simulation or contract-incompatible ADC structure')
        chk('archive_metadata', False, 'not evaluated')
    # public map accuracy
    try:
        t1 = np.asarray(np.load(F['t1map.npz'])['t1_s'], float)
        im = np.load(F['images.npz'])['images']
        assert t1.shape == (N, N) and im.shape == (NTI, N, N), (t1.shape, im.shape)
        sc = t1_scores(t1, pub_ph); M['public'] = sc
        chk('public_t1_accuracy', sc['max_vial_abs_rel_err'] <= TOL_VIAL and sc['voxel_median_abs_rel_err'] <= TOL_VOX and sc['finite_fraction'] >= 0.98, sc)
    except Exception as e:
        chk('public_t1_accuracy', False, repr(e)[:500]); t1 = None
    # report
    try:
        rep = json.loads(Path(F['report.json']).read_text())
        er = erode_labels(pub_ph['labels'])
        dets = {}; ok = rep.get('scanner_ready') is False and rep.get('bloch_simulation_performed') is True and bool(rep.get('limitations'))
        for k in range(2, int(pub_ph['labels'].max()) + 1):
            v = rep['t1_by_label_ms'][str(k)]; g = float(np.nanmedian(t1[er == k]) * 1e3)
            dets[str(k)] = [v, g]; ok = ok and abs(v / g - 1) <= 0.01
        if A is not None and 'ti_ms' in C['sequence_timing_contract']['detail']:
            rti = np.asarray(rep['realized_inversion_times_ms'], float); gti = np.asarray(C['sequence_timing_contract']['detail']['ti_ms'])
            ok = ok and rti.shape == gti.shape and np.all(np.abs(rti - gti) <= 0.5)
            ok = ok and abs(rep['max_b1_uT'] - A['hw']['max_b1_uT']) <= 0.05 * A['hw']['max_b1_uT'] + 0.05
        chk('report_consistency', ok, dets)
    except Exception as e:
        chk('report_consistency', False, repr(e)[:500])
    # hidden rerun of reconstruct.py + fit_t1.py on a replay of the submitted sequence with a hidden object
    hid_ph_path = HERE / 'hidden/phantom_hidden.npz'; hid_ph = dict(np.load(hid_ph_path))
    if A is not None and len(A['rows']) == NTI * NSP and F['reconstruct.py'] and F['fit_t1.py']:
        try:
            hs = kr.simulate(F['sequence.seq'], hid_ph)
            arc = build_archive(A, hs, F['sequence.seq'], hid_ph_path)
            d = ev_dir / 'hidden_rerun'; d.mkdir(exist_ok=True)
            np.savez(d / 'simulation.npz', **arc)
            shutil.copy2(F['reconstruct.py'], d / 'reconstruct.py'); shutil.copy2(F['fit_t1.py'], d / 'fit_t1.py')
            rc1, e1 = run_entry(py, 'reconstruct.py', ['--input', 'simulation.npz', '--output', 'images.npz'], d)
            rc2, e2 = run_entry(py, 'fit_t1.py', ['--input', 'images.npz', '--output', 't1map.npz'], d) if rc1 == 0 else (1, 'skipped')
            if rc1 == 0 and rc2 == 0:
                sc = t1_scores(np.load(d / 't1map.npz')['t1_s'], hid_ph); M['hidden'] = sc
                chk('hidden_rerun_t1_accuracy', sc['max_vial_abs_rel_err'] <= TOL_VIAL and sc['voxel_median_abs_rel_err'] <= TOL_VOX and sc['finite_fraction'] >= 0.98, sc)
            else:
                chk('hidden_rerun_t1_accuracy', False, {'reconstruct_rc': rc1, 'fit_rc': rc2, 'stderr': (e1 + e2)[-800:]})
        except Exception as e:
            chk('hidden_rerun_t1_accuracy', False, repr(e)[:600])
    else:
        chk('hidden_rerun_t1_accuracy', False, 'sequence not replayable under the contract or entrypoints missing')
    # fit-only rerun on synthetic phase-carrying images
    if F['fit_t1.py']:
        try:
            lab = hid_ph['labels']; T1 = np.where(lab > 0, hid_ph['T1_s'], 1.0)
            m0 = hid_ph['density'] * np.exp(-0.0010 / np.where(lab > 0, hid_ph['T2_s'], 1.0))
            Xn = hid_ph['x_m'] / FOV; Yn = hid_ph['y_m'] / FOV
            phase = 0.3 - 1.4 * Xn + 1.9 * Yn
            sig = np.stack([m0 * (1 - (2 - np.exp(-TD_SPEC / T1)) * np.exp(-ti / T1)) for ti in TI_SPEC])
            rng = np.random.default_rng(6211)
            img = sig * np.exp(1j * phase)[None] + 1e-3 * (rng.standard_normal(sig.shape) + 1j * rng.standard_normal(sig.shape))
            d = ev_dir / 'fit_only'; d.mkdir(exist_ok=True)
            np.savez(d / 'images.npz', images=img.astype(np.complex128), inversion_times_s=TI_SPEC.copy(), input_sha256='synthetic')
            shutil.copy2(F['fit_t1.py'], d / 'fit_t1.py')
            rc, e = run_entry(py, 'fit_t1.py', ['--input', 'images.npz', '--output', 't1map.npz'], d)
            if rc == 0:
                sc = t1_scores(np.load(d / 't1map.npz')['t1_s'], hid_ph); M['fit_only'] = sc
                chk('hidden_fit_only_accuracy', sc['max_vial_abs_rel_err'] <= TOL_FIT_VIAL and sc['voxel_median_abs_rel_err'] <= TOL_FIT_VOX and sc['finite_fraction'] >= 0.98, sc)
            else:
                chk('hidden_fit_only_accuracy', False, {'rc': rc, 'stderr': e})
        except Exception as e:
            chk('hidden_fit_only_accuracy', False, repr(e)[:600])
    else:
        chk('hidden_fit_only_accuracy', False, 'fit_t1.py missing')
    return dict(schema='heldout-v5-irt1-r4-grade-1', all_automated_checks_pass=all(v['pass'] for v in C.values()), checks=C,
                measurements=json.loads(json.dumps(M, default=float)), located={k: (str(v) if v else None) for k, v in F.items()})

if __name__ == '__main__':
    ws = Path(sys.argv[1]); ev = Path(sys.argv[2]); py = sys.argv[3] if len(sys.argv) > 3 else None
    g = grade(ws, ev, py)
    ev.mkdir(parents=True, exist_ok=True)
    (ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

