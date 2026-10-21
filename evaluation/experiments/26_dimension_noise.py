"""
d and seed noise in one pass: every d, every setting of config.GRID, every seed.

For each corpus (the universe, the synthetic lengths, the six logs), each alpha x beta of the
grid, each d in DIMS and each seed (HRR through evaluation.methods.represent):

  rank_agreement     Spearman of all pairwise distances (and _tau_b, Kendall's tau-b): against
                     the next seed ("vs next seed"), and against the reference d = D_REF at the
                     default seed ("vs reference"); the reference against its own next seed too
  neighbour_overlap  share of each variant's 10 nearest neighbours kept under the next seed
                     (logs; the universe has many ties)
  noise_band_p95     95th percentile of |distance under seed s - under the next seed| over all
                     pairs (a distance below it counts as 0)
  noise_gap_median   the median of the same gaps
  encode_seconds, distance_seconds   the cost

evaluation/d_rule.py reads these rows (test dimension_grid) for the smallest d that meets its three
thresholds on every corpus and setting; the noise band is read at that d.  The reference is at
32768 so that 8192 is itself a candidate.

    python evaluation/experiments/26_dimension_noise.py synthetic logs
    python evaluation/experiments/26_dimension_noise.py sepsis universe_4
"""

from __future__ import annotations

import itertools
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
from scipy.stats import rankdata  # noqa: E402

from evaluation import config, results, synthetic  # noqa: E402
from evaluation.agreement import tau_b  # noqa: E402
from evaluation.methods import represent  # noqa: E402

DIMS = (64, 128, 256, 512, 1024, 2048, 4096, 8192)
D_REF = 32768
K_NN = 10
G = config.GRID
TEST = "dimension_grid"


def corpus_of(name):
    return synthetic.corpus(name)


def draw(corpus, seed, a, b, d):
    t0 = time.perf_counter()
    rep = represent("hrr", corpus, seed, use_cache=False, alpha=a, beta=b, d=d)
    t1 = time.perf_counter()
    D = rep.distances
    t2 = time.perf_counter()
    del rep                                   # D is not reused: work in place (memory)
    v = D[np.triu_indices(len(D), 1)].astype(np.float32)
    np.fill_diagonal(D, np.inf)
    nn = np.argpartition(D, K_NN, axis=1)[:, :K_NN] if len(D) > K_NN else None
    del D
    return {"ranks": rankdata(v).astype(np.float32), "d": v, "nn": nn,
            "encode": t1 - t0, "distance": t2 - t1}


def rho(r1, r2) -> float:
    return float(np.corrcoef(r1, r2)[0, 1])


def overlap(nn1, nn2) -> float:
    return float(np.mean([len(set(x) & set(y)) / K_NN for x, y in zip(nn1, nn2)]))


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--grid"]
    names = synthetic.expand(args) or ["universe_4", *config.LOGS]
    commit = results.commit()
    for name in names:
        t_c = time.time()
        corpus = corpus_of(name)
        logs = not name.startswith("universe")
        rows = []
        for a, b in itertools.product(G["alpha"], G["beta"]):
            base = {"method": "hrr", "log": name, "knob": "alpha,beta,d", "test": TEST,
                    "commit": commit}
            ref = draw(corpus, config.SEEDS[0], a, b, D_REF)
            ref2 = draw(corpus, config.SEEDS[1], a, b, D_REF)
            rows += [{**base, "value": f"{a:g},{b:g},{D_REF}", "seed": config.SEEDS[0],
                      "edit": "vs next seed", "metric": m, "result": f(ref["ranks"], ref2["ranks"])}
                     for m, f in (("rank_agreement", rho), ("rank_agreement_tau_b", tau_b))]
            del ref2
            for d in DIMS:
                val = f"{a:g},{b:g},{d}"
                prev = None
                for s in config.SEEDS:
                    x = draw(corpus, s, a, b, d)
                    r = {**base, "value": val, "seed": s}
                    rows += [{**r, "edit": "vs reference", "metric": "rank_agreement",
                              "result": rho(x["ranks"], ref["ranks"])},
                             {**r, "edit": "vs reference", "metric": "rank_agreement_tau_b",
                              "result": tau_b(x["ranks"], ref["ranks"])},
                             {**r, "edit": "cost", "metric": "encode_seconds", "result": x["encode"]},
                             {**r, "edit": "cost", "metric": "distance_seconds", "result": x["distance"]}]
                    if prev is not None:
                        gap = np.abs(x["d"] - prev["d"])
                        rows += [{**r, "edit": "vs next seed", "metric": "rank_agreement",
                                  "result": rho(prev["ranks"], x["ranks"])},
                                 {**r, "edit": "vs next seed", "metric": "rank_agreement_tau_b",
                                  "result": tau_b(prev["ranks"], x["ranks"])},
                                 {**r, "edit": "vs next seed", "metric": "noise_band_p95",
                                  "result": float(np.percentile(gap, 95))},
                                 {**r, "edit": "vs next seed", "metric": "noise_gap_median",
                                  "result": float(np.median(gap))}]
                        if logs and x["nn"] is not None:
                            rows.append({**r, "edit": "vs next seed", "metric": "neighbour_overlap",
                                         "result": overlap(prev["nn"], x["nn"])})
                    prev = x
            print(f"  {name} alpha {a:g} beta {b:g} done ({time.time() - t_c:.0f}s)", flush=True)
        results.write(rows)
        print(f"{name}: {corpus.n:,} variants, {len(rows):,} rows, {time.time() - t_c:.0f}s", flush=True)


if __name__ == "__main__":
    main()
