"""Shared helpers for the heldout-v8 pulse-sequence graders.

Everything here is grader-side code. It reads an exported Pulseq file back with
PyPulseq, rebuilds the gradient waveforms as exact piecewise-linear functions,
computes RF/ADC event tables, k-space and gradient moments, replays the file in
KomaMRI (through juliacall, in a subprocess), and reruns participant entrypoints
in clean directories.  No function here raises on malformed input when called
through Checks.guard.
"""
import hashlib, json, math, os, shutil, subprocess, sys, tempfile, time, traceback, warnings
from pathlib import Path
import numpy as np

GAMMA = 42.576e6
HERE = Path(__file__).resolve().parent


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


class Checks:
    def __init__(self):
        self.c = {}

    def add(self, name, ok, detail):
        self.c[name] = {'pass': bool(ok), 'detail': detail}

    def guard(self, name, fn):
        try:
            ok, det = fn()
        except Exception as e:  # never crash the grader
            ok, det = False, 'error: %s: %s' % (type(e).__name__, str(e)[:600])
        self.add(name, ok, det)
        return ok

    def result(self, **extra):
        out = {'all_automated_checks_pass': bool(self.c) and all(v['pass'] for v in self.c.values()),
               'checks': self.c}
        out.update(extra)
        return out


def locate(ws, marker='sequence.seq'):
    """Deliverables live at the workspace root or in one subfolder."""
    ws = Path(ws)
    try:
        if (ws / marker).exists():
            return ws, '.'
        subs = [d for d in sorted(ws.iterdir()) if d.is_dir() and not d.name.startswith('.')
                and d.name not in ('venv', '__pycache__') and (d / marker).exists()]
        if subs:
            return subs[0], subs[0].name
    except Exception:
        pass
    return ws, None


def load_json(p):
    with open(p) as f:
        return json.load(f)


