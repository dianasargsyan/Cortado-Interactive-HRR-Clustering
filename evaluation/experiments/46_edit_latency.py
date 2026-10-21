"""
Is one edit fast enough?  On each of the six logs at d = config.D, alpha = beta = 1, seed 42: the
analyst's session holds the log's encoding, distances and a clustering (k-medoids by FasterPAM,
k = 10); one edit then costs

  prepare     the edited trees and weights (evaluation/edited.py)
  encode      every variant's vector
  distances   every pair
  cluster     FasterPAM started from the medoids before the edit

and the same for one knob change (alpha 1 to 0: nothing to prepare).  The median of three runs,
alone on the machine, against 1 second as the target and 10 seconds as the limit.

Rows: test edit_latency, edit = the kind of edit, metric seconds_<part> and seconds_total, and
variants_touched (the share of variants containing the edited activities).

    python evaluation/experiments/46_edit_latency.py            # the six logs, rows written
    python evaluation/experiments/46_edit_latency.py --dry bpi2017
"""

from __future__ import annotations

import sys
import time
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import kmedoids  # noqa: E402
import numpy as np  # noqa: E402

from rotation_hrr.domain_knowledge import DomainKnowledge as DK  # noqa: E402
from evaluation import config, results  # noqa: E402
from evaluation.corpus import load_log  # noqa: E402
from evaluation.edited import EditedLog  # noqa: E402
from rotation_hrr.tree_utils import tree_to_sequence  # noqa: E402

K, REPEATS, SEED = 10, 3, config.DEFAULT_SEED


def activities(trees):
    n = len(trees)
    share = Counter(a for t in trees for a in set(tree_to_sequence(t)))
    cand = sorted((c, a) for a, c in share.items() if 2 <= c < n)
    return cand[-1][1], cand[len(cand) // 2][1], cand[0][1]


def one(trees, d, ranges, dk, medoids, a=1.0, b=1.0, prebuilt=None):
    """Seconds per part for one edit (or, with *prebuilt*, one knob change)."""
    t = {}
    t0 = time.perf_counter()
    E = prebuilt or EditedLog(trees, dk, d=d, seed=SEED, ranges=ranges)
    t["prepare"] = 0.0 if prebuilt else time.perf_counter() - t0
    t0 = time.perf_counter()
    X = E.vectors(a, b, SEED)
    t["encode"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    nrm = np.linalg.norm(X, axis=1, keepdims=True)
    Xn = X / np.where(nrm < 1e-12, 1.0, nrm)
    S = Xn @ Xn.T
    D = np.arccos(np.clip(S, -1, 1)) / np.pi
    np.fill_diagonal(D, 0.0)
    t["distances"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    kmedoids.fasterpam(D, np.asarray(medoids), max_iter=100)
    t["cluster"] = time.perf_counter() - t0
    t["total"] = sum(t.values())
    return t


def main() -> None:
    args = sys.argv[1:]
    dry = "--dry" in args
    logs = [x for x in args if x != "--dry"] or list(config.LOGS)
    commit = results.commit()
    rows = []
    for key in logs:
        c = load_log(key)
        trees, d = c.trees, config.D
        A, M, R = activities(trees)
        base = EditedLog(trees, d=d, seed=SEED)
        D0 = base.distances(1.0, 1.0)
        medoids = kmedoids.fasterpam(D0, K, init="build", max_iter=100).medoids    # the session's clustering
        labs = [set(tree_to_sequence(t)) for t in trees]
        edits = {
            "equivalence": (DK(activity_equivalences={A: [M]}), {A, M}),
            "drop": (DK(ignored_activities={M}), {M}),
        }
        print(f"{key}: {c.n} variants, d = {d}", flush=True)
        for name, (dk, on) in list(edits.items()) + [("knob change", (None, None))]:
            runs = [one(trees, d, base.ranges, dk, medoids, a=0.0 if dk is None else 1.0,
                        prebuilt=base if dk is None else None) for _ in range(REPEATS)]
            med = {p: float(np.median([r[p] for r in runs])) for p in runs[0]}
            touched = 1.0 if on is None else float(np.mean([bool(on & s) for s in labs]))
            base_row = {"method": "hrr", "log": key, "test": "edit_latency", "edit": name,
                        "knob": "d", "value": d, "commit": commit}
            rows += [{**base_row, "metric": f"seconds_{p}", "result": v} for p, v in med.items()]
            rows.append({**base_row, "metric": "variants_touched", "result": touched})
            print(f"  {name:12s} total {med['total']:6.2f} s  (prepare {med['prepare']:.2f}, encode "
                  f"{med['encode']:.2f}, distances {med['distances']:.2f}, cluster {med['cluster']:.2f}); "
                  f"touches {touched:.0%}", flush=True)
    if not dry:
        results.write(rows)


if __name__ == "__main__":
    main()
