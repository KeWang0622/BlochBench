#!/usr/bin/env python3
"""Reference solution for heldout-v5-t2study; builds a complete mock workspace.
Usage: python reference_solution.py [ws_dir] [variant]"""
import csv, json, platform, shutil, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; TASK = HERE.parent; PY = sys.executable
GRAPPA = r'''
def grappa_recon(kw, mask, lam=1e-3):
    E, C, N, _ = kw.shape
    acq = np.where(mask)[0]
    c = N // 2; nacs = 0
    while c - nacs - 1 >= 0 and mask[c - nacs - 1] and mask[c + nacs]:
        nacs += 1
    acs = np.arange(c - nacs, c + nacs)
    R = int(np.min(np.diff(acq[(acq < c - nacs) | (acq >= c + nacs)])))
    out = np.zeros_like(kw)
    for e in range(E):
        k = kw[e]; kf = k.copy()
        for j in range(1, R):
            S = []; Tg = []
            for kp in acs:
                if kp + R in acs and kp + j in acs:
                    for x in range(1, N - 1):
                        S.append(np.concatenate([k[:, kp, x - 1:x + 2].ravel(), k[:, kp + R, x - 1:x + 2].ravel()]))
                        Tg.append(k[:, kp + j, x])
            S = np.array(S); Tg = np.array(Tg)
            AhA = S.conj().T @ S; Wt = np.linalg.solve(AhA + lam * np.trace(AhA).real / AhA.shape[0] * np.eye(AhA.shape[0]), S.conj().T @ Tg)
            for ky in range(N):
                if mask[ky]:
                    continue
                prev = acq[acq < ky]
                if len(prev) == 0 or ky - prev[-1] != j or prev[-1] + R >= N or not mask[prev[-1] + R]:
                    continue
                kp = prev[-1]
                src = np.stack([np.concatenate([k[:, kp, max(x - 1, 0):x + 2].ravel() if 0 < x < N - 1 else np.zeros(3 * C),
                                                k[:, kp + R, max(x - 1, 0):x + 2].ravel() if 0 < x < N - 1 else np.zeros(3 * C)]) for x in range(N)])
                kf[:, ky, :] = (src @ Wt).T
        out[e] = kf
    return out
'''

def run(cmd, cwd):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(' '.join(map(str, cmd)) + '\n' + r.stderr[-2000:])
    return r.stdout

def patch_map(src, variant):
    if variant == 'fft_shift':
        src = src.replace("    mag = np.abs(imgs)\n", "    mag = np.abs(np.roll(imgs, (imgs.shape[-2] // 2, imgs.shape[-1] // 2), axis=(-2, -1)))\n")
    if variant == 'te_seconds':
        src = src.replace("    te = np.asarray(d['echo_times_ms'], float)", "    te = np.asarray(d['echo_times_ms'], float) / 1000.0")
        src = src.replace("r2 = np.clip(p[1], 1e-4, 1.0)", "r2 = np.clip(p[1], 1e-1, 1e3)").replace("r2 = np.clip(r2 + dr2, 1e-4, 1.0)", "r2 = np.clip(r2 + dr2, 1e-1, 1e3)")
    if variant == 'lowres_sens':
        src = src.replace("default=os.environ.get('T2MAP_METHOD', 'espirit')", "default='lowres'")
    if variant == 'zero_filled':
        src = src.replace("    imgs, mps = recon_echoes(ksp, mask, noise, a.method)\n",
                          "    imgs = np.sqrt((np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(ksp, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))) ** 2).sum(1))\n")
    if variant == 'grappa_rss_naive':
        src = patch_map(src, 'grappa_rss')
        src = src.replace("kw = np.einsum('ij,ejyx->eiyx', np.linalg.inv(np.linalg.cholesky(psi)), ksp)", "kw = ksp")
        src = src.replace("    w = y ** 2\n", "    w = np.ones_like(y)\n")
        return src
    if variant == 'grappa_rss':
        src = src.replace("def fit_t2(", GRAPPA + "\ndef fit_t2(")
        src = src.replace("    imgs, mps = recon_echoes(ksp, mask, noise, a.method)\n", """    psi = noise.conj().T @ noise / noise.shape[0]
    kw = np.einsum('ij,ejyx->eiyx', np.linalg.inv(np.linalg.cholesky(psi)), ksp)
    kf = grappa_recon(kw, mask)
    coil = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kf, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))
    imgs = np.sqrt((np.abs(coil) ** 2).sum(1)).astype(np.complex64)
""")
        # weighted log-linear fit only (no Gauss-Newton refinement)
        src = src.replace("    for _ in range(30):                          # Gauss-Newton", "    for _ in range(0):                          # Gauss-Newton")
    return src

