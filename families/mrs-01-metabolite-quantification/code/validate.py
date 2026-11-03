#!/usr/bin/env python3
"""Author validation for heldout-v7-mrsquant."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _v7build import run_all


def report_fn(out):
    return {'scope': 'water-referenced SVS quantification', 'preprocessing': 'coil combination, ECC, alignment', 'fitting': 'Lorentzian VARPRO',
            'quantification_model': 'tissue-water referencing', 'software': {'numpy': np.__version__}, 'validation_summary': 'author control', 'limitations': ['synthetic']}


S = lambda a, b: (a, b)
T3 = ['public_concentrations', 'hidden_case1_concentrations', 'hidden_case2_concentrations']
CONTROLS = [
    dict(name='reference', kind='positive', subs=[]),
    dict(name='pos_time_domain_fit', kind='positive', subs=[S("FIT_DOMAIN = 'frequency'", "FIT_DOMAIN = 'time'")], desc='time-domain VARPRO with separate residual-water component'),
    dict(name='pos_unweighted_coil_sum', kind='positive', subs=[S("COIL_COMBINE = 'water_weighted'", "COIL_COMBINE = 'plain_sum'")], desc='unweighted coil sum (valid, lower SNR)'),
    dict(name='neg_no_eddy_current_correction', kind='negative', domain=True, subs=[S('ECC = True', 'ECC = False')], targets=T3, desc='no water-referenced eddy-current phase correction'),
    dict(name='neg_no_transient_alignment', kind='negative', domain=True, subs=[S('ALIGN = True', 'ALIGN = False')], targets=['public_concentrations', 'hidden_case1_concentrations'], desc='transients averaged without frequency/phase alignment'),
    dict(name='neg_no_relaxation_correction', kind='negative', domain=True, subs=[S('RELAXATION = True', 'RELAXATION = False')], targets=T3, desc='no T1/T2 correction of water or metabolites'),
    dict(name='neg_no_csf_partial_volume', kind='negative', domain=True, subs=[S('PARTIAL_VOLUME = True', 'PARTIAL_VOLUME = False')], targets=T3, desc='voxel treated as pure tissue (CSF ignored)'),
    dict(name='neg_pure_water_concentration', kind='negative', domain=True, subs=[S('WATER_CONTENT = True', 'WATER_CONTENT = False')], targets=T3, desc='55.5 M used for every compartment (tissue water content ignored)'),
    dict(name='neg_no_proton_count', kind='negative', domain=True, subs=[S("PROTONS = {'NAA': 3, 'Cr': 3, 'Cho': 9}", "PROTONS = {'NAA': 1, 'Cr': 1, 'Cho': 1}")], targets=T3, desc='number of contributing protons ignored'),
]

if __name__ == '__main__':
    run_all(HERE, 'mrs_quant.py', 'conc.json', report_fn, CONTROLS, HERE / 'grade_mrsquant_arm.py', sys.argv[1:] or None)

