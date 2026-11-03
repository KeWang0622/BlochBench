#!/usr/bin/env python3
"""Grader for heldout-v5-spiralb0 (spiral acquisition with field-map-based off-resonance correction).
Library: grade(ws, eval_dir, python); CLI: python grade_spiralb0.py <workspace> <eval_dir> [python]"""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; TASK = HERE.parent
sys.path.insert(0, str(HERE))
import seqtools as st

N = 40; FOV = 0.216; KMAX = N / (2 * FOV)
LIM = dict(grad=30.0, slew=125.0, b1=13.0)
TE_SPEC = 2.4e-3; TE_TOL = 0.05e-3; READ_MAX = 22e-3; COVER_TOL = 0.75
REQUIRED = ['sequence.seq', 'waveforms.png', 'simulation.npz', 'image.npz', 'reconstruct.py', 'comparison.png', 'report.json', 'README.md']
TOL = dict(field_med=3.0, field_p95=8.0, nrmse=0.07, ratio=0.03, phase=0.2)

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
    env = [p for d in _dirs(ws) for p in d.iterdir() if p.is_file() and _is_env(p.name)]
    F['environment_record'] = env[0] if env else None
    pys = [p for d in _dirs(ws) for p in d.glob('*.py') if p.name != 'reconstruct.py']
    F['build_or_simulation_script'] = pys[0] if pys else None
    return F, None

def erode_labels(lab):
    out = lab.copy(); n = lab.shape[0]; pad = np.pad(lab, 1, mode='edge')
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out[pad[1 + dy:1 + dy + n, 1 + dx:1 + dx + n] != lab] = 0
    return out

