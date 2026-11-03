#!/usr/bin/env python3
"""Reference CPMG T2 mapping with an extended-phase-graph (EPG) model (heldout-v4-t2epg).
python fit_t2.py --input-dir <dir> --output-dir <dir>"""
import argparse, json
from pathlib import Path
import numpy as np
import nibabel as nib

METHOD = 'dictionary'   # dictionary | dictionary_truncated | gauss_newton
MISTAKE = None


def rot(alpha, phi):
    c2 = np.cos(alpha / 2) ** 2; s2 = np.sin(alpha / 2) ** 2; s = np.sin(alpha); c = np.cos(alpha)
    e1 = np.exp(1j * phi); e2 = np.exp(2j * phi)
    T = np.empty(alpha.shape + (3, 3), complex)
    T[..., 0, 0] = c2; T[..., 0, 1] = e2 * s2; T[..., 0, 2] = -1j * e1 * s
    T[..., 1, 0] = np.conj(e2) * s2; T[..., 1, 1] = c2; T[..., 1, 2] = 1j * np.conj(e1) * s
    T[..., 2, 0] = -0.5j * np.conj(e1) * s; T[..., 2, 1] = 0.5j * e1 * s; T[..., 2, 2] = c
    return T


def epg(T2, B1, T1, esp, n, refoc_deg):
    T2, B1 = np.broadcast_arrays(np.atleast_1d(T2).astype(float), np.atleast_1d(B1).astype(float))
    T2 = T2.ravel(); B1 = B1.ravel(); V = T2.size; ns = 2 * n + 3
    F = np.zeros((V, 3, ns), complex); F[:, 2, 0] = 1
    exc_phase = 0.0 if MISTAKE == 'cp_phase' else np.pi / 2
    Te = rot(np.pi / 2 * B1, exc_phase); Tr = rot(np.deg2rad(refoc_deg) * B1, 0.0)
    tau = esp if MISTAKE == 'esp_full_each_half' else esp / 2
    E2 = np.exp(-tau / T2)[:, None]; E1 = np.exp(-tau / T1)
    F = np.einsum('vij,vjs->vis', Te, F)
    out = np.zeros((V, n))
    for k in range(n):
        for half in (0, 1):
            F[:, 0:2] *= E2[:, None]; F[:, 2] *= E1; F[:, 2, 0] += 1 - E1
            Fp = np.roll(F[:, 0], 1, axis=1); Fm = np.roll(F[:, 1], -1, axis=1); Fm[:, -1] = 0; Fp[:, 0] = np.conj(Fm[:, 0])
            F[:, 0] = Fp; F[:, 1] = Fm
            if half == 0:
                F = np.einsum('vij,vjs->vis', Tr, F)
        out[:, k] = np.abs(F[:, 0, 0])
    return out


def monoexp(Y, te, skip):
    Y = Y[:, skip:]; te = te[skip:]
    T2 = np.zeros(len(Y)); M0 = np.zeros(len(Y))
    from scipy.optimize import curve_fit
    L = np.log(np.maximum(Y, 1e-6)); w = np.maximum(Y, 1e-6) ** 2
    A = np.stack([np.ones_like(te), -te], 1)
    for i in range(len(Y)):
        Aw = A * np.sqrt(w[i])[:, None]; c = np.linalg.lstsq(Aw, L[i] * np.sqrt(w[i]), rcond=None)[0]
        T2[i] = 1 / max(c[1], 1e-6); M0[i] = np.exp(c[0])
    return T2, np.ones(len(Y)), M0


