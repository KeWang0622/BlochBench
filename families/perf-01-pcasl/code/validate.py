#!/usr/bin/env python3
"""Author validation: reference, positive and negative controls for heldout-v7-pcasl."""
import sys
sys.dont_write_bytecode = True
import sys, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _v7build import run_all


def report_fn(out):
    d = np.load(out)
    import json as _j
    tr = np.load(HERE / 'truth' / 'public_truth.npz')
    cbf, lab = d['cbf'], tr['labels']
    return {'scope': 'pCASL CBF quantification', 'model': 'white-paper single compartment',
            'effective_labeling_efficiency': float(d['alpha_effective']), 'pld_by_slice_s': d['pld_by_slice_s'].tolist(),
            'gm_cbf_by_slice': [float(cbf[z][lab[z] == 1].mean()) for z in range(cbf.shape[0])],
            'software': {'numpy': np.__version__}, 'validation_summary': 'author control', 'limitations': ['synthetic']}


S = lambda a, b: (a, b)
CONTROLS = [
    dict(name='reference', kind='positive', subs=[], desc='reference solution'),
    dict(name='pos_median_pairs', kind='positive', subs=[S("PAIR_STAT = 'mean'", "PAIR_STAT = 'median'")], desc='median of pairwise control-label differences'),
    dict(name='pos_glm_drift', kind='positive', subs=[S("PAIR_STAT = 'mean'", "PAIR_STAT = 'glm'")], desc='GLM with label regressor and linear drift'),
    dict(name='neg_no_slice_timing', kind='negative', domain=True, subs=[S('USE_SLICE_TIMING = True', 'USE_SLICE_TIMING = False')],
         targets=['public_gm_cbf', 'hidden_case1_gm_cbf', 'hidden_case2_gm_cbf'], desc='same PLD for every slice of the 2D multislice readout'),
    dict(name='neg_no_bs_efficiency', kind='negative', domain=True, subs=[S('USE_BS_EFFICIENCY = True', 'USE_BS_EFFICIENCY = False')],
         targets=['public_gm_cbf', 'hidden_case1_gm_cbf', 'hidden_case2_gm_cbf'], desc='background-suppression inversion losses ignored'),
    dict(name='neg_no_m0_tr_correction', kind='negative', domain=True, subs=[S('USE_M0_TR_CORRECTION = True', 'USE_M0_TR_CORRECTION = False')],
         targets=['public_gm_cbf', 'hidden_case1_gm_cbf', 'hidden_case2_gm_cbf'], desc='short-TR M0 used without saturation-recovery correction'),
    dict(name='neg_no_label_efficiency', kind='negative', domain=True, subs=[S('USE_LABEL_EFFICIENCY = True', 'USE_LABEL_EFFICIENCY = False')],
         targets=['public_gm_cbf', 'hidden_case1_gm_cbf', 'hidden_case2_gm_cbf'], desc='pCASL labeling efficiency set to 1'),
    dict(name='neg_tissue_t1_decay', kind='negative', domain=True, subs=[S("DECAY_T1 = 'blood'", "DECAY_T1 = 'tissue'")],
         targets=['public_gm_cbf', 'hidden_case1_gm_cbf', 'hidden_case2_gm_cbf'], desc='label decay with tissue T1 instead of blood T1'),
    dict(name='neg_label_minus_control', kind='negative', subs=[S('CONTROL_MINUS_LABEL = True', 'CONTROL_MINUS_LABEL = False')],
         targets=['public_gm_cbf', 'hidden_case1_gm_cbf'], desc='label minus control (sign error)'),
    dict(name='neg_lambda_one', kind='negative', subs=[S('LAMBDA_OVERRIDE = None', 'LAMBDA_OVERRIDE = 1.0')],
         targets=['public_gm_cbf', 'hidden_case1_gm_cbf', 'hidden_case2_gm_cbf'], desc='blood-brain partition coefficient 1.0 instead of supplied 0.9'),
]

if __name__ == '__main__':
    only = sys.argv[1:] or None
    run_all(HERE, 'asl_cbf.py', 'cbf.npz', report_fn, CONTROLS, HERE / 'grade_pcasl_arm.py', only)

