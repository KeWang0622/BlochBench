"""Shared helpers for heldout-v7 graders (copied verbatim into every task's private folder)."""
import json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path
import numpy as np

ENV_NAMES = ('environment.txt', 'environment.json', 'environment.md', 'environment.yml', 'environment.yaml',
             'requirements.txt', 'pip-freeze.txt', 'pip_freeze.txt')


def chk(checks, name, ok, detail):
    try:
        json.dumps(detail)
    except Exception:
        detail = str(detail)
    checks[name] = {'pass': bool(ok), 'detail': detail}


def locate(ws, entry):
    """Deliverables live at the workspace root or in one subfolder."""
    ws = Path(ws)
    if (ws / entry).exists():
        return ws
    try:
        cands = sorted(p.parent for p in ws.glob('*/' + entry)
                       if not p.parent.name.startswith('.') and p.parent.name not in ('venv', 'env'))
        if cands:
            return cands[0]
        for p in sorted(ws.glob('*/report.json')):
            if not p.parent.name.startswith('.'):
                return p.parent
    except Exception:
        pass
    return ws


def python_candidates(ws):
    ws = Path(ws)
    out = [ws / '.venv/bin/python']
    try:
        for pat in ('*/bin/python', '*/*/bin/python'):
            for p in sorted(ws.glob(pat)):
                if p not in out:
                    out.append(p)
    except Exception:
        pass
    return [p for p in out if p.exists()]


def _env():
    e = dict(os.environ)
    for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        e[k] = '1'
    e['MPLBACKEND'] = 'Agg'
    e.pop('PYTHONPATH', None)
    return e


def run_entry(py, entry_src, input_dir, workdir, out_name='output.npz', timeout=900):
    """Copy the standalone entrypoint and the inputs into a clean directory and run it."""
    workdir = Path(workdir)
    k = 0
    base = workdir
    while workdir.exists():
        k += 1
        workdir = Path(str(base) + f'-{k}')
    workdir.mkdir(parents=True)
    rec = {'python': str(py), 'workdir': str(workdir)}
    try:
        shutil.copy2(entry_src, workdir / Path(entry_src).name)
        shutil.copytree(input_dir, workdir / 'inputs')
    except Exception as e:
        rec.update(returncode=-2, stderr='copy failed: ' + repr(e), output=None)
        return rec
    cmd = [str(py), Path(entry_src).name, '--input-dir', 'inputs', '--output', out_name]
    t = time.time()
    try:
        r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout, env=_env())
        rec.update(returncode=r.returncode, stderr=r.stderr[-1500:])
    except subprocess.TimeoutExpired:
        rec.update(returncode=-9, stderr=f'timeout after {timeout} s')
    except Exception as e:
        rec.update(returncode=-1, stderr=repr(e))
    rec['seconds'] = round(time.time() - t, 1)
    o = workdir / out_name
    rec['output'] = str(o) if (rec['returncode'] == 0 and o.exists()) else None
    return rec


def pick_python(ws, entry_src, pub_inputs, ev, out_name='output.npz', timeout=900):
    """Workspace interpreters first (.venv first); the grader interpreter only as a last resort."""
    trials = []
    if entry_src is None or not Path(entry_src).exists():
        return None, None, trials
    cands = python_candidates(ws) + [Path(sys.executable)]
    for i, py in enumerate(cands):
        rec = run_entry(py, entry_src, pub_inputs, Path(ev) / f'probe-{i}', out_name, timeout)
        rec['fallback_grader_python'] = (Path(py) == Path(sys.executable))
        trials.append(rec)
        if rec['output']:
            return py, rec, trials
    return None, None, trials


def load_npz(path):
    try:
        with np.load(path, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}
    except Exception:
        return None


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def get_arr(d, key, shape=None, complex_ok=False):
    if d is None or key not in d:
        return None, f'missing key {key}'
    a = np.asarray(d[key])
    if not complex_ok and np.iscomplexobj(a):
        a = np.real(a)
    try:
        a = a.astype(complex if (complex_ok and np.iscomplexobj(a)) else float)
    except Exception:
        return None, f'{key} not numeric'
    if shape is not None and tuple(a.shape) != tuple(shape):
        return None, f'{key} shape {a.shape} != {tuple(shape)}'
    return a, 'ok'


def docs_checks(checks, src, required_files, report_keys):
    src = Path(src)
    missing = [f for f in required_files if not (src / f).exists()]
    chk(checks, 'deliverables_present', not missing, {'folder': str(src), 'missing': missing})
    rep = load_json(src / 'report.json')
    if not isinstance(rep, dict):
        chk(checks, 'report_schema', False, 'report.json missing or not a JSON object')
    else:
        miss = [k for k in report_keys if k not in rep]
        lim = rep.get('limitations')
        ok = (not miss) and isinstance(lim, list) and len(lim) > 0
        chk(checks, 'report_schema', ok, {'missing_keys': miss, 'limitations_nonempty_list': isinstance(lim, list) and len(lim) > 0})
    try:
        envs = [p.name for p in src.iterdir() if p.is_file() and (p.name.lower() in ENV_NAMES)]
    except Exception:
        envs = []
    chk(checks, 'environment_record', bool(envs), envs or 'no environment record found')
    try:
        txt = (src / 'README.md').read_text(errors='ignore').lower()
        ok = ('validat' in txt) and ('limitation' in txt)
        chk(checks, 'readme_validation_limitations', ok, 'README.md mentions validation and limitations' if ok else 'README.md must describe validation evidence and limitations')
    except Exception:
        chk(checks, 'readme_validation_limitations', False, 'README.md missing')
    return rep


def finish(checks, extra=None):
    g = {'all_automated_checks_pass': bool(checks) and all(v['pass'] for v in checks.values()), 'checks': checks}
    if extra:
        g.update(extra)
    return g


def arm_main(grade_fn):
    if len(sys.argv) < 3:
        print('usage: grade_<slug>_arm.py <workspace_dir> <eval_dir>')
        sys.exit(2)
    ws = Path(sys.argv[1]).resolve()
    ev = Path(sys.argv[2]).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    try:
        g = grade_fn(ws, ev)
    except Exception:
        g = {'all_automated_checks_pass': False,
             'checks': {'grader_internal_error': {'pass': False, 'detail': traceback.format_exc()[-2000:]}}}
    (ev / 'grade.json').write_text(json.dumps(g, indent=1, default=str) + '\n')
    print(json.dumps({'pass': g['all_automated_checks_pass'], 'failed': [k for k, v in g['checks'].items() if not v['pass']]}))

