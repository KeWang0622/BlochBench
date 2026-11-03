#!/usr/bin/env python3
"""Reference: simulate the exported spiral sequence with KomaMRI including the phantom field, write simulation.npz.
Usage: python simulate.py --seq sequence.seq --phantom phantom.npz --out simulation.npz [--hz-as-rad]"""
import argparse, hashlib, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seqtools as st, koma_replay as kr

def measure(seq_path):
    seq = st.read(seq_path); ev = st.events(seq); gw = st.gradient_waveforms(seq)
    exc = ev['rf'][0]; a = ev['adc'][0]
    K = st.kspace_at(gw, exc['t_center'], a['t'])[:, :2]
    return dict(kxy_cycles_per_m=K, adc_times_s=a['t'], excitation_time_s=float(exc['t_center']),
                echo_time_s=float(a['t'][0] - exc['t_center']), fov_m=0.216, matrix=np.array([40, 40]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seq', required=True); ap.add_argument('--phantom', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--hz-as-rad', action='store_true')
    a = ap.parse_args()
    ph = dict(np.load(a.phantom))
    field = ph['B0_Hz'] / (2 * np.pi) if a.hz_as_rad else ph['B0_Hz']     # control: Hz handed over as rad/s
    sig = kr.simulate(a.seq, ph, field_hz=field)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    np.savez(a.out, raw_signal=sig, sequence_sha256=sha(a.seq), phantom_sha256=sha(a.phantom), **measure(a.seq))
    print('simulated', sig.shape)

if __name__ == '__main__':
    main()

