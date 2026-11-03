"""Run the reference pipeline (or a control variant) into a workspace directory."""
import argparse, shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument('--ws', required=True); ap.add_argument('--variant', default='reference')
a = ap.parse_args()
ws = Path(a.ws); ws.mkdir(parents=True, exist_ok=True)
for f in ['refkit.py', 'build_sequence.py', 'simulate.py', 'reconstruct.py', 'finish.py']:
    shutil.copy2(HERE / f, ws / f)
if a.variant in ('neg_no_ghost_correction', 'neg_uniform_kx_recon', 'pos_linear_phase_nav'):
    s = (ws / 'reconstruct.py').read_text().replace("default='reference'", "default='%s'" % a.variant); (ws / 'reconstruct.py').write_text(s)
shutil.copy2(HERE.parent.parent / 'public/inputs/phantom.npz', ws / 'phantom.npz')
py = sys.executable
def run(*c):
    subprocess.run([py] + list(c), cwd=ws, check=True)
if a.variant == 'neg_simulated_other_sequence':
    run('build_sequence.py', '--variant', 'neg_te_wrong_echo', '--out', 'sequence.seq')
    run('simulate.py', '--phantom', 'phantom.npz')
    run('build_sequence.py', '--variant', 'reference', '--out', 'sequence.seq')
else:
    run('build_sequence.py', '--variant', a.variant if a.variant not in ('neg_no_ghost_correction', 'neg_uniform_kx_recon', 'pos_linear_phase_nav') else 'reference', '--out', 'sequence.seq')
    run('simulate.py', '--phantom', 'phantom.npz')
run('finish.py', '--phantom', 'phantom.npz', '--variant', a.variant)