def patch_stats(src, variant):
    if variant == 'scans_as_units':
        src = src.replace("    m = {g: np.array([np.mean(list(s['vals'].values())) for s in subj.values() if s['group'] == g]) for g in ('control', 'patient')}",
                          "    m = {g: np.array([v for s in subj.values() if s['group'] == g for v in s['vals'].values()]) for g in ('control', 'patient')}")
    if variant == 'student_t':
        src = src.replace("    se = np.sqrt(v1 / n1 + v2 / n2)\n    df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))",
                          "    spp = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)\n    se = np.sqrt(spp * (1 / n1 + 1 / n2))\n    df = n1 + n2 - 2")
    if variant == 'cohen_d':
        src = src.replace(" * (1 - 3 / (4 * (n1 + n2) - 9))", "")
    if variant == 'wsd_no_sqrt2':
        src = src.replace("wsd = np.sqrt(np.mean(d ** 2) / 2)", "wsd = np.std(d, ddof=1)")
    if variant == 'drop_incomplete':
        src = src.replace("    m = {g: np.array([np.mean(list(s['vals'].values())) for s in subj.values() if s['group'] == g]) for g in ('control', 'patient')}",
                          "    m = {g: np.array([np.mean(list(s['vals'].values())) for s in subj.values() if s['group'] == g and len(s['vals']) == 2]) for g in ('control', 'patient')}")
    if variant == 'sign_flip':
        src = src.replace("    diff = p.mean() - c.mean()", "    diff = c.mean() - p.mean()")
    return src

def make_workspace(ws, variant='ref'):
    ws = Path(ws).resolve(); ws.mkdir(parents=True, exist_ok=True)
    (ws / 't2maps').mkdir(exist_ok=True)
    (ws / 'map_t2.py').write_text(patch_map((HERE / 'refsol/map_t2.py').read_text(), variant))
    (ws / 'study_stats.py').write_text(patch_stats((HERE / 'refsol/study_stats.py').read_text(), variant))
    inp = TASK / 'public/inputs'
    parts = {r['subject_id']: r for r in csv.DictReader(open(inp / 'participants.tsv'), delimiter='\t')}
    rows = []
    STATS_ONLY = ('scans_as_units', 'student_t', 'cohen_d', 'wsd_no_sqrt2', 'drop_incomplete', 'sign_flip')
    refws = HERE / 'validation/ws_ref'
    if variant in STATS_ONLY and (refws / 'roi_t2_by_scan.csv').exists():
        for f in (refws / 't2maps').glob('*.npz'):
            shutil.copy2(f, ws / 't2maps' / f.name)
        rows = [dict(r) for r in csv.DictReader(open(refws / 'roi_t2_by_scan.csv'))]
    for f in ([] if rows else sorted((inp / 'scans').glob('*.npz'))):
        sid, ses = f.stem.split('_ses-')
        out = ws / 't2maps' / f'{f.stem}.npz'
        run([PY, 'map_t2.py', '--input', f, '--output', out], ws)
        val = float(np.load(out)['roi_mean_t2_ms'])
        if variant == 'ses1_label' and ses == '2' and (inp / 'scans' / f'{sid}_ses-1.npz').exists():
            lab1 = np.load(inp / 'scans' / f'{sid}_ses-1.npz')['labels']
            val = float(np.nanmean(np.load(out)['t2_ms'][lab1 == 1]))
        if variant == 'te_seconds':
            pass
        rows.append(dict(subject_id=sid, group=parts[sid]['group'], session=int(ses), roi_t2_ms=round(val, 6)))
    with open(ws / 'roi_t2_by_scan.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['subject_id', 'group', 'session', 'roi_t2_ms']); w.writeheader(); [w.writerow(r) for r in rows]
    run([PY, 'study_stats.py', '--input', 'roi_t2_by_scan.csv', '--output', 'study_stats.json'], ws)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    st = json.loads((ws / 'study_stats.json').read_text())
    fig, ax = plt.subplots(figsize=(4, 4))
    for i, g in enumerate(['control', 'patient']):
        v = [r['roi_t2_ms'] for r in rows if r['group'] == g]; ax.plot(np.full(len(v), i) + np.random.default_rng(i).uniform(-.1, .1, len(v)), v, 'o')
    ax.set_xticks([0, 1]); ax.set_xticklabels(['control', 'patient']); ax.set_ylabel('ROI T2 (ms)')
    fig.savefig(ws / 'summary.png', dpi=80); plt.close(fig)
    rep = dict(scope='simulated multi-subject T2 study', reconstruction_method='prewhitened ESPIRiT CG-SENSE', fit_model='mono-exponential magnitude',
               unit_of_analysis='subject', primary_result=f"difference {st['difference_ms']:.2f} ms, p={st['p_value_two_sided']:.4f}",
               software=dict(python=platform.python_version(), numpy=np.__version__), validation_summary='reference', limitations=['simulated data'])
    (ws / 'report.json').write_text(json.dumps(rep, indent=1))
    (ws / 'README.md').write_text('# reference\n')
    (ws / 'environment.txt').write_text(run([PY, '-m', 'pip', 'freeze'], ws))
    return st

if __name__ == '__main__':
    ws = sys.argv[1] if len(sys.argv) > 1 else str(HERE / 'validation/ws_ref')
    v = sys.argv[2] if len(sys.argv) > 2 else 'ref'
    print(json.dumps(make_workspace(ws, v), indent=1))

