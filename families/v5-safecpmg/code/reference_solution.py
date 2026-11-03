#!/usr/bin/env python3
"""Reference solution for heldout-v5-safecpmg: build sequence -> safety metrics -> KomaMRI simulation -> EPG fit.
build_workspace() is reused by the control scripts."""
import hashlib, json, os, platform, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'
GPY = '/Users/kewang/Documents/Codex/2026-09-22/read-mri-talk-handoff-md-and/work/radial-gre-venv/bin/python'

RUNNER = r'''
import hashlib, json, sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_sequence, safety_check, simulate_koma, fit_t2
SEQ_P = json.loads(sys.argv[1]); FIT_O = json.loads(sys.argv[2]); SIM_P = json.loads(sys.argv[3]); out = Path(sys.argv[4]); inp = Path(sys.argv[5])
out.mkdir(parents=True, exist_ok=True)
seq, p = build_sequence.build(str(out / 'sequence.seq'), SEQ_P)
a = safety_check.analyze(out / 'sequence.seq')
samples = json.loads((inp / 'samples.json').read_text())['samples']
simseq = out / 'sequence.seq'
if SIM_P.get('simulate_other'):
    build_sequence.build(str(out / '_sim_variant.seq'), dict(SEQ_P, **SIM_P['simulate_other'])); simseq = out / '_sim_variant.seq'
ns = [x['n'] for x in a['adc']]
S = simulate_koma.simulate_samples(simseq, samples, ns)
te = np.array(a['cpmg']['echo_times_s'])
sha = hashlib.sha256((out / 'sequence.seq').read_bytes()).hexdigest()
np.savez(out / 'simulation.npz', signals=S, echo_times_s=te, t1_s=np.array([s['T1_s'] for s in samples]), sample_ids=np.array([s['id'] for s in samples]),
         sequence_sha256=np.array(sha), simulator=np.array('KomaMRI 0.14 via juliacall'))
fit_t2.OPT.update(FIT_O)
t2, b1 = fit_t2.main(str(out / 'simulation.npz'), str(out / 'fit_public.npz'))
tr_for_report = SIM_P.get('report_tr_s', a['duration_s'])
E = sum(r['energy_uT2s'] for r in a['rf'])
rep = {'scope': 'safety-constrained CPMG T2/B1 relaxometry, simulation only', 'scanner_ready': False,
       'sequence': {'echo_spacing_ms': a['cpmg']['esp_s'] * 1e3, 'n_echoes': a['cpmg']['n_echo'], 'refocusing_flip_deg': a['cpmg']['ref_flip_deg'][0],
                    'refocusing_duration_ms': p['tau_ref_s'] * 1e3, 'excitation_duration_ms': p['tau_exc_s'] * 1e3, 'tr_s': a['duration_s'],
                    'crusher_moment_cycles_per_m': a['cpmg']['crusher_post_cyc_per_m'][0]},
       'safety': {'b1_rms_uT': float(np.sqrt(E / tr_for_report)), 'b1_peak_uT': a['b1_peak_uT'], 'pns_max_fraction': a['pns_max_fraction'],
                  'gz_rms_mT_per_m': a['gz_rms_mT_per_m'], 'max_grad_mT_per_m': a['max_grad_mT_per_m'], 'max_slew_T_per_m_per_s': a['max_slew_T_per_m_per_s']},
       'simulator': 'KomaMRI 0.14 (juliacall), 2000 Hann-weighted isochromats along z',
       'fit_model': 'finite-pulse extended phase graph (RF split into sub-rotations with relaxation), T1 from input, least squares on |echoes|',
       'fit_public': {s['id']: {'t2_s': float(t2[i]), 'b1': float(b1[i])} for i, s in enumerate(samples)},
       'validation_summary': 'finite-pulse EPG reproduces the KomaMRI echo trains of the exported sequence; public parameters recovered',
       'limitations': ['simulation only; no scanner validation', 'single-compartment samples; B0 = 0', 'T1 must be known (supplied) for the stimulated-echo model']}
(out / 'report.json').write_text(json.dumps(rep, indent=1, default=float))
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5)); tf = a['_tf']; m = tf < 0.035
    ax[0].plot(tf[m] * 1e3, a['_wave']['z'][m] / 42.576e3); ax[0].set_xlabel('ms'); ax[0].set_ylabel('Gz mT/m')
    for i in range(len(S)):
        ax[1].plot(te * 1e3, np.abs(S[i]), '.-', label=samples[i]['id'])
    ax[1].legend(); fig.savefig(out / 'waveforms_and_echoes.png', dpi=80); plt.close(fig)
except Exception as e:
    print('figure failed', e)
'''

