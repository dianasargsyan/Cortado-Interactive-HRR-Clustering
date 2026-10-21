"""
Which settings are allowed, and where does each knob stop working?  HRR on every corpus of the
universe (evaluation/universe.py), on the longer synthetic corpora (evaluation/synthetic.py) and on the six
logs (BPI 2012 and BPI 2017 on config.SWEEP_SAMPLE's sample), five seeds.

Settings: alpha swept at beta = 1, beta swept at alpha = 1 (step 0.25 over 0 to 2), and a coarse
joint grid (alpha, beta in {0, 0.5, 1, 1.5, 2}).  The rules, fixed before the run:

  should_be_same   the block-order and renaming checks at the setting: HRR's gap over the
                   seed-to-seed gap on the same distances (a ratio above 1 fails)
  collisions       pairs of different variants closer than the noise band (95th percentile of
                   the gaps between two seeds on the same pairs), per seed
  saturation       rank agreement with the next setting of the sweep (same seed), next to the
                   agreement between two seeds at the setting: the knob has stopped mattering
                   where a step changes the ranking less than a reseed does
  collapse         rank agreement with alpha = beta = 0 (the bag of activity vectors, same seed),
                   next to the seed agreement: HRR has collapsed to a bag where it agrees with
                   the bag at least as well as with itself under another seed
  bunching         spread of the distances (90th minus 10th percentile), next to the noise band:
                   all distances bunch together where the spread is below the band

The should-be-the-same checks run on the universe only: they compare a variant with every
written-out order of a block, and the corpus with every renaming that maps it onto itself, which
exist only in a complete enumeration.  Every other rule runs on every corpus.  Distances are
dropped per seed once their numbers are taken, and rankings are kept in float32, so the largest
log fits in memory.

Rows: test admissibility, edit = the sweep.

    python evaluation/experiments/29_admissibility.py                    # the universe, d = config.D
    python evaluation/experiments/29_admissibility.py 8192 synthetic logs
"""

from __future__ import annotations

import itertools
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
from scipy.stats import rankdata  # noqa: E402

from evaluation import config, results, synthetic  # noqa: E402
from evaluation import universe as U  # noqa: E402
from evaluation.agreement import tau_b  # noqa: E402
from evaluation.methods import represent  # noqa: E402
from rotation_hrr.variant_enumeration import canon  # noqa: E402


STEPS = np.round(np.arange(0.0, 2.001, 0.25), 2)
COARSE = (0.0, 0.5, 1.0, 1.5, 2.0)


def sweeps():
    out = [("alpha sweep", [(a, 1.0) for a in STEPS]), ("beta sweep", [(1.0, b) for b in STEPS])]
    out.append(("joint", list(itertools.product(COARSE, COARSE))))
    return out


def upper(D):
    return D[np.triu_indices(len(D), 1)]


def rho(r1, r2) -> float:
    return float(np.corrcoef(r1, r2)[0, 1])


def main() -> None:
    args = sys.argv[1:]
    d = int(args.pop(0)) if args and args[0].isdigit() else config.HRR_DEFAULTS["d"]
    seeds = list(config.SEEDS)
    commit = results.commit()
    for name in synthetic.expand(args) or list(U.corpora()):
        t0 = time.time()
        corpus = synthetic.corpus(name, sampled=True)
        trees = corpus.trees
        if name.startswith("universe"):           # the should-be-the-same cases (see above)
            index = {canon(t): i for i, t in enumerate(trees)}
            cases = U.order_cases(trees, index)
            gs = U.rename_groups(name, trees)
            rn = {g: U.renamings(trees, idx, index) for g, idx in gs}
        else:
            cases, gs, rn = [], [], {}

        def dist(a, b, s):
            return represent("hrr", corpus, s, use_cache=False, outside_range=True,
                             alpha=a, beta=b, d=d).distances

        def ranks(v):
            return rankdata(v).astype(np.float32)

        rows = []
        bag = {s: ranks(upper(dist(0.0, 0.0, s)).astype(np.float32)) for s in seeds}
        for sweep, points in sweeps():
            prev = None
            for a, b in points:
                base = {"method": "hrr", "log": name, "knob": "alpha,beta,d",
                        "value": f"{a:g},{b:g},{d}", "test": "admissibility", "edit": sweep,
                        "commit": commit}
                V, Rk, od, od_gap = {}, {}, {}, {}
                d0 = {g: {} for g in rn}
                ng = {g: [] for g in rn}
                for s in seeds:                       # one matrix at a time (memory)
                    Dm = dist(a, b, s)
                    V[s] = upper(Dm).astype(np.float32)
                    Rk[s] = ranks(V[s])
                    if cases:
                        od[s] = np.concatenate([Dm[v, outs] for v, outs in cases])
                        od_gap[s] = np.mean([U.mean_pair_gap(Dm[v, outs][:, None], 0)
                                             for v, outs in cases])
                    for g, idx in gs:
                        if rn[g]:
                            iu = np.triu_indices(len(idx), 1)
                            d0[g][s] = Dm[np.ix_(idx, idx)][iu]
                            ng[g].append(np.mean([np.abs(Dm[np.ix_(img, img)][iu] - d0[g][s]).mean()
                                                  for _, img in rn[g]]))
                    del Dm
                gaps = np.concatenate([np.abs(V[s1] - V[s2]) for s1, s2 in zip(seeds, seeds[1:])])
                band = float(np.percentile(gaps, 95))
                del gaps
                seed_rho = float(np.mean([rho(Rk[s1], Rk[s2]) for s1, s2 in zip(seeds, seeds[1:])]))
                rows += [{**base, "metric": "noise_band", "result": band},
                         {**base, "metric": "seed_agreement", "result": seed_rho},
                         {**base, "metric": "seed_agreement_tau_b", "result":
                          float(np.mean([tau_b(Rk[s1], Rk[s2]) for s1, s2 in zip(seeds, seeds[1:])]))},
                         {**base, "metric": "vs_bag", "result":
                          float(np.mean([rho(Rk[s], bag[s]) for s in seeds]))},
                         {**base, "metric": "vs_bag_tau_b", "result":
                          float(np.mean([tau_b(Rk[s], bag[s]) for s in seeds]))},
                         {**base, "metric": "collisions", "result":
                          float(np.mean([np.sum(V[s] < band) for s in seeds]))},
                         {**base, "metric": "spread", "result":
                          float(np.mean([np.percentile(V[s], 90) - np.percentile(V[s], 10)
                                         for s in seeds]))}]
                if prev is not None:
                    rows.append({**base, "metric": "vs_previous_step", "result":
                                 float(np.mean([rho(Rk[s], prev[s]) for s in seeds]))})
                    rows.append({**base, "metric": "vs_previous_step_tau_b", "result":
                                 float(np.mean([tau_b(Rk[s], prev[s]) for s in seeds]))})
                prev = Rk
                # the should-be-the-same checks at this setting (universe only)
                if cases:
                    sg = U.mean_pair_gap(np.stack([od[s] for s in seeds]), 0)
                    rows.append({**base, "metric": "orders_gap_over_seed_gap",
                                 "result": float(np.mean([od_gap[s] for s in seeds]) / sg)
                                 if sg > 0 else 0.0})
                for g, _ in gs:
                    if not rn[g]:
                        continue
                    sg = U.mean_pair_gap(np.stack([d0[g][s] for s in seeds]), 0)
                    rows.append({**base, "log": g, "metric": "names_gap_over_seed_gap",
                                 "result": float(np.mean(ng[g]) / sg) if sg > 0 else 0.0})
        results.write(rows)
        print(f"{name}: {len(rows):,} rows, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
