#!/usr/bin/env python3
"""Reference: simulate the exported sequence with KomaMRI and write simulation.npz.
Usage: python simulate.py --seq sequence.seq --phantom phantom.npz --out simulation.npz [--swap-xy]"""
import argparse, hashlib, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import seqtools as st, koma_replay as kr

NTI, NSP, NS = 5, 40, 40

def measure(seq_path):
    seq = st.read(seq_path)
    ev = st.events(seq); gw = st.gradient_waveforms(seq)
    exc = [r for r in ev['rf'] if 60 < r['flip_deg'] < 120]
    inv = [r for r in ev['rf'] if r['flip_deg'] > 150]
    K = []; T = []; TI = []; TD = []
    for a in ev['adc']:
        e = [r for r in exc if r['t_center'] < a['t'][0]][-1]
        i = [r for r in inv if r['t_center'] < e['t_center']][-1]
        nxt = [r for r in inv if r['t_center'] > e['t_center']]
        K.append(st.kspace_at(gw, e['t_center'], a['t'])[:, :2]); T.append(a['t'])
        TI.append(e['t_center'] - i['t_center'])
        if nxt:
            TD.append(nxt[0]['t_center'] - e['t_center'])
    K = np.array(K).reshape(NTI, NSP, NS, 2); T = np.array(T).reshape(NTI, NSP, NS)
    TI = np.array(TI).reshape(NTI, NSP).mean(1)
    e0 = [r for r in exc if r['t_center'] < ev['adc'][0]['t'][0]][-1]
    te = ev['adc'][0]['t'][NS // 2] - e0['t_center']
    return dict(kxy_cycles_per_m=K, adc_times_s=T, inversion_times_s=TI, recovery_delay_s=float(np.mean(TD)),
                echo_time_s=float(te), excitation_flip_deg=float(np.mean([r['flip_deg'] for r in exc])),
                inversion_flip_deg=float(np.mean([r['flip_deg'] for r in inv])))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seq', required=True); ap.add_argument('--phantom', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--swap-xy', action='store_true'); ap.add_argument('--t1-ms', action='store_true')
    a = ap.parse_args()
    ph = dict(np.load(a.phantom))
    if a.swap_xy:
        ph['x_m'], ph['y_m'] = ph['y_m'], ph['x_m']
    if a.t1_ms:
        ph['T1_s'] = ph['T1_s'] * 1000
    sig = kr.simulate(a.seq, ph)
    m = measure(a.seq)
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    np.savez(a.out, raw_signal=sig.reshape(NTI, NSP, NS).astype(np.complex128), sequence_sha256=sha(a.seq), phantom_sha256=sha(a.phantom), **m)
    print('simulated', sig.shape, 'TI', m['inversion_times_s'], 'TD', m['recovery_delay_s'], 'TE', m['echo_time_s'])

if __name__ == '__main__':
    main()