def load_npz(p):
    with np.load(p, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def num(x):
    a = np.asarray(x)
    if a.size != 1:
        raise ValueError('not a scalar')
    v = float(a.reshape(()).real)
    if not np.isfinite(v):
        raise ValueError('not finite')
    return v


# ----------------------------------------------------------------------------- sequence readback
class SeqInfo:
    """Exact piecewise-linear readback of a Pulseq file (via PyPulseq)."""

    def __init__(self, path, lim):
        import pypulseq as pp
        self.lim = lim
        opts = pp.Opts(max_grad=1e9, grad_unit='Hz/m', max_slew=1e15, slew_unit='Hz/m/s',
                       rf_dead_time=lim['rf_dead_time_s'], rf_ringdown_time=lim['rf_ringdown_time_s'],
                       adc_dead_time=lim['adc_dead_time_s'], grad_raster_time=lim['gradient_raster_s'],
                       rf_raster_time=lim['rf_raster_s'], adc_raster_time=lim['adc_raster_s'],
                       block_duration_raster=lim['block_raster_s'])
        seq = pp.Sequence(system=opts)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            seq.read(str(path))
        self.seq = seq
        self.definitions = dict(seq.definitions) if hasattr(seq, 'definitions') else {}
        self.blocks, self.rfs, self.adcs = [], [], []
        pts = {a: [] for a in 'xyz'}
        self.timing_errors = []
        t = 0.0
        keys = sorted(seq.block_events.keys())
        rr = lim['rf_raster_s']
        for k in keys:
            b = seq.get_block(k)
            dur = float(seq.block_durations[k])
            blk = {'index': k, 't0': t, 'dur': dur, 'rf': None, 'adc': None}
            if b.rf is not None:
                rf = b.rf
                sig = np.asarray(rf.signal, complex)
                tt = np.asarray(rf.t, float)
                if len(tt) > 1 and np.allclose(np.diff(tt), rr, atol=1e-9) and abs(tt[0] - rr / 2) < 1e-9:
                    area = sig.sum() * rr
                    shape_dur = len(tt) * rr
                else:
                    area = np.trapezoid(sig, tt) if hasattr(np, 'trapezoid') else np.trapz(sig, tt)
                    shape_dur = float(tt[-1]) if len(tt) else 0.0
                center = getattr(rf, 'center', None)
                if center is None or not np.isfinite(center):
                    center = float(tt[int(np.argmax(np.abs(sig)))])
                d = {'t_start': t + float(rf.delay), 'dur': float(shape_dur), 't_center': t + float(rf.delay) + float(center),
                     'flip_deg': float(np.degrees(2 * np.pi * abs(area))),
                     'phase_deg': float(np.degrees(float(rf.phase_offset) + np.angle(area))) % 360.0,
                     'phase_offset_deg': float(np.degrees(float(rf.phase_offset))) % 360.0,
                     'freq_Hz': float(rf.freq_offset), 'use': str(getattr(rf, 'use', '') or ''),
                     'signal': sig, 't': tt + t + float(rf.delay), 'block': k, 'peak_Hz': float(np.max(np.abs(sig))) if sig.size else 0.0}
                self.rfs.append(d); blk['rf'] = d
                if rf.delay < lim['rf_dead_time_s'] - 1e-9:
                    self.timing_errors.append('block %d: RF starts %.1f us after block start (< dead time)' % (k, rf.delay * 1e6))
                if dur - (rf.delay + shape_dur) < lim['rf_ringdown_time_s'] - 1e-9:
                    self.timing_errors.append('block %d: RF ringdown violated' % k)
            if b.adc is not None:
                a = b.adc
                n = int(a.num_samples); dw = float(a.dwell)
                ts = t + float(a.delay) + (np.arange(n) + 0.5) * dw
                d = {'t_start': t + float(a.delay), 'n': n, 'dwell': dw, 'times': ts,
                     'phase_deg': float(np.degrees(float(a.phase_offset))) % 360.0, 'freq_Hz': float(a.freq_offset), 'block': k}
                self.adcs.append(d); blk['adc'] = d
                if a.delay < lim['adc_dead_time_s'] - 1e-9:
                    self.timing_errors.append('block %d: ADC starts before dead time' % k)
                if dur + 1e-9 < a.delay + n * dw + lim['adc_dead_time_s']:
                    self.timing_errors.append('block %d: ADC (plus dead time) exceeds block' % k)
                if abs(dw / lim['adc_raster_s'] - round(dw / lim['adc_raster_s'])) > 1e-3:
                    self.timing_errors.append('block %d: ADC dwell not on ADC raster' % k)
            for ax in 'xyz':
                g = getattr(b, 'g' + ax, None)
                if g is None:
                    continue
                gr = lim['gradient_raster_s']
                if g.type == 'trap':
                    de, ri, fl, fa = float(g.delay), float(g.rise_time), float(g.flat_time), float(g.fall_time)
                    A = float(g.amplitude)
                    for q in (de, ri, fl, fa):
                        if abs(q / gr - round(q / gr)) > 1e-3:
                            self.timing_errors.append('block %d g%s: trapezoid timing not on gradient raster' % (k, ax)); break
                    tp = [de, de + ri, de + ri + fl, de + ri + fl + fa]
                    gp = [0.0, A, A, 0.0]
                else:
                    de = float(g.delay)
                    tt = np.asarray(g.tt, float); w = np.asarray(g.waveform, float)
                    first = float(getattr(g, 'first', w[0])); last = float(getattr(g, 'last', w[-1]))
                    regular = len(tt) > 1 and np.allclose(np.diff(tt), gr, atol=1e-9) and abs(tt[0] - gr / 2) < 1e-9
                    if regular:
                        sd = float(getattr(g, 'shape_dur', tt[-1] + gr / 2))
                        tp = [de] + list(de + tt) + [de + sd]
                        gp = [first] + list(w) + [last]
                    else:
                        tp = list(de + tt); gp = list(w)
                        if np.any(np.abs(np.asarray(tt) / gr - np.round(np.asarray(tt) / gr)) > 1e-3):
                            self.timing_errors.append('block %d g%s: gradient corner not on gradient raster' % (k, ax))
                    if tp[-1] > dur + 1e-9:
                        self.timing_errors.append('block %d g%s: gradient exceeds block' % (k, ax))
                    if abs(gp[-1]) > 1e-6 and abs(tp[-1] - dur) > 1e-9:
                        self.timing_errors.append('block %d g%s: nonzero gradient end not at block boundary' % (k, ax))
                pts[ax].append((np.asarray(tp) + t, np.asarray(gp, float)))
            if abs(dur / lim['block_raster_s'] - round(dur / lim['block_raster_s'])) > 1e-3:
                self.timing_errors.append('block %d duration not on block raster' % k)
            self.blocks.append(blk)
            t += dur
        self.total = t
        self.pwl = {}
        self.jumps = {}
        for ax in 'xyz':
            T = [0.0]; G = [0.0]; jumps = []
            ev = sorted(pts[ax], key=lambda q: q[0][0])
            for tp, gp in ev:
                tolj = lambda u, v: abs(u - v) > max(1e-3 * max(abs(u), abs(v)), 10.0)
                if tp[0] > T[-1] + 1e-12:
                    if tolj(G[-1], 0.0):
                        jumps.append((T[-1], G[-1], 0.0)); T.append(T[-1]); G.append(0.0)
                    T.append(tp[0]); G.append(0.0)
                if tolj(gp[0], G[-1]):
                    jumps.append((tp[0], G[-1], gp[0]))
                T += list(tp); G += list(gp)
            if abs(G[-1]) > 10.0:
                jumps.append((T[-1], G[-1], 0.0)); T.append(T[-1]); G.append(0.0)
            T.append(max(T[-1], t)); G.append(0.0)
            T = np.maximum.accumulate(np.asarray(T, float)); G = np.asarray(G, float)
            self.pwl[ax] = (T, G)
            self.jumps[ax] = jumps
        self._cum = {}
        for ax in 'xyz':
            T, G = self.pwl[ax]
            dT = np.diff(T)
            self._cum[ax] = np.concatenate([[0.0], np.cumsum(0.5 * (G[1:] + G[:-1]) * dT)])

    # exact quantities from the piecewise-linear waveforms ---------------------------------
    def grad(self, ax, t):
        T, G = self.pwl[ax]
        t = np.asarray(t, float)
        i = np.clip(np.searchsorted(T, t, side='right') - 1, 0, len(T) - 2)
        dT = T[i + 1] - T[i]
        f = np.where(dT > 0, (t - T[i]) / np.where(dT > 0, dT, 1), 0.0)
        return G[i] + f * (G[i + 1] - G[i])

    def moment0(self, ax, t):
        """integral of g_ax from 0 to t (cycles/m)."""
        T, G = self.pwl[ax]
        t = np.asarray(t, float)
        i = np.clip(np.searchsorted(T, t, side='right') - 1, 0, len(T) - 2)
        dt = np.clip(t - T[i], 0, None)
        dT = T[i + 1] - T[i]
        slope = np.where(dT > 0, (G[i + 1] - G[i]) / np.where(dT > 0, dT, 1), 0.0)
        return self._cum[ax][i] + G[i] * dt + 0.5 * slope * dt ** 2

    def M(self, t):
        return np.stack([self.moment0(a, t) for a in 'xyz'], axis=-1)

    def max_grad_slew(self):
        out = {}
        for ax in 'xyz':
            T, G = self.pwl[ax]
            dT = np.diff(T); dG = np.diff(G)
            ok = dT > 1e-10
            slew = np.abs(dG[ok] / dT[ok]) if ok.any() else np.zeros(1)
            zero_dt_jump = np.abs(dG[~ok]).max() if (~ok).any() else 0.0
            out[ax] = {'gmax': float(np.abs(G).max()), 'smax': float(slew.max()) if slew.size else 0.0,
                       'instant_jump': float(zero_dt_jump), 'n_boundary_jumps': len(self.jumps[ax])}
        return out

    def kspace(self, adc_list=None, classify=None, delay=0.0):
        """k (cycles/m) at every ADC sample.  classify(rf)->'exc'|'ref'|'inv'|'ignore'.
        delay>0 means gradients lag the ADC (true k at sample time t is k_nominal(t-delay))."""
        adc_list = self.adcs if adc_list is None else adc_list
        classify = classify or (lambda r: 'exc' if r['flip_deg'] < 100 else 'ref')
        events = [(r['t_center'], classify(r)) for r in self.rfs]
        events = [e for e in events if e[1] in ('exc', 'ref', 'inv')]
        events.sort()
        ev_t = np.array([e[0] for e in events]) if events else np.zeros(0)
        Mev = self.M(ev_t) if len(ev_t) else np.zeros((0, 3))
        # k just after each event
        k_after = np.zeros((len(events), 3)); kcur = np.zeros(3); tlast = None; Mlast = np.zeros(3); excited = False
        for j, (te, kind) in enumerate(events):
            if excited:
                kcur = kcur + (Mev[j] - Mlast)
            if kind == 'exc':
                kcur = np.zeros(3); excited = True
            else:
                kcur = -kcur
            k_after[j] = kcur; Mlast = Mev[j]
        out = []
        for a in adc_list:
            ts = a['times'] - delay
            j = np.searchsorted(ev_t, ts[0], side='right') - 1
            if j < 0:
                out.append(np.full((len(ts), 3), np.nan)); continue
            out.append(k_after[j] + self.M(ts) - Mev[j])
        return out

    def last_rf_before(self, t, kinds=None, classify=None):
        best = None
        for r in self.rfs:
            if r['t_center'] <= t and (kinds is None or classify(r) in kinds):
                best = r
        return best


def hardware_check(si, lim, tol=1.005):
    hs = si.max_grad_slew()
    gmax = lim['max_gradient_mT_per_m'] * 1e-3 * lim['gamma_Hz_per_T']
    smax = lim['max_slew_T_per_m_per_s'] * lim['gamma_Hz_per_T']
    bad = []
    for ax, v in hs.items():
        if v['gmax'] > gmax * tol:
            bad.append('%s: |g| %.2f mT/m > limit' % (ax, v['gmax'] / lim['gamma_Hz_per_T'] * 1e3))
        if v['smax'] > smax * tol:
            bad.append('%s: slew %.1f T/m/s > limit' % (ax, v['smax'] / lim['gamma_Hz_per_T']))
        if v['instant_jump'] > 1.0 or v['n_boundary_jumps']:
            bad.append('%s: discontinuous gradient (%d jumps)' % (ax, v['n_boundary_jumps']))
    det = {ax: {'max_mT_per_m': round(v['gmax'] / lim['gamma_Hz_per_T'] * 1e3, 3),
                'max_slew_T_per_m_per_s': round(v['smax'] / lim['gamma_Hz_per_T'], 2)} for ax, v in hs.items()}
    return (not bad), {'violations': bad, 'axes': det}


def timing_check(si, lim):
    bad = list(si.timing_errors)
    defs = si.definitions
    for key, lk in (('GradientRasterTime', 'gradient_raster_s'), ('RadiofrequencyRasterTime', 'rf_raster_s'),
                    ('AdcRasterTime', 'adc_raster_s'), ('BlockDurationRaster', 'block_raster_s')):
        if key in defs:
            v = defs[key]
            v = float(v[0] if isinstance(v, (list, tuple, np.ndarray)) else v)
            if abs(v - lim[lk]) > 1e-12:
                bad.append('definition %s=%g differs from %g' % (key, v, lim[lk]))
        else:
            bad.append('definition %s missing' % key)
    for r in si.rfs:
        dt = np.diff(r['t'])
        if len(dt) > 1 and np.any(np.abs(dt / lim['rf_raster_s'] - np.round(dt / lim['rf_raster_s'])) > 1e-3):
            bad.append('RF samples off RF raster in block %d' % r['block']); break
    return (not bad), {'violations': bad[:20], 'n_violations': len(bad)}


# ----------------------------------------------------------------------------- KomaMRI replay
def phantom_arrays(d):
    n = len(np.asarray(d['x']).ravel())
    out = {}
    for k in ('x', 'y', 'z'):
        out[k] = np.asarray(d.get(k, np.zeros(n)), float).ravel()
    out['rho'] = np.asarray(d.get('rho', d.get('density')), float).ravel()
    out['T1'] = np.asarray(d.get('T1', d.get('T1_s')), float).ravel()
    out['T2'] = np.asarray(d.get('T2', d.get('T2_s')), float).ravel()
    dw = d.get('dw_rad_s', None)
    if dw is None:
        dw = 2 * np.pi * np.asarray(d.get('B0_Hz', np.zeros(n)), float).ravel()
    out['dw'] = np.asarray(dw, float).ravel()
    return out


def koma_replay(seq_path, phantoms, workdir, adc_shift_s=0.0, dt_rf=1e-5, dt=1e-3, timeout=900, block_range=None):
    """Replay seq_path in KomaMRI for every phantom (list of dicts). Returns list of complex vectors."""
    workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)
    job = {'seq': str(seq_path), 'phantoms': [], 'out': str(workdir / 'replay_out.npz'), 'adc_shift_s': float(adc_shift_s),
           'dt_rf': dt_rf, 'dt': dt, 'block_range': block_range}
    for i, ph in enumerate(phantoms):
        p = workdir / ('replay_ph%d.npz' % i)
        np.savez(p, **phantom_arrays(ph))
        job['phantoms'].append(str(p))
    jp = workdir / 'replay_job.json'
    jp.write_text(json.dumps(job))
    env = dict(os.environ)
    env.update({'JULIA_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'PYTHON_JULIACALL_THREADS': '1',
                'JULIA_NUM_PRECOMPILE_TASKS': '1', 'PYTHON_JULIACALL_HANDLE_SIGNALS': 'yes'})
    t0 = time.time()
    r = subprocess.run([sys.executable, str(HERE / 'koma_replay.py'), str(jp)], capture_output=True, text=True,
                       timeout=timeout, env=env)
    (workdir / 'replay_log.txt').write_text(r.stdout[-4000:] + '\n---\n' + r.stderr[-8000:])
    if r.returncode != 0 or not Path(job['out']).exists():
        raise RuntimeError('KomaMRI replay failed: ' + r.stderr[-500:])
    z = np.load(job['out'])
    sigs = [z['sig%d' % i] for i in range(len(phantoms))]
    return sigs, time.time() - t0


