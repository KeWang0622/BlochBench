#!/usr/bin/env python3
"""Generate public sample definitions and hidden samples for heldout-v5-safecpmg (fixed seeds)."""
import json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'; HID = HERE / 'hidden'
OBJ = {'n_isochromats': 2000, 'length_m': 0.012, 'axis': 'z',
       'positions': 'z_k = ((k + 0.5) / 2000 - 0.5) * 0.012 m, k = 0..1999; x = y = 0',
       'density': 'w_k = sin^2(pi * (k + 0.5) / 2000) normalised so that sum_k w_k = 1 (Hann-weighted sample profile); total M0 = 1',
       'B0_Hz': 0.0}
def main():
    PUB.mkdir(parents=True, exist_ok=True); HID.mkdir(parents=True, exist_ok=True)
    pub = [
        {'id': 'P1', 'T1_s': 0.95, 'T2_s': 0.048, 'B1_scale': 0.84},
        {'id': 'P2', 'T1_s': 1.40, 'T2_s': 0.072, 'B1_scale': 1.19},
        {'id': 'P3', 'T1_s': 0.70, 'T2_s': 0.098, 'B1_scale': 0.90},
        {'id': 'P4', 'T1_s': 1.80, 'T2_s': 0.140, 'B1_scale': 1.13},
        {'id': 'P5', 'T1_s': 1.15, 'T2_s': 0.190, 'B1_scale': 0.79},
        {'id': 'P6', 'T1_s': 2.00, 'T2_s': 0.265, 'B1_scale': 1.01},
    ]
    (PUB / 'samples.json').write_text(json.dumps({'object': OBJ, 'samples': pub}, indent=1) + '\n')
    rng = np.random.default_rng(81233)
    t2 = np.array([0.029, 0.039, 0.054, 0.076, 0.105, 0.150, 0.205, 0.290])
    b1 = np.array([1.20, 0.80, 1.10, 0.86, 1.21, 0.95, 0.79, 1.05])
    t1 = rng.uniform(0.4, 2.2, 8).round(3)
    hid = [{'id': 'H%d' % (i + 1), 'T1_s': float(t1[i]), 'T2_s': float(t2[i]), 'B1_scale': float(b1[i])} for i in range(8)]
    (HID / 'hidden_samples.json').write_text(json.dumps({'object': OBJ, 'samples': hid, 'noise_sigma': 0.0008, 'noise_seed': 5309}, indent=1) + '\n')
if __name__ == '__main__':
    main()

