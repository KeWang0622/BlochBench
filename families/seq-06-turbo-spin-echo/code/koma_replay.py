"""KomaMRI replay worker: python koma_replay.py job.json  (runs inside the grader interpreter)."""
import json, os, sys
import numpy as np
job = json.load(open(sys.argv[1]))
os.environ.setdefault('JULIA_NUM_THREADS', '1')
from juliacall import Main as jl
jl.seval('using KomaMRI')
jl.seval('''
function v8_replay(f, xs, ys, zs, rhos, T1s, T2s, dws, adc_shift, dtrf, dt, b0, b1)
  seq = read_seq(f)
  if b1 > 0
    seq = seq[b0:b1]
  end
  if adc_shift != 0.0
    for a in seq.ADC
      if a.N > 0
        a.delay = a.delay + adc_shift
      end
    end
  end
  sp = KomaMRICore.default_sim_params()
  sp["return_type"] = "mat"; sp["gpu"] = false; sp["Nthreads"] = 1; sp["precision"] = "f64"
  sp["Δt_rf"] = dtrf; sp["Δt"] = dt
  outs = Vector{Vector{ComplexF64}}()
  for i in 1:length(xs)
    obj = Phantom(x=xs[i], y=ys[i], z=zs[i], ρ=rhos[i], T1=T1s[i], T2=T2s[i], Δw=dws[i])
    sig = simulate(obj, seq, Scanner(); sim_params=sp, verbose=false)
    push!(outs, ComplexF64.(vec(sig[:, 1, 1])))
  end
  return outs
end''')
P = [np.load(p) for p in job['phantoms']]
xs = jl.seval('Vector{Vector{Float64}}')([np.ascontiguousarray(p['x'], float) for p in P])
ys = jl.seval('Vector{Vector{Float64}}')([np.ascontiguousarray(p['y'], float) for p in P])
zs = jl.seval('Vector{Vector{Float64}}')([np.ascontiguousarray(p['z'], float) for p in P])
rh = jl.seval('Vector{Vector{Float64}}')([np.ascontiguousarray(p['rho'], float) for p in P])
t1 = jl.seval('Vector{Vector{Float64}}')([np.ascontiguousarray(p['T1'], float) for p in P])
t2 = jl.seval('Vector{Vector{Float64}}')([np.ascontiguousarray(p['T2'], float) for p in P])
dw = jl.seval('Vector{Vector{Float64}}')([np.ascontiguousarray(p['dw'], float) for p in P])
br = job.get('block_range') or [0, 0]
outs = jl.v8_replay(job['seq'], xs, ys, zs, rh, t1, t2, dw, float(job.get('adc_shift_s', 0.0)), float(job['dt_rf']), float(job['dt']), int(br[0]), int(br[1]))
res = {}
for i in range(len(P)):
    res['sig%d' % i] = np.array(outs[i], dtype=complex)
np.savez(job['out'], **res)
print('ok', [len(v) for v in res.values()])

