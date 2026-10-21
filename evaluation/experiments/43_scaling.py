"""
The scaling curve: how each method's time for every pair grows with the number of variants.
BPI 2017 (most variants) and BPIC15_1 (longest variants), samples of 100, 200, 500, 1,000, 2,000
and 5,000 variants (as far as the log has them), drawn once with the shared seed, the same sample
for every method; one run each (41's per-corpus times are the full-size points).  HRR at
d = config.D: one encoding with the batch encoder and every pair, both knobs on.

Rows: test cost_scaling, metric seconds_all_pairs, value = the number of variants.  A size whose
row exists is skipped (a rerun continues).

    python evaluation/experiments/43_scaling.py                          # every method but APTED
    python evaluation/experiments/43_scaling.py --methods apted          # overnight
    python evaluation/experiments/43_scaling.py --sizes 100 --methods apted   # a quick check
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402

from evaluation import config, results  # noqa: E402
from evaluation.corpus import from_trees, load_log  # noqa: E402
from evaluation.batch_hrr import Batch  # noqa: E402
from evaluation.methods import hrr_ranges, represent  # noqa: E402
from rotation_hrr.encoder import RotationHRREncoder  # noqa: E402

LOGS = ("bpi2017", "bpic15_1")
SIZES = (100, 200, 500, 1000, 2000, 5000)
METHODS = ("onehot", "trigram", "pqgram", "binary_branch", "hrr")


def done_rows():
    if not config.RESULTS.exists():
        return set()
    x = results.read(keep=lambda c: c[c["test"] == "cost_scaling"])
    return {(r.log, r.method, int(float(r.value))) for r in x.itertuples()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--sizes", default=",".join(map(str, SIZES)))
    ap.add_argument("--redo", action="store_true", help="time again sizes already in the table")
    args = ap.parse_args()
    methods = args.methods.split(",")
    sizes = [int(x) for x in args.sizes.split(",")]
    commit = results.commit()
    have = set() if args.redo else done_rows()
    for key in LOGS:
        c = load_log(key)
        order = config.rng_for(config.DEFAULT_SEED, "pairs").permutation(c.n)   # one draw per log
        for n in sizes:
            if n > c.n:
                continue
            sub = from_trees(f"{key}_sample_{n}", [c.trees[i] for i in order[:n]])
            rows = []
            for m in methods:
                if (key, m, n) in have:
                    continue
                t0 = time.perf_counter()
                if m == "hrr":                 # the batch encoder, as in 41's per-corpus cost
                    rg = hrr_ranges(c.trees)
                    enc = RotationHRREncoder(d=config.D, n_max=rg[0], n_max_depth=rg[1],
                                             seed=config.DEFAULT_SEED)
                    X = Batch(sub.trees).vectors(enc, 1.0, 1.0)
                    X /= np.linalg.norm(X, axis=1, keepdims=True)
                    np.arccos(np.clip(X @ X.T, -1, 1))
                else:
                    represent(m, sub, use_cache=False).distances
                sec = time.perf_counter() - t0
                rows.append({"method": m, "log": key, "knob": "variants", "value": n,
                             "test": "cost_scaling", "metric": "seconds_all_pairs", "result": sec,
                             "commit": commit})
                print(f"{key} n={n} {m}: {sec:.1f} s", flush=True)
            if rows:
                results.write(rows)


if __name__ == "__main__":
    main()
