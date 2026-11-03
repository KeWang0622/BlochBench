#!/usr/bin/env python3
"""Train the reference learned reconstruction (small residual U-Net + data consistency) on CPU.
Usage: python train.py <train.npz> <outdir> [opts-json]"""
import json, sys, time
from pathlib import Path
import numpy as np, torch, torch.nn as nn
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import fft2c, ifft2c, make_masks
from net import Net, to_ch, from_ch, dc
torch.set_num_threads(1); torch.manual_seed(0)

def main(train_path, outdir, opts):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    d = np.load(train_path); K = d['kspace']; sid = d['subject_id']
    subs = sorted(set(sid.tolist())); val = subs[-6:]; trn = subs[:-6]
    if opts.get('split') == 'slice':  # (negative control) slice-level split
        rng0 = np.random.default_rng(1); idx = rng0.permutation(len(K)); vi = idx[:36]; ti = idx[36:]
        json.dump({'train_subjects': sorted(set(sid[ti].tolist())), 'validation_subjects': sorted(set(sid[vi].tolist())), 'split_level': 'slice'}, open(outdir / 'split.json', 'w'))
    else:
        ti = np.where(np.isin(sid, trn))[0]; vi = np.where(np.isin(sid, val))[0]
        json.dump({'train_subjects': trn, 'validation_subjects': val, 'split_level': 'subject'}, open(outdir / 'split.json', 'w'))
    img = ifft2c(K)
    cfg = {'base': opts.get('base', 24), 'per_echo_norm': opts.get('per_echo_norm', False), 'mag_only': opts.get('mag_only', False),
           'iters': opts.get('iters', 2), 'use_dc': opts.get('use_dc', True)}
    net = Net(**cfg)
    optim = torch.optim.Adam(net.parameters(), lr=2e-3)
    rng = np.random.default_rng(7); E = K.shape[1]; bs = 8; epochs = opts.get('epochs', 25)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=epochs)
    t0 = time.time(); best = (1e9, None); log = []
    vm = make_masks(np.random.default_rng(99), len(vi))
    for ep in range(epochs):
        net.train(); perm = rng.permutation(ti); tl = []
        for b in range(0, len(perm), bs):
            ii = perm[b:b + bs]; m = make_masks(rng, len(ii))
            ku = K[ii] * m; x = img[ii]
            out = net(torch.from_numpy(ku), torch.from_numpy(m))
            tgt = torch.from_numpy(x.astype(np.complex64))
            loss = (out - tgt).abs().mean() / tgt.abs().mean()
            optim.zero_grad(); loss.backward(); optim.step(); tl.append(loss.item())
        sched.step(); net.eval()
        with torch.no_grad():
            out = net(torch.from_numpy((K[vi] * vm).astype(np.complex64)), torch.from_numpy(vm)).numpy()
        vl = float(np.linalg.norm(out - img[vi]) / np.linalg.norm(img[vi]))
        log.append({'epoch': ep, 'train_loss': float(np.mean(tl)), 'val_nrmse': vl, 'time_s': time.time() - t0})
        print(log[-1], flush=True)
        if vl < best[0]:
            best = (vl, {k: v.clone() for k, v in net.state_dict().items()})
    torch.save({'state': best[1], 'cfg': cfg}, outdir / 'model.pt')
    json.dump(log, open(outdir / 'train_log.json', 'w'))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], (json.loads(Path(sys.argv[3]).read_text()) if Path(sys.argv[3]).exists() else json.loads(sys.argv[3])) if len(sys.argv) > 3 else {})

