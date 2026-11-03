#!/usr/bin/env python3
"""Negative controls for heldout-v5-t2study: each plausible mistake must fail its targeted check."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from reference_solution import make_workspace
from grade_t2study import grade

CONTROLS = {
    'fft_shift': ('per_scan_roi_accuracy', 'centred k-space handed to an uncentred inverse FFT (image displaced by half the FOV relative to the label map)', 'raw-data convention->reconstruction'),
    'te_seconds': ('per_scan_roi_accuracy', 'echo times converted to seconds for fitting but T2 written to the ms table without conversion', 'fit->per-scan table'),
    'ses1_label': ('per_scan_roi_accuracy', 'session-1 label map reused for the session-2 scan of the same subject', 'label map->ROI measurement'),
    'zero_filled': ('hidden_rerun_mapping', 'zero-filled inverse FFT with root-sum-of-squares, ignoring the R=3 undersampling', None),
    'scans_as_units': ('stats_vs_truth', 'each scan treated as an independent observation in the group comparison (pseudo-replication)', 'per-scan table->subject-level statistics'),
    'student_t': ('hidden_rerun_stats', 'pooled-variance Student t-test instead of the pre-specified Welch test', None),
    'cohen_d': ('hidden_rerun_stats', "Cohen's d reported as Hedges' g (no small-sample correction)", None),
    'wsd_no_sqrt2': ('hidden_rerun_stats', 'within-subject SD taken as the SD of the scan-rescan differences', None),
    'drop_incomplete': ('hidden_rerun_stats', 'subjects with a single scan dropped from the primary analysis', 'per-scan table->subject-level statistics'),
    'sign_flip': ('stats_vs_truth', 'difference computed as control minus patient', None),
}

def main():
    out = {}
    for name in (sys.argv[1:] or list(CONTROLS)):
        tgt, desc, handoff = CONTROLS[name]
        ws = HERE / 'validation' / f'neg_{name}'
        make_workspace(ws, name)
        g = grade(ws, HERE / 'validation' / f'eval_neg_{name}')
        failed = [k for k, v in g['checks'].items() if not v['pass']]
        out[name] = dict(target=tgt, description=desc, handoff=handoff, target_failed=tgt in failed, failed_checks=failed,
                         target_detail=g['checks'][tgt]['detail'])
        print(name, 'target failed' if tgt in failed else 'TARGET PASSED (bad)', failed, flush=True)
    p = HERE / 'validation' / 'negative_controls_result.json'
    prev = json.loads(p.read_text()) if p.exists() else {}
    prev.update(out); p.write_text(json.dumps(prev, indent=1, default=str))
    print('ALL TARGETS FAILED' if all(v['target_failed'] for v in prev.values()) else 'SOME CONTROL NOT DETECTED')

if __name__ == '__main__':
    main()

