"""b-matrix from an exported Pulseq file (reference-solution helper, PyPulseq waveforms)."""
import numpy as np

def bmatrix(seq, t_exc, t_refs, t_echo, dt=1e-6):
    """b-matrix (s/mm^2) from the excitation centre to t_echo, with sign inversion at each refocusing centre."""
    wd = seq.waveforms_and_times()[0]
    t = np.arange(t_exc, t_echo, dt) + dt / 2
    k = np.zeros((len(t), 3))
    for ax in range(3):
        w = wd[ax]
        if w.shape[1] == 0:
            continue
        g = np.interp(t, w[0], w[1], left=0, right=0)
        sign = np.ones_like(t)
        for tr in t_refs:
            sign[t > tr] *= -1
        k[:, ax] = np.cumsum(g * sign) * dt
    B = (2 * np.pi) ** 2 * np.einsum('ti,tj->ij', k, k) * dt * 1e-6
    return B

