"""Reference network: residual U-Net on the zero-filled multi-echo image (real/imag channels) + hard data consistency."""
import numpy as np, torch, torch.nn as nn

def fft2c_t(x):
    return torch.fft.fftshift(torch.fft.fft2(torch.fft.ifftshift(x, dim=(-2, -1)), norm='ortho'), dim=(-2, -1))

def ifft2c_t(k):
    return torch.fft.fftshift(torch.fft.ifft2(torch.fft.ifftshift(k, dim=(-2, -1)), norm='ortho'), dim=(-2, -1))

def to_ch(x):
    return torch.cat([x.real, x.imag], 1)

def from_ch(y):
    E = y.shape[1] // 2
    return torch.complex(y[:, :E], y[:, E:])

def dc(x, ku, m):
    k = fft2c_t(x)
    return ifft2c_t(torch.where(m, ku, k))

def block(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.LeakyReLU(0.1), nn.Conv2d(o, o, 3, padding=1), nn.LeakyReLU(0.1))

class UNet(nn.Module):
    def __init__(self, c, b):
        super().__init__()
        self.e1 = block(c, b); self.e2 = block(b, 2 * b); self.e3 = block(2 * b, 4 * b)
        self.u2 = nn.ConvTranspose2d(4 * b, 2 * b, 2, 2); self.d2 = block(4 * b, 2 * b)
        self.u1 = nn.ConvTranspose2d(2 * b, b, 2, 2); self.d1 = block(2 * b, b); self.out = nn.Conv2d(b, c, 1)
    def forward(self, x):
        a = self.e1(x); b_ = self.e2(nn.functional.avg_pool2d(a, 2)); c = self.e3(nn.functional.avg_pool2d(b_, 2))
        d = self.d2(torch.cat([self.u2(c), b_], 1)); e = self.d1(torch.cat([self.u1(d), a], 1))
        return x + self.out(e)

class Net(nn.Module):
    def __init__(self, base=24, E=5, per_echo_norm=False, mag_only=False, iters=2, use_dc=True):
        super().__init__()
        self.per_echo_norm = per_echo_norm; self.mag_only = mag_only; self.use_dc = use_dc
        self.nets = nn.ModuleList([UNet(2 * E, base) for _ in range(iters)])
    def forward(self, ku, m):
        x = ifft2c_t(ku)
        if self.per_echo_norm:   # (negative control) each echo scaled to unit max -> destroys decay
            s = x.abs().amax(dim=(-2, -1), keepdim=True) + 1e-8
        else:                    # one scale per slice, shared by all echoes
            s = x[:, :1].abs().amax(dim=(-3, -2, -1), keepdim=True) + 1e-8
        x = x / s; kus = ku / s
        for n in self.nets:
            x = from_ch(n(to_ch(x)))
            if self.use_dc:
                x = dc(x, kus, m)
        if self.mag_only:        # (negative control) magnitude-only output
            x = torch.complex(x.abs(), torch.zeros_like(x.real))
        if self.per_echo_norm:
            return x             # returned in normalised units per echo (negative control)
        return x * s