def dictionary_fit(Y, T1, esp, n, refoc, w=None):
    t2g = np.geomspace(0.008, 1.2, 420); b1g = np.round(np.arange(0.40, 1.2001, 0.005), 4)
    Yn = Y / np.maximum(np.linalg.norm(Y if w is None else Y * w, axis=1, keepdims=True), 1e-12)
    best = np.full(len(Y), -np.inf); bt2 = np.zeros(len(Y)); bb1 = np.zeros(len(Y)); bm0 = np.zeros(len(Y))
    for b1 in b1g:
        D = epg(t2g, np.full_like(t2g, b1), T1, esp, n, refoc)
        Dn = D / np.linalg.norm(D, axis=1, keepdims=True)
        if w is None:
            S = Yn @ Dn.T
        else:
            S = np.einsum('ve,te->vt', Yn * w, Dn) / np.sqrt(np.einsum('ve,te->vt', w ** 2 * 0 + w, Dn ** 2))
        j = S.argmax(1); s = S[np.arange(len(Y)), j]; upd = s > best
        best[upd] = s[upd]; bt2[upd] = t2g[j[upd]]; bb1[upd] = b1
    Dbest = epg(bt2, bb1, T1, esp, n, refoc)
    m0 = np.sum(Dbest * Y, 1) / np.maximum(np.sum(Dbest ** 2, 1), 1e-12)
    return bt2, bb1, m0


def truncated_fit(Y, T1, esp, n, refoc, noise):
    t2g = np.geomspace(0.008, 1.2, 420); b1g = np.round(np.arange(0.40, 1.2001, 0.005), 4)
    W = (Y > 4 * noise).astype(float); W[:, :4] = 1
    best = np.full(len(Y), -np.inf); bt2 = np.zeros(len(Y)); bb1 = np.zeros(len(Y))
    Yw = Y * W; ny = np.sum(Yw ** 2, 1)
    for b1 in b1g:
        D = epg(t2g, np.full_like(t2g, b1), T1, esp, n, refoc)
        num = Yw @ D.T; den = W @ (D ** 2).T
        S = num ** 2 / np.maximum(den, 1e-12)          # explained energy with free M0 on unmasked echoes
        j = S.argmax(1); s = S[np.arange(len(Y)), j]; upd = s > best
        best[upd] = s[upd]; bt2[upd] = t2g[j[upd]]; bb1[upd] = b1
    Dbest = epg(bt2, bb1, T1, esp, n, refoc)
    m0 = np.sum(Dbest * Yw, 1) / np.maximum(np.sum(Dbest ** 2 * W, 1), 1e-12)
    return bt2, bb1, m0


