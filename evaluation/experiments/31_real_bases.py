"""
Real variants as probe bases, and what the probe set costs.

  real bases   per log and length bin of the dataset (evaluation.probe_sets.length_bins; 6 and 9 take
               the variants of exactly that length), R real variants per seed, drawn uniformly
               on the probe stream, with their own activities and repeats; every path on each
               (evaluation.probes.paths_on)
  cost         APTED (unit costs) per pair and HRR (d = config.D) per tree, by length, on a
               sample of path pairs; and the counts of every probe layer

Output: cache/variants/real_paths.csv (one row per path step, regenerable) and
probe_counts.csv (the counts of every layer); results table rows test cost (method apted / hrr,
log "length <n>", metric ms_per_pair / ms_per_tree).

    python evaluation/experiments/31_real_bases.py            # R = 5
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from evaluation._env import CACHE, require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from evaluation import config, dataset, probe_sets, probes, results, synthetic  # noqa: E402
from evaluation.baselines import apted_pair_distances  # noqa: E402
from evaluation.corpus import load_log  # noqa: E402
from evaluation.methods import hrr_ranges  # noqa: E402
from rotation_hrr.encoder import RotationHRREncoder  # noqa: E402
from rotation_hrr.tree_utils import tree_to_sequence  # noqa: E402
from rotation_hrr.variant_enumeration import tree_str  # noqa: E402

OUT = CACHE / "real_paths.csv"
OUT_COUNTS = CACHE / "probe_counts.csv"
N_TIMED = 30                      # path pairs timed per length


def main() -> None:
    r = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    commit = results.commit()
    t0 = time.time()
    rows, avail = [], []
    for key in config.LOGS:
        c = load_log(key)
        lengths = np.array([len(tree_to_sequence(t)) for t in c.trees])
        for n, (lo, hi) in probe_sets.length_bins().items():
            idx = np.flatnonzero((lengths >= lo) & (lengths <= hi))
            avail.append({"log": key, "length": n, "bin": f"{lo}-{hi if hi < 10 ** 6 else ''}",
                          "variants": len(idx)})
            for seed in config.SEEDS:
                rng = config.rng_for(seed, "probe")
                pick = rng.choice(idx, size=min(r, len(idx)), replace=False) if len(idx) else []
                for i in pick:
                    t = c.trees[i]
                    for (edit, place, anchor), steps in probes.paths_on(t, probe_sets.thinned(n)).items():
                        for e in steps:
                            rows.append({"seed": seed, "log": key, "length_bin": n,
                                         "length": int(lengths[i]), "variant": int(i),
                                         "base": tree_str(e.base), "edit": edit, "place": str(place),
                                         "anchor": anchor, "size": e.size,
                                         "edited": tree_str(e.edited), "position": e.position,
                                         "depth": e.depth})
        print(f"{key}: bases drawn ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(OUT, index=False)

    # cost, on synthetic path pairs of each grid length (the same pairs for both methods)
    P = pd.read_csv(CACHE / "paths_counts.csv")
    cost_rows = []
    rng = np.random.default_rng(0)
    for n in probe_sets.LENGTHS:
        shapes = [t for _, t in dataset.base_shapes(n)]
        pairs = [(e.base, e.edited) for t in shapes
                 for st in probes.paths_on(t, probe_sets.thinned(n)).values() for e in st]
        pairs = [pairs[i] for i in rng.choice(len(pairs), size=min(N_TIMED, len(pairs)), replace=False)]
        trees = [t for p in pairs for t in p]
        t1 = time.perf_counter()
        apted_pair_distances(trees, np.arange(0, len(trees), 2), np.arange(1, len(trees), 2), n_jobs=1)
        ted = (time.perf_counter() - t1) / len(pairs) * 1000
        rg = hrr_ranges(trees)
        enc = RotationHRREncoder(d=config.D, n_max=rg[0], n_max_depth=rg[1], seed=config.DEFAULT_SEED)
        t1 = time.perf_counter()
        for t in trees:
            enc.encode_tree(t)
        hrr = (time.perf_counter() - t1) / len(trees) * 1000
        cost_rows += [{"method": "apted", "log": f"length {n}", "knob": "defaults", "test": "cost",
                       "metric": "ms_per_pair", "result": ted, "commit": commit},
                      {"method": "hrr", "log": f"length {n}", "knob": "d", "value": config.D,
                       "test": "cost", "metric": "ms_per_tree", "result": hrr, "commit": commit}]
        print(f"length {n}: APTED {ted:.1f} ms per pair, HRR {hrr:.2f} ms per tree", flush=True)
    results.write(cost_rows)

    v = len(synthetic.load("universe_4").trees)
    counts = [{"layer": "universe", "item": "universe_4", "variants": v, "pairs": v * (v - 1) // 2}]
    for layer, g in P[P["edit"] != "loops"].groupby("layer", sort=False):
        counts.append({"layer": "paths (synthetic)", "item": layer,
                       "variants": int(g["bases"].iloc[0]), "pairs": int(g["steps"].sum())})
    for (key, n), g in R.groupby(["log", "length_bin"]):
        counts.append({"layer": "paths (real bases)", "item": f"{key}, length {n}",
                       "variants": g["base"].nunique(), "pairs": len(g)})
    pd.DataFrame(counts + [{"layer": "real variants available", "item": f"{a['log']}, length {a['length']}",
                            "variants": a["variants"], "pairs": ""} for a in avail]).to_csv(OUT_COUNTS, index=False)
    print(f"\n{len(R):,} path steps on real bases; wrote {OUT.name}, {OUT_COUNTS.name} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
