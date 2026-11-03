"""Reference-solution helpers: KomaMRI simulation through juliacall and PyPulseq readback."""
import hashlib, os, json, numpy as np

def sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

_JL = None
def julia():
    global _JL
    if _JL is None:
        os.environ.setdefault('JULIA_NUM_THREADS', '1')
        from juliacall import Main as jl
        jl.seval('using KomaMRI')
        jl.seval('''
        function ref_sim(f, x, y, z, rho, T1, T2, dw, dtrf, adc_shift)
          seq = read_seq(f)
          if adc_shift != 0.0
            for a in seq.ADC
              if a.N > 0
                a.delay = a.delay + adc_shift
              end
            end
          end
          obj = Phantom(x=x, y=y, z=z, ρ=rho, T1=T1, T2=T2, Δw=dw)
          sp = KomaMRICore.default_sim_params()
          sp["return_type"]="mat"; sp["gpu"]=false; sp["Nthreads"]=1; sp["precision"]="f64"; sp["Δt_rf"]=dtrf
          sig = simulate(obj, seq, Scanner(); sim_params=sp, verbose=false)
          return ComplexF64.(vec(sig[:,1,1]))
        end''')
        _JL = jl
    return _JL

def koma(seq_path, iso, dtrf=1e-5, adc_shift=0.0):
    jl = julia()
    f = lambda k: np.ascontiguousarray(iso[k], dtype=float)
    out = jl.ref_sim(str(seq_path), f('x'), f('y'), f('z'), f('rho'), f('T1'), f('T2'), f('dw'), float(dtrf), float(adc_shift))
    return np.array(out, dtype=complex)

def koma_version():
    jl = julia()
    try:
        return str(jl.seval('string(pkgversion(KomaMRI))'))
    except Exception:
        return 'unknown'

def expand_columns(ph):
    """map phantom with z_offsets -> isochromat dict"""
    x = np.asarray(ph['x_m']); y = np.asarray(ph['y_m']); z = np.asarray(ph['z_offsets_m'])
    rho = np.asarray(ph['density'])
    iy, ix = np.nonzero(rho > 0)
    nz = len(z)
    rep = lambda a: np.repeat(a, nz)
    return {'x': rep(x[ix]), 'y': rep(y[iy]), 'z': np.tile(z, len(ix)), 'rho': rep(rho[iy, ix] / nz),
            'T1': rep(np.asarray(ph['T1_s'])[iy, ix]), 'T2': rep(np.asarray(ph['T2_s'])[iy, ix]),
            'dw': rep(2 * np.pi * np.asarray(ph['B0_Hz'])[iy, ix])}

def read_seq(path):
    import pypulseq as pp, warnings
    seq = pp.Sequence()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        seq.read(str(path))
    return seq

def rf_table(seq):
    """centre time, flip (deg), phase (deg) of every RF pulse; ADC sample times per ADC block."""
    t = 0.0; rfs = []; adcs = []
    for k in sorted(seq.block_events):
        b = seq.get_block(k)
        if b.rf is not None:
            rf = b.rf
            dt = np.diff(rf.t).mean() if len(rf.t) > 1 else 1e-6
            area = np.trapezoid(rf.signal, rf.t) if not np.allclose(np.diff(rf.t), 1e-6) else rf.signal.sum() * 1e-6
            c = rf.center if getattr(rf, 'center', None) is not None else rf.t[np.argmax(abs(rf.signal))]
            rfs.append((t + rf.delay + c, float(np.degrees(2 * np.pi * abs(area))), float(np.degrees(rf.phase_offset))))
        if b.adc is not None:
            a = b.adc
            adcs.append(t + a.delay + (np.arange(a.num_samples) + 0.5) * a.dwell)
        t += float(seq.block_durations[k])
    return rfs, adcs

