"""Shared helpers for the reference learned/classical reconstructions (copied into each entrypoint folder)."""
import numpy as np

def fft2c(x):
    return np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(x, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))

def ifft2c(k):
    return np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k, axes=(-2, -1)), norm='ortho'), axes=(-2, -1))

def make_masks(rng, n, E=5, N=64, accel=4.0, rc=5.5):
    ky, kx = np.meshgrid(np.arange(N) - N // 2, np.arange(N) - N // 2, indexing='ij')
    r = np.sqrt(ky ** 2 + kx ** 2); cen = r <= rc
    w = 1.0 / (1 + (r / 8.0) ** 2); w[cen] = 0; w = w.ravel() / w.sum()
    nsel = int(round(N * N / accel)) - int(cen.sum())
    out = np.zeros((n, E, N, N), bool)
    for i in range(n):
        for e in range(E):
            m = cen.copy().ravel(); m[rng.choice(N * N, nsel, replace=False, p=w)] = True; out[i, e] = m.reshape(N, N)
    return out

def maps(img, te):
    te = np.asarray(te, float); mag = np.abs(img).astype(float); w = mag ** 2; lm = np.log(np.maximum(mag, 1e-12))
    t = te.reshape((-1, 1, 1))
    sw = w.sum(-3); st = (w * t).sum(-3); stt = (w * t * t).sum(-3); sy = (w * lm).sum(-3); sty = (w * t * lm).sum(-3)
    den = sw * stt - st ** 2
    r2s = -np.where(den > 0, (sw * sty - st * sy) / np.where(den > 0, den, 1), 0.0)
    z = (img[..., 1:, :, :] * np.conj(img[..., :-1, :, :])).sum(-3)
    return r2s, np.angle(z) / (2 * np.pi * np.diff(te).mean())

def roi(img, te, labels):
    from scipy.ndimage import binary_erosion
    r2s, b0 = maps(img, te); out = []
    for i in range(len(labels)):
        d = {}
        for k in range(1, 5):
            m = binary_erosion(labels[i] == k)
            if m.sum() >= 10:
                d[str(k)] = {'r2s_per_s': float(r2s[i][m].mean()), 'b0_hz': float(b0[i][m].mean())}
        out.append(d)
    return out

