"""
Which clustering algorithm: does it chain?  An algorithm chains when one cluster swallows most of
the log and the others are a handful of outliers; an analyst asking for k = 20 then gets one blob
and nineteen singletons.

For each log, HRR at its final settings (alpha = beta = 1, d = config.D, frequency ranges from
the log), five seeds, and k in K_RANGE (2, then every 5 to 30; 5, 10 and 20 are config.K):

  largest_cluster_variant_share   share of the variants in the largest cluster
  largest_cluster_case_share      the same, weighted by cases
  singleton_clusters              clusters holding exactly one variant

for hierarchical clustering with average and with complete linkage, and FasterPAM from BUILD.
An algorithm that chains keeps the largest share high as k grows; one that subdivides lets it
fall.  Hierarchical clustering is cut with maxclust, which can return fewer than k clusters on
ties; the number produced is recorded.  Rows: test chaining.

    python evaluation/experiments/17_chaining_check.py                  # the six logs
    python evaluation/experiments/17_chaining_check.py sepsis domestic
"""

from __future__ import annotations


import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import ROOT, require_cortado_env  # noqa: E402

require_cortado_env()
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from scipy.cluster.hierarchy import fcluster, linkage  # noqa: E402
from scipy.spatial.distance import squareform  # noqa: E402

from evaluation.clustering import kmedoids_cluster  # noqa: E402
from evaluation import config, results  # noqa: E402
from evaluation.corpus import load_log  # noqa: E402
from evaluation.methods import represent  # noqa: E402

CANDIDATES = list(config.LOGS)
K_RANGE = (2, 5, 10, 15, 20, 25, 30)


def hrr_distance(corpus, seed: int) -> np.ndarray:
    """HRR at its final settings through the pipeline (alpha = beta = 1, d = config.D)."""
    return represent("hrr", corpus, seed=seed, use_cache=False).distances


def summarise(labels: np.ndarray, counts: np.ndarray) -> dict:
    ids, sizes = np.unique(labels, return_counts=True)
    case_mass = np.array([counts[labels == i].sum() for i in ids])
    return {
        "clusters_produced": len(ids),
        "largest_cluster_variant_share": sizes.max() / len(labels),
        "largest_cluster_case_share": case_mass.max() / counts.sum(),
        "singleton_clusters": int((sizes == 1).sum()),
    }


def run(key: str, seed: int, commit: str) -> list[dict]:
    corpus = load_log(key)
    print(f"[{key}] {corpus.note} (seed {seed})", flush=True)
    counts = np.asarray(corpus.counts, dtype=float)

    t0 = time.perf_counter()
    D = hrr_distance(corpus, seed)
    print(f"  encoded + all-pairs in {time.perf_counter() - t0:.1f}s", flush=True)

    rows = []

    def emit(algo, k, stats):
        for metric, value in stats.items():
            rows.append({"method": "hrr", "log": key, "seed": seed, "algorithm": algo, "k": k,
                         "knob": "alpha,beta,d", "value": f"1,1,{config.D}", "test": "chaining",
                         "metric": metric, "result": value, "commit": commit})

    condensed = squareform(D, checks=False)
    for method in ("average", "complete"):
        t0 = time.perf_counter()
        Z = linkage(condensed, method=method)
        for k in K_RANGE:
            emit(f"hac-{method}", k, summarise(fcluster(Z, k, criterion="maxclust"), counts))
        print(f"  hac-{method}: {time.perf_counter() - t0:.1f}s", flush=True)

    t0 = time.perf_counter()
    for k in K_RANGE:
        _, labels = kmedoids_cluster(D, k, algorithm="fasterpam", seed=seed)
        emit("fasterpam", k, summarise(labels, counts))
    print(f"  fasterpam: {time.perf_counter() - t0:.1f}s", flush=True)
    return rows


def main() -> None:
    keys = [a for a in sys.argv[1:] if not a.startswith("-")] or CANDIDATES
    commit = results.commit()
    for key in keys:                       # one log at a time, written as it finishes
        rows = [r for seed in config.SEEDS for r in run(key, seed, commit)]
        results.write(rows)
        print(f"  {len(rows)} rows written", flush=True)


if __name__ == "__main__":
    main()
