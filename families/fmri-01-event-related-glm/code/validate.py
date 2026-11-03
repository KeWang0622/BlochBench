#!/usr/bin/env python3
"""Author validation for heldout-v7-fmriglm."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _v7build import run_all


def report_fn(out):
    return {'scope': 'event-related GLM', 'design': 'canonical HRF per slice', 'noise_model': 'AR(1)', 'n_volumes_analysed': 240,
            'software': {'numpy': np.__version__}, 'validation_summary': 'author control', 'limitations': ['synthetic']}


S = lambda a, b: (a, b)
B3 = ['public_psc_bias', 'hidden_case1_psc_bias', 'hidden_case2_psc_bias']
CONTROLS = [
    dict(name='reference', kind='positive', subs=[]),
    dict(name='pos_pooled_ar1', kind='positive', subs=[S('AR_POOLED = False', 'AR_POOLED = True')], desc='slice-pooled AR(1) prewhitening'),
    dict(name='pos_dummy_spikes_legendre', kind='positive', subs=[S('DROP_DUMMIES = True', 'DROP_DUMMIES = False'), S('DUMMY_SPIKES = False', 'DUMMY_SPIKES = True'), S("DRIFT_BASIS = 'dct'", "DRIFT_BASIS = 'legendre'")], desc='dummy volumes modelled with spike regressors; Legendre drift basis'),
    dict(name='neg_no_slice_timing', kind='negative', domain=True, subs=[S('SLICE_TIMING = True', 'SLICE_TIMING = False')], targets=B3, desc='regressor sampled at volume start for every slice'),
    dict(name='neg_dummies_dropped_onsets_unshifted', kind='negative', domain=True, subs=[S('SHIFT_ONSETS = True', 'SHIFT_ONSETS = False')], targets=B3, desc='dummy volumes discarded but event onsets not re-referenced'),
    dict(name='neg_dummies_kept', kind='negative', domain=True, subs=[S('DROP_DUMMIES = True', 'DROP_DUMMIES = False')], targets=B3, desc='pre-steady-state volumes analysed as data'),
    dict(name='neg_no_motion_regressors', kind='negative', domain=True, subs=[S('MOTION_REGRESSORS = True', 'MOTION_REGRESSORS = False')], targets=['public_psc_mae', 'public_null_calibration', 'hidden_case1_psc_mae', 'hidden_case2_null_calibration'], desc='stimulus-correlated motion left in the model residual'),
    dict(name='neg_ols_white_noise', kind='negative', domain=True, subs=[S('PREWHITEN = True', 'PREWHITEN = False')], targets=['public_null_calibration', 'hidden_case1_null_calibration'], desc='OLS statistics assuming white noise'),
    dict(name='neg_no_highpass', kind='negative', domain=True, subs=[S('HIGHPASS = True', 'HIGHPASS = False')], targets=['hidden_case1_null_calibration'], desc='no drift model'),
]

if __name__ == '__main__':
    run_all(HERE, 'fmri_glm.py', 'stats.npz', report_fn, CONTROLS, HERE / 'grade_fmriglm_arm.py', sys.argv[1:] or None)

