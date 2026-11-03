#!/usr/bin/env python3
"""Generate seeded pilot data (public) and the reference key (private) for the knee cartilage T2 pilot-design task."""
import csv, json, math, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pilot_stats as S
PUB = HERE.parent / 'public' / 'inputs'
SEED = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 70455

CFG = dict(mu=41.5, sd_b=2.3, sd_asym=0.8, sd_sess=0.55, sd_side=0.85, n_tr=22, qc_tr='V15', qc_tr_session=1, n_pat=18, n_con=15, qc_grp='OA07', d_true=2.9,
           delta_acute=1.1, delta_group=2.0, alpha=0.05, power=0.85, nonevaluable=0.15)


def gen(seed):
    rng = np.random.default_rng(seed)
    tr = []
    for i in range(1, CFG['n_tr'] + 1):
        sid = f'V{i:02d}'; s = rng.normal(CFG['mu'], CFG['sd_b']); a = rng.normal(0, CFG['sd_asym'])
        for ses in (1, 2):
            g = rng.normal(0, CFG['sd_sess'])
            for h, sg in (('L', 1), ('R', -1)):
                v = s + sg * a + g + rng.normal(0, CFG['sd_side']); qc = True
                if sid == CFG['qc_tr'] and ses == CFG['qc_tr_session']:
                    v -= 9.5; qc = False
                tr.append({'subject_id': sid, 'session': ses, S.SIDE: h, S.VALUE: f'{v:.2f}', 'qc_pass': 'true' if qc else 'false'})
    gr = []
    for grp, pre, nn, mu in ((S.G1, 'OA', CFG['n_pat'], CFG['mu'] + CFG['d_true']), (S.G0, 'CT', CFG['n_con'], CFG['mu'])):
        for i in range(1, nn + 1):
            sid = f'{pre}{i:02d}'; s = rng.normal(mu, CFG['sd_b']); a = rng.normal(0, CFG['sd_asym']); g = rng.normal(0, CFG['sd_sess'])
            for h, sg in (('L', 1), ('R', -1)):
                v = s + sg * a + g + rng.normal(0, CFG['sd_side']); qc = True
                if sid == CFG['qc_grp']:
                    v += 16.0; qc = False
                gr.append({'subject_id': sid, 'group': grp, S.SIDE: h, S.VALUE: f'{v:.2f}', 'qc_pass': 'true' if qc else 'false'})
    return tr, gr


def write_csv(p, rows):
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


AP, PW = CFG['alpha'], CFG['power']


def derive(tr, gr):
    ep = S.endpoint_tr(tr); w, wci, df, n = S.wsd(ep); wc, wcci, _, _ = S.wsd(ep, centered=True)
    icc, icci = S.icc21(ep)
    G = S.group_diff(S.endpoint_groups(gr))
    sdd = math.sqrt(2) * w
    out = {'n_tr': n, 'wsd': w, 'wsd_ci': wci, 'wsd_centered': wc, 'wsd_centered_ci': wcci, 'rc': 1.96 * math.sqrt(2) * w, 'icc': icc, 'icc_ci': icci, 'group': G, 'sd_diff': sdd,
           'acute_n_z': S.n_paired_z(sdd, CFG['delta_acute'], AP, PW), 'acute_n_t': S.n_paired_t(sdd, CFG['delta_acute'], AP, PW),
           'group_n_z': S.n_two_z(G['sd_pooled'], CFG['delta_group'], AP, PW), 'group_n_t': S.n_two_t(G['sd_pooled'], CFG['delta_group'], AP, PW)}
    eph = S.endpoint_tr(tr, unit='hemisphere'); wh = S.wsd(eph)[0]; icch = S.icc21(eph)[0]
    epq = S.endpoint_tr(tr, qc=False); wq = S.wsd(epq)[0]; iccq = S.icc21(epq)[0]
    Gh = S.group_diff(S.endpoint_groups(gr, unit='hemisphere')); Gq = S.group_diff(S.endpoint_groups(gr, qc=False))
    out['alt'] = {'wsd_side': wh, 'icc_side': icch, 'wsd_noqc': wq, 'icc_noqc': iccq, 'acute_n_side': S.n_paired_z(math.sqrt(2) * wh, CFG['delta_acute'], AP, PW),
                  'acute_n_noqc': S.n_paired_z(math.sqrt(2) * wq, CFG['delta_acute'], AP, PW), 'group_sd_side': Gh['sd_pooled'], 'group_n_side': S.n_two_z(Gh['sd_pooled'], CFG['delta_group'], AP, PW),
                  'group_sd_noqc': Gq['sd_pooled'], 'group_n_noqc': S.n_two_z(Gq['sd_pooled'], CFG['delta_group'], AP, PW)}
    return out


if __name__ == '__main__':
    tr, gr = gen(SEED)
    D = derive(tr, gr)
    print(json.dumps(D, default=float))
    if '--write' in sys.argv:
        write_csv(PUB / 'pilot_test_retest.csv', tr); write_csv(PUB / 'pilot_groups.csv', gr)
        key = {'seed': SEED, 'cfg': CFG, 'ref': D, 'excluded_tr': [CFG['qc_tr']], 'excluded_groups': [CFG['qc_grp']]}
        (HERE / 'key.json').write_text(json.dumps(key, indent=1, default=float) + '\n')
        print('written')

