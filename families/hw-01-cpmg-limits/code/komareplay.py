"""KomaMRI replay of a CPMG .seq on Hann-weighted 1D samples (grader side)."""
import numpy as np
_JL = None
def jl():
    global _JL
    if _JL is None:
        from juliacall import Main as J
        J.seval('using KomaMRI')
        J.seval('''
        function v5_simsample(path, T1, T2, b1, z, w)
            seq = read_seq(path)
            for i in eachindex(seq.RF)
                seq.RF[i].A = seq.RF[i].A .* b1
            end
            M = length(z)
            obj = Phantom(name="s", x=zeros(M), y=zeros(M), z=z, ρ=w, T1=fill(T1,M), T2=fill(T2,M))
            sp = KomaMRICore.default_sim_params()
            sp["return_type"] = "mat"; sp["gpu"] = false; sp["Nthreads"] = 1
            return simulate(obj, seq, Scanner(); sim_params=sp, verbose=false)
        end
        ''')
        _JL = J
    return _JL
def sample_object(n=2000, L=0.012):
    k = np.arange(n) + 0.5
    z = (k / n - 0.5) * L; w = np.sin(np.pi * k / n) ** 2; w = w / w.sum()
    return z, w
def simulate_samples(seq_path, samples, adc_ns):
    J = jl(); z, w = sample_object()
    out = []
    for s in samples:
        raw = np.asarray(J.v5_simsample(str(seq_path), float(s['T1_s']), float(s['T2_s']), float(s['B1_scale']), J.seval('collect')(z), J.seval('collect')(w))).ravel()
        idx = np.cumsum([0] + list(adc_ns))
        mids = [raw[idx[i] + adc_ns[i] // 2] for i in range(len(adc_ns))]
        out.append(np.array(mids))
    return np.array(out)