def build_workspace(ws, seq_p=None, fit_opt=None, sim_p=None, post=None):
    ws = Path(ws)
    if ws.exists():
        tr = HERE / 'validation' / '_trash'; tr.mkdir(parents=True, exist_ok=True)
        shutil.move(str(ws), str(tr / (ws.name + '_%d' % len(list(tr.iterdir())))))
    code = ws / 'code'; code.mkdir(parents=True)
    shutil.copy2(HERE / 'reference_code' / 'build_sequence.py', code)
    s = (HERE / 'reference_code' / 'fit_t2.py').read_text()
    sp = dict(json.loads(json.dumps({'alpha_deg': 120.0, 'tau_ref_s': 7.0e-3, 'tau_exc_s': 1.0e-3, 'esp_s': 12e-3})), **{k: v for k, v in (seq_p or {}).items() if k in ('alpha_deg', 'tau_ref_s', 'tau_exc_s', 'esp_s')})
    s = s.replace("SEQ = {'alpha_deg': 120.0, 'tau_ref_s': 7.0e-3, 'tau_exc_s': 1.0e-3, 'esp_s': 12e-3}", 'SEQ = ' + repr(sp))
    if fit_opt:
        s = s.replace("'mono': False, 'm': 24}", "'mono': False, 'm': 24, **" + repr(fit_opt) + "}", 1)
    (code / 'fit_t2.py').write_text(s)
    shutil.copy2(HERE / 'seqcheck.py', code / 'safety_check.py')
    shutil.copy2(HERE / 'komareplay.py', code / 'simulate_koma.py')
    (code / 'run_pipeline.py').write_text(RUNNER)
    os.symlink(str(Path(GPY).parent.parent), str(ws / '.venv'))
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', JULIA_NUM_THREADS='1')
    r = subprocess.run([GPY, 'run_pipeline.py', json.dumps(seq_p or {}), json.dumps({}), json.dumps(sim_p or {}), str(ws / 'outputs'), str(PUB)],
                       cwd=code, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-3000:])
    shutil.move(str(code / 'fit_t2.py'), str(ws / 'outputs' / 'fit_t2.py'))
    if post:
        post(ws)
    (ws / 'README.md').write_text(README)
    fr = subprocess.run([GPY, '-m', 'pip', 'freeze'], capture_output=True, text=True).stdout
    (ws / 'environment.txt').write_text('python ' + platform.python_version() + '\nKomaMRI 0.14.0 (Julia, via juliacall)\n' + fr)
    return ws

README = """# Safety-constrained CPMG relaxometry (reference)
Design: 90 deg block excitation (1 ms), 28 block refocusing pulses of 120 deg / 7.0 ms (CPMG phase), ESP 12 ms, symmetric z
crushers (1000 cycles/m, 20 mT/m, 60 T/m/s) and TR 1.0 s. The refocusing angle and pulse length were chosen so that the B1+rms over
the TR stays below the limit while 28 echoes fit in 12 ms spacing; crusher amplitude/slew were reduced to keep the PNS fraction < 0.8.
Simulation: KomaMRI replay of the exported sequence.seq on the Hann-weighted 2000-isochromat samples (12 mm) (B1 scale applied to RF).
Fit: outputs/fit_t2.py, finite-pulse EPG (relaxation during the long refocusing pulses) with T1 from the input archive.
Validation: echo trains of finite-pulse EPG agree with KomaMRI to <0.1 % for known parameters; instantaneous-pulse EPG does not.
Limitations: simulation only; single-compartment samples; no B0 offsets; T1 must be supplied.
"""

if __name__ == '__main__':
    ws = build_workspace(HERE / 'validation' / 'ws_reference')
    ev = HERE / 'validation' / 'eval_reference'
    r = subprocess.run([GPY, str(HERE / 'grade_safecpmg_arm.py'), str(ws), str(ev)], capture_output=True, text=True,
                       env=dict(os.environ, OMP_NUM_THREADS='1', JULIA_NUM_THREADS='1'))
    print(r.stdout, r.stderr[-1500:])