def analyse_sequence(path):
    seq = st.read(path); ev = st.events(seq); gw = st.gradient_waveforms(seq); hw = st.hardware(seq)
    det = dict(n_rf=len(ev['rf']), n_adc=len(ev['adc']))
    A = dict(hw=hw, det=det, ok=False)
    if len(ev['rf']) != 1 or len(ev['adc']) != 1:
        return A
    exc = ev['rf'][0]; a = ev['adc'][0]
    K = st.kspace_at(gw, exc['t_center'], a['t'])[:, :2]
    from scipy.spatial import cKDTree
    idx = (np.arange(N) - N // 2) / FOV
    KX, KY = np.meshgrid(idx, idx); m = np.hypot(KX, KY) <= 0.95 * KMAX
    dist = cKDTree(K).query(np.stack([KX[m], KY[m]], 1))[0]
    det.update(flip_deg=exc['flip_deg'], te_ms=(a['t'][0] - exc['t_center']) * 1e3, readout_ms=len(a['t']) * a['dwell'] * 1e3,
               first_sample_k=float(np.hypot(*K[0])), coverage_max_dist_fov_units=float(dist.max() * FOV), n_samples=len(a['t']))
    A.update(K=K, t_adc=a['t'], t_exc=exc['t_center'], det=det, ok=True)
    return A

def explicit_recon(raw, k, t, field, lam=1e-3, chunk=1500):
    idx = np.arange(N) - N // 2
    Y, X = np.meshgrid(idx * FOV / N, idx * FOV / N, indexing='ij')
    r = np.stack([X.ravel(), Y.ravel()], 1); fv = np.asarray(field, float).ravel()
    AhA = np.zeros((N * N, N * N), complex); Ahy = np.zeros(N * N, complex)
    for s in range(0, len(raw), chunk):
        E = np.exp(-2j * np.pi * (k[s:s + chunk] @ r.T + np.outer(t[s:s + chunk], fv)))
        AhA += E.conj().T @ E; Ahy += E.conj().T @ raw[s:s + chunk]
    x = np.linalg.solve(AhA + lam * np.trace(AhA).real / (N * N) * np.eye(N * N), Ahy)
    return x.reshape(N, N)

def image_scores(img, field_est, ph, oracle, te):
    lab = ph['labels']; er = erode_labels(lab); m = er > 0
    img = np.asarray(img); fe = np.abs(np.asarray(field_est, float) - ph['B0_Hz'])[m]
    a = np.abs(img[m]); b = np.abs(oracle[m]); s = np.dot(a, b) / max(np.dot(a, a), 1e-30)
    nrmse = float(np.linalg.norm(s * a - b) / np.linalg.norm(b))
    w = ph['density'] * np.exp(-te / np.where(lab > 0, ph['T2_s'], 1.0))
    ratios = {}; rerr = {}
    for k in sorted(set(np.unique(lab)) - {0, 1}):
        ratios[str(int(k))] = float(np.abs(img[er == k]).mean() / np.abs(img[er == 1]).mean())
        rerr[str(int(k))] = ratios[str(int(k))] - float(w[er == k].mean() / w[er == 1].mean())
    c = np.exp(1j * np.angle(img[m] * np.conj(oracle[m]))).mean()
    csd = float(np.sqrt(max(-2 * np.log(max(abs(c), 1e-12)), 0)))
    return dict(field_median_abs_err_hz=float(np.median(fe)), field_p95_abs_err_hz=float(np.percentile(fe, 95)), nrmse_vs_oracle=nrmse,
                ratios=ratios, ratio_err_vs_truth=rerr, max_abs_ratio_err=max(abs(v) for v in rerr.values()), phase_circ_sd_vs_oracle_rad=csd)

def scores_ok(s):
    return (s['field_median_abs_err_hz'] <= TOL['field_med'] and s['field_p95_abs_err_hz'] <= TOL['field_p95'] and s['nrmse_vs_oracle'] <= TOL['nrmse']
            and s['max_abs_ratio_err'] <= TOL['ratio'] and s['phase_circ_sd_vs_oracle_rad'] <= TOL['phase'])

def run_entry(py, args, cwd, timeout=1500):
    r = subprocess.run([str(py)] + [str(a) for a in args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stderr[-1500:]

def grade(ws, ev_dir, python=None):
    ws = Path(ws); ev_dir = Path(ev_dir); ev_dir.mkdir(parents=True, exist_ok=True)
    py = Path(python) if python else Path(sys.executable)
    F, _ = locate(ws); C = {}; M = {}
    def chk(n, ok, det):
        C[n] = {'pass': bool(ok), 'detail': det}
    missing = [k for k, v in F.items() if v is None]
    chk('deliverables_present', not missing, {'missing': missing})
    pub_ph_path = TASK / 'public/inputs/phantom.npz'; pub_ph = dict(np.load(pub_ph_path))
    hid_ph_path = HERE / 'hidden/phantom_hidden.npz'; hid_ph = dict(np.load(hid_ph_path))
    A = None
    try:
        A = analyse_sequence(F['sequence.seq'])
    except Exception as e:
        chk('sequence_readable', False, repr(e)[:400])
    if A is not None:
        hw = A['hw']; M['hardware'] = hw
        chk('sequence_hardware_limits', hw['max_grad_mT_per_m'] <= LIM['grad'] * 1.01 and hw['max_slew_T_per_m_per_s'] <= LIM['slew'] * 1.01
            and hw['max_b1_uT'] <= LIM['b1'] * 1.005, hw)
        d = A['det']
        ok = A['ok'] and abs(d['flip_deg'] - 90) <= 2 and abs(d['te_ms'] - TE_SPEC * 1e3) <= TE_TOL * 1e3 and d['readout_ms'] <= READ_MAX * 1e3 + 1e-6
        chk('sequence_timing_contract', ok, d)
        ok = A['ok'] and d['first_sample_k'] <= 2.0 and d['coverage_max_dist_fov_units'] <= COVER_TOL
        chk('trajectory_coverage_contract', ok, {k: d.get(k) for k in ('first_sample_k', 'coverage_max_dist_fov_units', 'n_samples')})
    else:
        for n in ('sequence_hardware_limits', 'sequence_timing_contract', 'trajectory_coverage_contract'):
            chk(n, False, 'sequence not readable')
    import koma_replay as kr
    replay_ok = A is not None and A['ok']
    if replay_ok and F['simulation.npz'] is not None:
        try:
            rs = kr.simulate(F['sequence.seq'], pub_ph)
            d = np.load(F['simulation.npz']); s = np.asarray(d['raw_signal']).reshape(-1)
            c = np.vdot(s, rs) / np.vdot(s, s); rel = float(np.linalg.norm(c * s - rs) / np.linalg.norm(rs))
            ss = str(d['sequence_sha256']) == sha(F['sequence.seq']) if 'sequence_sha256' in d else False
            sp = str(d['phantom_sha256']) == sha(pub_ph_path) if 'phantom_sha256' in d else False
            chk('simulation_matches_replay', rel <= 0.05 and abs(abs(c) - 1) <= 0.05 and ss and sp,
                {'rel_err_after_global_phase': rel, 'scale': float(abs(c)), 'sequence_sha_match': ss, 'phantom_sha_match': sp})
            kerr = float(np.max(np.abs(np.asarray(d['kxy_cycles_per_m']).reshape(-1, 2) - A['K'])))
            terr = float(np.max(np.abs(np.asarray(d['adc_times_s']).reshape(-1) - A['t_adc'])))
            eerr = abs(float(d['excitation_time_s']) - A['t_exc'])
            chk('archive_metadata', kerr <= 0.1 and terr <= 1e-6 and eerr <= 1e-6, {'kxy_max_abs_err': kerr, 'adc_time_max_abs_err_s': terr, 'excitation_time_err_s': eerr})
            te = A['det']['te_ms'] * 1e-3
            oracle = explicit_recon(rs, A['K'], A['t_adc'] - A['t_exc'], pub_ph['B0_Hz'])
            im = np.load(F['image.npz'])
            assert np.asarray(im['image']).shape == (N, N) and np.asarray(im['field_map_hz']).shape == (N, N)
            sc = image_scores(im['image'], im['field_map_hz'], pub_ph, oracle, te); M['public'] = sc
            chk('public_field_map_accuracy', sc['field_median_abs_err_hz'] <= TOL['field_med'] and sc['field_p95_abs_err_hz'] <= TOL['field_p95'],
                {k: sc[k] for k in ('field_median_abs_err_hz', 'field_p95_abs_err_hz')})
            chk('public_image_fidelity', sc['nrmse_vs_oracle'] <= TOL['nrmse'] and sc['max_abs_ratio_err'] <= TOL['ratio'] and sc['phase_circ_sd_vs_oracle_rad'] <= TOL['phase'],
                {k: sc[k] for k in ('nrmse_vs_oracle', 'max_abs_ratio_err', 'phase_circ_sd_vs_oracle_rad', 'ratio_err_vs_truth')})
            rep = json.loads(Path(F['report.json']).read_text())
            okr = rep.get('scanner_ready') is False and rep.get('bloch_simulation_performed') is True and bool(rep.get('limitations'))
            okr = okr and all(abs(float(rep['signal_ratio_by_label'][k]) - v) <= 0.01 for k, v in sc['ratios'].items())
            okr = okr and abs(float(rep['realized_echo_time_ms']) - A['det']['te_ms']) <= 0.02
            chk('report_consistency', okr, {'reported': rep.get('signal_ratio_by_label'), 'from_image': sc['ratios']})
        except Exception as e:
            for n in ('simulation_matches_replay', 'archive_metadata', 'public_field_map_accuracy', 'public_image_fidelity', 'report_consistency'):
                if n not in C:
                    chk(n, False, repr(e)[:500])
    else:
        for n in ('simulation_matches_replay', 'archive_metadata', 'public_field_map_accuracy', 'public_image_fidelity', 'report_consistency'):
            chk(n, False, 'sequence does not follow the single-excitation single-ADC contract or files missing')
    if replay_ok and F['reconstruct.py'] is not None:
        try:
            hs = kr.simulate(F['sequence.seq'], hid_ph)
            dd = ev_dir / 'hidden_rerun'; dd.mkdir(exist_ok=True)
            np.savez(dd / 'simulation.npz', raw_signal=hs, kxy_cycles_per_m=A['K'], adc_times_s=A['t_adc'], excitation_time_s=A['t_exc'],
                     echo_time_s=A['det']['te_ms'] * 1e-3, fov_m=FOV, matrix=np.array([N, N]), sequence_sha256=sha(F['sequence.seq']),
                     phantom_sha256=sha(hid_ph_path))
            shutil.copy2(HERE / 'hidden/fieldmap_scan_hidden.npz', dd / 'fieldmap_scan.npz'); shutil.copy2(F['reconstruct.py'], dd / 'reconstruct.py')
            rc, err = run_entry(py, ['reconstruct.py', '--input', 'simulation.npz', '--fieldmap', 'fieldmap_scan.npz', '--output', 'image.npz'], dd)
            if rc != 0:
                chk('hidden_rerun_correction', False, {'rc': rc, 'stderr': err})
            else:
                oracle = explicit_recon(hs, A['K'], A['t_adc'] - A['t_exc'], hid_ph['B0_Hz'])
                im = np.load(dd / 'image.npz')
                sc = image_scores(im['image'], im['field_map_hz'], hid_ph, oracle, A['det']['te_ms'] * 1e-3); M['hidden'] = sc
                chk('hidden_rerun_correction', scores_ok(sc), sc)
        except Exception as e:
            chk('hidden_rerun_correction', False, repr(e)[:600])
    else:
        chk('hidden_rerun_correction', False, 'not replayable or reconstruct.py missing')
    return dict(schema='heldout-v5-spiralb0-r4-grade-1', all_automated_checks_pass=all(v['pass'] for v in C.values()), checks=C,
                measurements=json.loads(json.dumps(M, default=float)), located={k: (str(v) if v else None) for k, v in F.items()})

if __name__ == '__main__':
    ws = Path(sys.argv[1]); ev = Path(sys.argv[2]); py = sys.argv[3] if len(sys.argv) > 3 else None
    g = grade(ws, ev, py); ev.mkdir(parents=True, exist_ok=True)
    (ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

