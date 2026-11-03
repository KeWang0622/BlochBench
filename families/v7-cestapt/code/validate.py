#!/usr/bin/env python3
"""Author validation for heldout-v7-cestapt."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _v7build import run_all


def report_fn(out):
    d = np.load(out)
    t = np.load(HERE / 'truth' / 'public_truth.npz')
    lab = t['labels']
    return {'scope': 'APT CEST asymmetry', 'b0_method': 'WASSR', 'normalisation': 'S0',
            'roi_mtrasym_percent': {str(l): float(np.median(d['mtr_asym_3p5_percent'][lab == l])) for l in range(1, 6)},
            'software': {'numpy': np.__version__}, 'validation_summary': 'author control', 'limitations': ['synthetic']}


S = lambda a, b: (a, b)
T3 = ['public_mtrasym_rois', 'public_mtrasym_voxelwise', 'hidden_case1_mtrasym_rois', 'hidden_case1_mtrasym_voxelwise', 'hidden_case2_mtrasym_rois', 'hidden_case2_mtrasym_voxelwise']
CONTROLS = [
    dict(name='reference', kind='positive', subs=[]),
    dict(name='pos_lorentz_wassr_linear', kind='positive', subs=[S("B0_METHOD = 'spline_min'", "B0_METHOD = 'lorentz'"), S("INTERP = 'spline'", "INTERP = 'linear'")], desc='Lorentzian WASSR fit and linear interpolation'),
    dict(name='pos_parabola_wassr', kind='positive', subs=[S("B0_METHOD = 'spline_min'", "B0_METHOD = 'parabola'")], desc='three-point parabolic WASSR minimum'),
    dict(name='neg_no_b0', kind='negative', domain=True, subs=[S('USE_B0 = True', 'USE_B0 = False')], targets=T3, desc='no B0 correction of the Z-spectrum'),
    dict(name='neg_b0_wrong_sign', kind='negative', domain=True, subs=[S('B0_SIGN = 1.0', 'B0_SIGN = -1.0')], targets=T3, desc='B0 shift applied in the wrong direction'),
    dict(name='neg_wassr_hz_as_ppm', kind='negative', domain=True, subs=[S('WASSR_IN_PPM_ALREADY = False', 'WASSR_IN_PPM_ALREADY = True')], targets=T3 + ['public_b0_map'], desc='WASSR offsets in Hz used as ppm'),
    dict(name='neg_norm_far_offset', kind='negative', domain=True, subs=[S("NORMALISE = 's0'", "NORMALISE = 'far'")], targets=T3, desc='Z normalised by the most negative saturated image instead of the unsaturated S0'),
    dict(name='neg_assume_sorted', kind='negative', subs=[S('TRUST_STORED_ORDER = True', 'TRUST_STORED_ORDER = False')], targets=T3, desc='images assumed stored in ascending offset order'),
    dict(name='neg_asym_sign', kind='negative', subs=[S('ASYM_SIGN = 1.0', 'ASYM_SIGN = -1.0')], targets=T3, desc='Z(+3.5) - Z(-3.5)'),
]

if __name__ == '__main__':
    run_all(HERE, 'cest_apt.py', 'apt.npz', report_fn, CONTROLS, HERE / 'grade_cestapt_arm.py', sys.argv[1:] or None)

