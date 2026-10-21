"""
How much does the ranking change as a knob moves, against how much a reseed changes it?

On each log (or synthetic corpus; BPI 2012 and BPI 2017 on config.SWEEP_SAMPLE's sample, both
sides of every comparison on the same pairs), HRR at d = config.D, five seeds: alpha in ALPHAS at beta = 1,
and beta in BETAS at alpha = 1.  For every two values of a knob (same seed): rank agreement of
all pairwise distances (Spearman and Kendall's tau-b) and the overlap of each variant's 10
nearest neighbours; for every two seeds at one value: the same.

A step Delta is resolved at a value where moving by Delta changes the ranking more than a reseed
does (agreement between the two values below the agreement between two seeds, on every seed).
The grid's step for a knob is the smallest Delta resolved at every value of its range.  Where
even the largest move changes the ranking less than a reseed, the knob has saturated.  On the
universe, neighbour overlap is not computed (many variants tie, so a variant's 10 nearest depend
on how ties are broken).  Rows: test response.

    python evaluation/experiments/34_response.py                 # every log
    python evaluation/experiments/34_response.py sepsis
    python evaluation/experiments/34_response.py synthetic       # every synthetic corpus
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
from evaluation.agreement import tau_b  # noqa: E402

from evaluation import config, results, synthetic  # noqa: E402
from evaluation.methods import represent  # noqa: E402

D = config.D
ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
BETAS = (0.0, 0.25, 0.5, 0.75, 1.0)
K_NN = 10


def summary(Dm):
    v = Dm[np.triu_indices(len(Dm), 1)].astype(np.float32)
    np.fill_diagonal(Dm, np.inf)
    nn = np.argpartition(Dm, K_NN, axis=1)[:, :K_NN]
    return rankdata(v).astype(np.float32), nn


def rho(a, b) -> float:
    return float(np.corrcoef(a, b)[0, 1])


def overlap(n1, n2) -> float:
    return float(np.mean([len(set(x) & set(y)) / K_NN for x, y in zip(n1, n2)]))


def main() -> None:
    commit = results.commit()
    for key in (synthetic.expand(sys.argv[1:]) or config.LOGS):
        t0 = time.time()
        c = synthetic.corpus(key, sampled=True)
        nn = not key.startswith("universe")
        rows = []
        for knob, values, fixed in (("alpha", ALPHAS, ("beta", 1.0)), ("beta", BETAS, ("alpha", 1.0))):
            prev = {}
            for s in config.SEEDS:
                cur = {}
                for x in values:
                    kw = {knob: x, fixed[0]: fixed[1], "d": D}
                    cur[x] = summary(represent("hrr", c, s, use_cache=False, **kw).distances)
                base = {"method": "hrr", "log": key, "seed": s, "knob": f"{knob},d",
                        "test": "response", "commit": commit}
                for x1, x2 in itertools.combinations(values, 2):
                    r = {**base, "value": f"{x1:g}->{x2:g},{D}", "edit": f"{knob} step {x2 - x1:g}"}
                    rows.append({**r, "metric": "rank_agreement", "result": rho(cur[x1][0], cur[x2][0])})
                    rows.append({**r, "metric": "rank_agreement_tau_b", "result": tau_b(cur[x1][0], cur[x2][0])})
                    if nn:
                        rows.append({**r, "metric": "neighbour_overlap",
                                     "result": overlap(cur[x1][1], cur[x2][1])})
                if prev:
                    for x in values:
                        r = {**base, "value": f"{x:g},{D}", "edit": f"{knob}: vs next seed"}
                        rows.append({**r, "metric": "rank_agreement", "result": rho(prev[x][0], cur[x][0])})
                        rows.append({**r, "metric": "rank_agreement_tau_b", "result": tau_b(prev[x][0], cur[x][0])})
                        if nn:
                            rows.append({**r, "metric": "neighbour_overlap",
                                         "result": overlap(prev[x][1], cur[x][1])})
                prev = cur
        results.write(rows)
        print(f"{key}: {c.n:,} variants, {len(rows):,} rows, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
