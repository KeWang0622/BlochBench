#!/usr/bin/env python3
"""Standalone learned reconstruction: python predict.py --input test.npz --output recon.npz
Needs model.pt, net.py (and common.py) in the same folder."""
import argparse, sys
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
from net import Net
torch.set_num_threads(1)
OPT = {'shift_output': False}

def main(inp, outp):
    d = np.load(inp); ku = d['kspace'].astype(np.complex64); m = d['mask'].astype(bool)
    ck = torch.load(HERE / 'model.pt', map_location='cpu'); net = Net(**ck['cfg']); net.load_state_dict(ck['state']); net.eval()
    out = []
    with torch.no_grad():
        for b in range(0, len(ku), 8):
            out.append(net(torch.from_numpy(ku[b:b + 8]), torch.from_numpy(m[b:b + 8])).numpy())
    R = np.concatenate(out).astype(np.complex64)
    if OPT['shift_output']:   # (negative control) missing ifftshift in the centred-FFT convention
        R = np.fft.fftshift(R, axes=(-2, -1))
    np.savez_compressed(outp, recon=R)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--input', required=True); ap.add_argument('--output', required=True)
    a = ap.parse_args(); main(a.input, a.output)

