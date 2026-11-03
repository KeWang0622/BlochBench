#!/usr/bin/env python3
"""Validation-based comparison (downstream R2*/B0) and public-test reconstructions (reference).
Usage: python evaluate.py <inputs_dir> <outputs_dir>"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import common, predict, classical_recon
REPORT_SCALE = {'r2s': 1.0, 'b0': 1.0}

def summ(est, ref):
    er, eb = [], []
    for e, t in zip(est, ref):
        for k, v in t.items():
            if k in e:
                er.append(abs(e[k]['r2s_per_s'] / v['r2s_per_s'] - 1)); eb.append(abs(e[k]['b0_hz'] - v['b0_hz']))
    er, eb = np.array(er), np.array(eb)
    return {'r2s_rel_err_median': float(np.median(er)), 'r2s_rel_err_p90': float(np.percentile(er, 90)),
            'b0_abs_err_median_hz': float(np.median(eb)), 'b0_abs_err_p90_hz': float(np.percentile(eb, 90))}

def main(inp, outd):
    inp = Path(inp); outd = Path(outd); outd.mkdir(parents=True, exist_ok=True)
    split = json.loads((outd / 'split.json').read_text())
    tr = np.load(inp / 'train.npz'); te = tr['te_s']
    vi = np.where(np.isin(tr['subject_id'], split['validation_subjects']))[0]
    full = common.ifft2c(tr['kspace'][vi]); lab = tr['labels'][vi]
    m = common.make_masks(np.random.default_rng(12345), len(vi))
    vk = (tr['kspace'][vi] * m).astype(np.complex64)
    np.savez(outd / '_val_us.npz', kspace=vk, mask=m, labels=lab, te_s=te)
    ref = common.roi(full, te, lab)
    # classical tuning on half of the validation slices
    sub = np.arange(0, len(vi), 2); tun = {}
    np.savez(outd / '_val_sub.npz', kspace=vk[sub], mask=m[sub], labels=lab[sub], te_s=te)
    for lam in [0.01, 0.03, 0.1]:
        R = classical_recon.main(str(outd / '_val_sub.npz'), str(outd / '_tmp.npz'), lam)
        tun[lam] = summ(common.roi(R, te, lab[sub]), [ref[i] for i in sub])
    best = min(tun, key=lambda l: tun[l]['r2s_rel_err_median'] + tun[l]['r2s_rel_err_p90'])
    classical_recon.LAM = best
    s = (HERE / 'classical_recon.py').read_text().split('\n')
    s = [('LAM = %r   # tuned on validation subjects (downstream R2*/B0 error)' % best) if l.startswith('LAM = ') else l for l in s]
    (HERE / 'classical_recon.py').write_text('\n'.join(s))
    predict.main(str(outd / '_val_us.npz'), str(outd / '_val_learned.npz')); RL = np.load(outd / '_val_learned.npz')['recon']
    RC = classical_recon.main(str(outd / '_val_us.npz'), str(outd / '_val_classical.npz'), best)
    ZF = common.ifft2c(vk)
    val = {'subjects': split['validation_subjects'], 'n_slices': int(len(vi)), 'reference': 'ROI values of the fully sampled validation images',
           'learned': summ(common.roi(RL, te, lab), ref), 'classical': summ(common.roi(RC, te, lab), ref), 'zero_filled': summ(common.roi(ZF, te, lab), ref)}
    for k, R in [('learned', RL), ('classical', RC), ('zero_filled', ZF)]:
        val[k]['nrmse'] = float(np.linalg.norm(R - full) / np.linalg.norm(full))
    # public test
    t = np.load(inp / 'test.npz')
    predict.main(str(inp / 'test.npz'), str(outd / 'test_recon_learned.npz'))
    classical_recon.main(str(inp / 'test.npz'), str(outd / 'test_recon_classical.npz'), best)
    test = {}
    for meth in ['learned', 'classical']:
        R = np.load(outd / ('test_recon_' + meth + '.npz'))['recon']
        rv = common.roi(R, t['te_s'], t['labels'])
        for d in rv:
            for v in d.values():
                v['r2s_per_s'] *= REPORT_SCALE['r2s']; v['b0_hz'] *= REPORT_SCALE['b0']
        test[meth] = rv
    pref = 'learned' if val['learned']['r2s_rel_err_median'] <= val['classical']['r2s_rel_err_median'] else 'classical'
    out = {'validation': val, 'classical_tuning': {'parameter': 'group-sparsity weight lambda (relative to unit echo-1 peak)', 'values': [0.01, 0.03, 0.1], 'selected': best,
           'criterion': 'median + p90 relative R2* ROI error on validation slices', 'per_value': {str(k): v for k, v in tun.items()}},
           'test': test, 'preferred_method': pref, 'preferred_rationale': 'lower median R2* ROI error on validation subjects'}
    (outd / 'downstream_results.json').write_text(json.dumps(out, indent=1))
    for f in ['_val_us.npz', '_val_sub.npz', '_tmp.npz', '_val_learned.npz', '_val_classical.npz']:
        p = outd / f
        if p.exists():
            p.rename(outd / ('.' + f))
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        RLt = np.load(outd / 'test_recon_learned.npz')['recon']; RCt = np.load(outd / 'test_recon_classical.npz')['recon']; zf = common.ifft2c(t['kspace'])
        fig, ax = plt.subplots(2, 3, figsize=(10, 6))
        for j, (nm, R) in enumerate([('zero-filled', zf), ('learned', RLt), ('classical', RCt)]):
            r2, b0 = common.maps(R[:1], t['te_s'])
            ax[0, j].imshow(np.abs(R[0, 0]), cmap='gray'); ax[0, j].set_title(nm + ' |echo 1|')
            ax[1, j].imshow(r2[0], vmin=0, vmax=70); ax[1, j].set_title(nm + ' R2* (1/s)')
        fig.savefig(outd / 'comparison.png', dpi=80); plt.close(fig)
    except Exception as e:
        print('fig failed', e)
    return out

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])

