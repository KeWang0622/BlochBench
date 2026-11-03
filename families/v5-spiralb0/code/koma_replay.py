"""KomaMRI replay helper (juliacall). simulate(seq_path, phantom_dict) -> complex128 vector of all ADC samples."""
import os
os.environ.setdefault('PYTHON_JULIAPKG_OFFLINE', 'yes')
os.environ.setdefault('JULIA_NUM_THREADS', '1')
import numpy as np
_JL = None

def _jl():
    global _JL
    if _JL is None:
        from juliacall import Main as M
        M.seval('using KomaMRI')
        M.seval('''function _v5koma(path, x, y, z, rho, T1, T2, dw)
            seq = read_seq(path)
            obj = Phantom(name="p", x=collect(Float64, x), y=collect(Float64, y), z=collect(Float64, z),
                          ρ=collect(Float64, rho), T1=collect(Float64, T1), T2=collect(Float64, T2), Δw=collect(Float64, dw))
            sig = simulate(obj, seq, Scanner(); sim_params=Dict{String,Any}("return_type"=>"mat", "gpu"=>false, "Nthreads"=>1), verbose=false)
            return ComplexF64.(vec(sig[:, 1, 1]))
        end''')
        _JL = M
    return _JL

def simulate(seq_path, ph, field_hz=None):
    """ph: mapping with x_m, y_m, z_m, density, T1_s, T2_s (any shape). field_hz overrides ph['B0_Hz'] if given.
    Spins with density <= 0 are skipped. KomaMRI off-resonance input is dw = 2*pi*field_hz (rad/s)."""
    rho = np.asarray(ph['density'], float).ravel()
    m = rho > 0
    f = np.asarray(ph['B0_Hz'] if field_hz is None else field_hz, float).ravel()
    args = [np.ascontiguousarray(np.asarray(ph[k], float).ravel()[m]) for k in ('x_m', 'y_m', 'z_m')]
    args += [rho[m], np.asarray(ph['T1_s'], float).ravel()[m], np.asarray(ph['T2_s'], float).ravel()[m], 2 * np.pi * f[m]]
    out = _jl()._v5koma(str(seq_path), *args)
    return np.asarray(out).astype(np.complex128)

