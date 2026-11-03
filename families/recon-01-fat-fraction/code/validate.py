#!/usr/bin/env python3
"""Author validation for heldout-v7-dixonraw."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _v7build import run_all


def report_fn(out):
    return {'scope': 'PDFF from raw k-space', 'reconstruction': 'ifft, crop oversampling', 'coil_combination': 'phase preserving', 'signal_model': 'multipeak',
            't1_correction': 'B1-corrected', 'software': {'numpy': np.__version__}, 'validation_summary': 'author control', 'limitations': ['synthetic']}


S = lambda a, b: (a, b)
P3 = ['public_pdff_vials', 'hidden_case1_pdff_vials', 'hidden_case2_pdff_vials']
CONTROLS = [
    dict(name='reference', kind='positive', subs=[]),
    dict(name='pos_refcoil_unwhitened', kind='positive', subs=[S("COMBINE = 'echo1_reference'", "COMBINE = 'refcoil_smooth'"), S('PREWHITEN = True', 'PREWHITEN = False')], desc='reference-coil phase, smoothed sensitivities, no prewhitening'),
    dict(name='pos_refcoil_whitened_sigma6', kind='positive', subs=[S("COMBINE = 'echo1_reference'", "COMBINE = 'refcoil_smooth'"), S('SMOOTH_SIGMA = 4.0', 'SMOOTH_SIGMA = 6.0')], desc='prewhitened reference-coil combination, stronger field-map regularisation'),
    dict(name='neg_single_peak_fat', kind='negative', domain=True, subs=[S("FAT_MODEL = 'multipeak'", "FAT_MODEL = 'single'")], targets=P3, desc='single-peak fat model'),
    dict(name='neg_chemical_shift_sign', kind='negative', domain=True, subs=[S('CS_SIGN = 1.0', 'CS_SIGN = -1.0')], targets=P3, desc='fat placed at positive frequency offsets'),
    dict(name='neg_no_t1_correction', kind='negative', domain=True, subs=[S('T1_CORRECTION = True', 'T1_CORRECTION = False')], targets=P3, desc='signal fat fraction reported as PDFF (T1 weighting ignored)'),
    dict(name='neg_t1_correction_nominal_flip', kind='negative', domain=True, subs=[S('USE_B1 = True', 'USE_B1 = False')], targets=['public_pdff_vials', 'hidden_case2_pdff_vials'], desc='T1 correction with nominal flip angle (B1 map ignored)'),
    dict(name='neg_rss_coil_combination', kind='negative', domain=True, subs=[S("COMBINE = 'echo1_reference'", "COMBINE = 'rss'")], targets=P3, desc='root-sum-of-squares combination destroys the echo phase evolution'),
    dict(name='neg_kspace_crop_oversampling', kind='negative', subs=[S("OVERSAMPLING = 'image_crop'", "OVERSAMPLING = 'kspace_crop'")], targets=P3, desc='readout oversampling removed by cropping k-space'),
    dict(name='neg_even_echoes_not_reversed', kind='negative', subs=[S('REVERSE_EVEN_ECHOES = True', 'REVERSE_EVEN_ECHOES = False')], targets=P3, desc='bipolar readout ordering ignored'),
]

if __name__ == '__main__':
    run_all(HERE, 'dixon_pdff.py', 'pdff.npz', report_fn, CONTROLS, HERE / 'grade_dixonraw_arm.py', sys.argv[1:] or None)

