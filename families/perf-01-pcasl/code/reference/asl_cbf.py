#!/usr/bin/env python3
"""pCASL CBF quantification (reference solution, heldout-v7-pcasl).

Usage: python asl_cbf.py --input-dir <dir with asl.npz m0.npz t1.npz acq.json> --output cbf.npz
White-paper single-compartment model with per-slice post-labeling delay, background-suppression
inversion efficiency folded into the labeling efficiency and saturation-recovery correction of M0.
"""
import argparse, json
from pathlib import Path
import numpy as np

USE_SLICE_TIMING = True
USE_BS_EFFICIENCY = True
USE_M0_TR_CORRECTION = True
USE_LABEL_EFFICIENCY = True
DECAY_T1 = 'blood'
LAMBDA_OVERRIDE = None
CONTROL_MINUS_LABEL = True
PAIR_STAT = 'mean'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    d = Path(a.input_dir)
    acq = json.loads((d / 'acq.json').read_text())
    asl = np.load(d / 'asl.npz')['asl'].astype(np.float64)
    m0 = np.load(d / 'm0.npz')['m0'].astype(np.float64)
    t1 = np.load(d / 't1.npz')['t1_s'].astype(np.float64)
    nz = asl.shape[1]
    first_ctrl = acq['first_volume'] == 'control'
    ctrl = asl[0::2] if first_ctrl else asl[1::2]
    lab = asl[1::2] if first_ctrl else asl[0::2]
    n = min(len(ctrl), len(lab))
    diff = ctrl[:n] - lab[:n]
    if not CONTROL_MINUS_LABEL:
        diff = -diff
    if PAIR_STAT == 'median':
        dm = np.median(diff, axis=0)
    elif PAIR_STAT == 'glm':
        y = np.concatenate([ctrl[:n], lab[:n]]).reshape(2 * n, -1)
        tt = np.concatenate([np.arange(n) * 2.0 + (0 if first_ctrl else 1), np.arange(n) * 2.0 + (1 if first_ctrl else 0)])
        X = np.stack([np.ones(2 * n), np.r_[np.ones(n) * 0.5, -np.ones(n) * 0.5], (tt - tt.mean()) / tt.std()], 1)
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        dm = b[1].reshape(asl.shape[1:])
    else:
        dm = diff.mean(0)
    if USE_M0_TR_CORRECTION:
        t1c = np.clip(t1, 0.05, None)
        m0 = m0 / (1 - np.exp(-acq['m0_tr_s'] / t1c))
    alpha = acq['labeling_efficiency'] if USE_LABEL_EFFICIENCY else 1.0
    if USE_BS_EFFICIENCY:
        alpha *= acq['bs_inversion_efficiency'] ** acq['n_bs_pulses']
    pld = np.full(nz, float(acq['pld_s']))
    if USE_SLICE_TIMING:
        for i, z in enumerate(acq['slice_order']):
            pld[z] = acq['pld_s'] + i * acq['slice_interval_s']
    T1b = acq['t1_blood_s']
    tau = acq['label_duration_s']
    lam = LAMBDA_OVERRIDE or acq['partition_coefficient_mL_per_g']
    if DECAY_T1 == 'blood':
        decay = np.exp(pld[:, None, None] / T1b) * np.ones_like(dm)
    else:
        decay = np.exp(pld[:, None, None] / np.clip(t1, 0.05, None))
    with np.errstate(divide='ignore', invalid='ignore'):
        cbf = 6000.0 * lam * dm * decay / (2 * alpha * T1b * m0 * (1 - np.exp(-tau / T1b)))
    mask = m0 > 0.2 * np.percentile(m0, 99)
    cbf = np.where(mask & np.isfinite(cbf), cbf, 0.0).astype(np.float32)
    np.savez_compressed(a.output, cbf=cbf, pld_by_slice_s=pld, alpha_effective=alpha)


if __name__ == '__main__':
    main()