def gauss_newton(Y, T1, esp, n, refoc):
    # coarse grid start, then vectorised Gauss-Newton on (log T2, B1) with M0 eliminated
    t2g = np.geomspace(0.01, 1.0, 60); b1g = np.arange(0.4, 1.21, 0.04)
    Yn = Y / np.linalg.norm(Y, axis=1, keepdims=True); best = np.full(len(Y), -np.inf); lt = np.zeros(len(Y)); b = np.zeros(len(Y))
    for b1 in b1g:
        D = epg(t2g, np.full_like(t2g, b1), T1, esp, n, refoc); S = Yn @ (D / np.linalg.norm(D, axis=1, keepdims=True)).T
        j = S.argmax(1); s = S[np.arange(len(Y)), j]; u = s > best; best[u] = s[u]; lt[u] = np.log(t2g[j[u]]); b[u] = b1

    def resid(lt, b):
        D = epg(np.exp(lt), np.clip(b, 0.3, 1.3), T1, esp, n, refoc)
        m0 = np.sum(D * Y, 1) / np.maximum(np.sum(D * D, 1), 1e-12)
        return Y - m0[:, None] * D, m0
    for it in range(12):
        r0, _ = resid(lt, b); h = 1e-4
        J1 = (resid(lt + h, b)[0] - r0) / h; J2 = (resid(lt, b + h)[0] - r0) / h
        a11 = np.sum(J1 * J1, 1); a12 = np.sum(J1 * J2, 1); a22 = np.sum(J2 * J2, 1)
        g1 = np.sum(J1 * r0, 1); g2 = np.sum(J2 * r0, 1); lam = 1e-6 * (a11 + a22)
        det = (a11 + lam) * (a22 + lam) - a12 ** 2
        d1 = -((a22 + lam) * g1 - a12 * g2) / det; d2 = -((a11 + lam) * g2 - a12 * g1) / det
        lt = lt + np.clip(d1, -0.3, 0.3); b = np.clip(b + np.clip(d2, -0.1, 0.1), 0.3, 1.25)
    _, m0 = resid(lt, b)
    return np.exp(lt), b, m0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--input-dir', required=True); ap.add_argument('--output-dir', required=True)
    a = ap.parse_args(); ind = Path(a.input_dir); out = Path(a.output_dir); out.mkdir(parents=True, exist_ok=True)
    img = nib.load(str(ind / 'mese.nii.gz')); data = np.asarray(img.dataobj, float)
    lab = np.asarray(nib.load(str(ind / 'labels.nii.gz')).dataobj).astype(int)
    acq = json.loads((ind / 'acquisition.json').read_text())
    n = data.shape[-1]; esp = float(acq['EchoSpacing_s']); refoc = float(acq['RefocusingFlipAngle_deg']); T1 = float(acq.get('AssumedT1_s', 1.0))
    if MISTAKE == 'hardcoded_protocol':
        esp, refoc = 0.0095, 165.0
    te = esp * np.arange(1, n + 1)
    s0 = data[..., 0]; mask = s0 > 0.05 * np.percentile(s0, 99)
    Y = data[mask]
    if MISTAKE in ('monoexp_all', 'monoexp_skip_first'):
        T2, B1, M0 = monoexp(Y, te, 1 if MISTAKE == 'monoexp_skip_first' else 0)
    elif MISTAKE == 'epg_b1_fixed':
        t2g = np.geomspace(0.008, 1.2, 420); D = epg(t2g, np.ones_like(t2g), T1, esp, n, refoc)
        S = (Y / np.linalg.norm(Y, axis=1, keepdims=True)) @ (D / np.linalg.norm(D, axis=1, keepdims=True)).T
        T2 = t2g[S.argmax(1)]; B1 = np.ones(len(Y)); M0 = Y[:, 0]
    elif METHOD == 'dictionary_truncated':
        noise = np.median(data[~mask][:, -1]) / 1.2533 if np.any(~mask) else 1.0
        T2, B1, M0 = truncated_fit(Y, T1, esp, n, refoc, noise)
    elif METHOD == 'gauss_newton':
        T2, B1, M0 = gauss_newton(Y, T1, esp, n, refoc)
    else:
        T2, B1, M0 = dictionary_fit(Y, T1, esp, n, refoc)
    maps = {}
    for name, v in [('t2_map', T2), ('b1_map', B1), ('m0_map', M0)]:
        m = np.zeros(mask.shape, np.float32); m[mask] = v; maps[name] = m
        nib.save(nib.Nifti1Image(m, img.affine), str(out / (name + '.nii.gz')))
    roi = {str(k): float(np.mean(maps['t2_map'][lab == k])) for k in sorted(set(np.unique(lab)) - {0})}
    (out / 'roi_t2.json').write_text(json.dumps({'label_mean_T2_s': roi, 'model': 'EPG CPMG, free T2, B1 and M0', 'assumed_T1_s': T1}, indent=1) + '\n')
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        z = mask.shape[2] // 2; fig, ax = plt.subplots(1, 2, figsize=(8, 4))
        ax[0].imshow(maps['t2_map'][:, :, z].T * 1e3, origin='lower', vmin=0, vmax=200); ax[0].set_title('T2 (ms)')
        ax[1].imshow(maps['b1_map'][:, :, z].T, origin='lower', vmin=0.4, vmax=1.2); ax[1].set_title('B1+ scale')
        fig.savefig(out / 't2_b1_maps.png', dpi=80); plt.close(fig)
    except Exception:
        pass


if __name__ == '__main__':
    main()

