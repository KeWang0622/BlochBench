#!/usr/bin/env python3
"""Author validation for heldout-v7-epidti."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _v7build import run_all


def report_fn(out):
    return {'scope': 'EPI DTI from raw k-space', 'ghost_correction': '3-line navigator', 'distortion_correction': 'field map', 'gradient_nonlinearity': 'per-voxel L',
            'tensor_fit': 'WLS', 'software': {'numpy': np.__version__}, 'validation_summary': 'author control', 'limitations': ['synthetic']}


S = lambda a, b: (a, b)
G3 = ['public_geometry', 'hidden_case1_geometry', 'hidden_case2_geometry']
CONTROLS = [
    dict(name='reference', kind='positive', subs=[]),
    dict(name='pos_model_based_unwarp', kind='positive', subs=[S("UNWARP = 'pixel_shift'", "UNWARP = 'model'")], desc='regularised model-based inversion of the off-resonance encoding per column'),
    dict(name='pos_pooled_navigator_ols', kind='positive', subs=[S('GHOST_POOL = False', 'GHOST_POOL = True'), S("FIT = 'wls'", "FIT = 'ols'")], desc='navigator phase pooled over volumes; unweighted log-linear tensor fit'),
    dict(name='neg_no_ghost_correction', kind='negative', domain=True, subs=[S('GHOST_CORRECTION = True', 'GHOST_CORRECTION = False')], targets=['public_nyquist_ghost', 'hidden_case1_nyquist_ghost', 'hidden_case2_nyquist_ghost'], desc='navigators ignored'),
    dict(name='neg_ghost_constant_phase_only', kind='negative', domain=True, subs=[S('GHOST_LINEAR = True', 'GHOST_LINEAR = False')], targets=['public_nyquist_ghost', 'hidden_case1_nyquist_ghost', 'hidden_case2_nyquist_ghost'], desc='only a constant odd/even phase removed (echo shift ignored)'),
    dict(name='neg_no_distortion_correction', kind='negative', domain=True, subs=[S('DISTORTION_CORRECTION = True', 'DISTORTION_CORRECTION = False')], targets=G3, desc='field map not used'),
    dict(name='neg_distortion_wrong_sign', kind='negative', domain=True, subs=[S('DISTORTION_SIGN = 1.0', 'DISTORTION_SIGN = -1.0')], targets=G3, desc='displacement applied in the wrong direction'),
    dict(name='neg_ignore_blip_polarity', kind='negative', domain=True, subs=[S('PE_SIGN_OVERRIDE = None', 'PE_SIGN_OVERRIDE = 1')], targets=['hidden_case1_geometry'], desc='phase-encoding polarity assumed positive'),
    dict(name='neg_no_gradient_nonlinearity', kind='negative', domain=True, subs=[S("GNL_CORRECTION = 'full'", "GNL_CORRECTION = 'none'")], targets=['public_fa_md_rois', 'hidden_case1_fa_md_rois', 'hidden_case2_fa_md_rois'], desc='nominal b-matrix'),
    dict(name='neg_negative_readouts_not_reversed', kind='negative', subs=[S('REVERSE_NEGATIVE_READOUTS = True', 'REVERSE_NEGATIVE_READOUTS = False')], targets=G3, desc='alternate EPI lines not time-reversed'),
]

if __name__ == '__main__':
    run_all(HERE, 'epi_dti.py', 'dti.npz', report_fn, CONTROLS, HERE / 'grade_epidti_arm.py', sys.argv[1:] or None)