# ----------------------------------------------------------------------------- entrypoint reruns
def python_candidates(ws):
    ws = Path(ws)
    c = [ws / '.venv/bin/python']
    try:
        for pat in ['*/bin/python', '*/*/bin/python']:
            for p in sorted(ws.glob(pat)):
                if p not in c:
                    c.append(p)
    except Exception:
        pass
    c = [p for p in c if p.exists()]
    c.append(Path(sys.executable))
    return c


def run_entry(python, script_src, input_src, workdir, input_name, output_name, extra_args=(), timeout=900):
    """Copy the standalone script and one input archive into a clean directory and run it."""
    workdir = Path(workdir)
    if workdir.exists():
        shutil.move(str(workdir), str(workdir) + '.old%d' % int(time.time() * 1000))
    workdir.mkdir(parents=True)
    shutil.copy2(script_src, workdir / Path(script_src).name)
    shutil.copy2(input_src, workdir / input_name)
    cmd = [str(python), Path(script_src).name, '--input', input_name, '--output', output_name] + list(extra_args)
    env = dict(os.environ)
    env.update({'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'MPLBACKEND': 'Agg'})
    try:
        r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout, env=env)
        rc, err = r.returncode, r.stderr[-1500:]
    except subprocess.TimeoutExpired:
        rc, err = -9, 'timeout'
    out = workdir / output_name
    return (rc == 0 and out.exists()), out, rc, err


def choose_python(ws, script_src, input_src, ev, input_name, output_name):
    trials = []
    if not (Path(script_src).exists() and Path(input_src).exists()):
        return None, trials
    for i, py in enumerate(python_candidates(ws)):
        ok, out, rc, err = run_entry(py, script_src, input_src, Path(ev) / ('probe-%d' % i), input_name, output_name)
        trials.append({'python': str(py), 'returncode': rc, 'stderr': err[-600:]})
        if ok:
            return py, trials
    return None, trials


def erode(mask, it=1):
    m = mask.copy()
    for _ in range(it):
        mm = m.copy()
        for ax in range(m.ndim):
            mm &= np.roll(m, 1, ax) & np.roll(m, -1, ax)
        m = mm
    return m


def label_interior(labels, k):
    """voxels of label k that do not touch another label (face neighbours)."""
    m = labels == k
    nb = np.ones_like(m)
    for ax in range(labels.ndim):
        for s in (1, -1):
            sh = np.roll(labels, s, ax)
            nb &= (sh == k)
    return m & nb

