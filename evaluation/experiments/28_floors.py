"""
Do scale and sign matter?  The exact identities of tests/test_knob_floors.py, on every synthetic
corpus (the universe and each length of the dataset), at every seed and every setting of
config.GRID.  Each holds by algebra; this checks that the code does what the algebra says,
everywhere the evaluation runs.

  F1  scaling every activity weight by c (0.25, 3, 4, -1) leaves every similarity unchanged
  F2  a weight -w on one activity = weight w with that activity's vector reversed
  F3  flipping alpha and beta together = the mirror image of the encoding with mirrored vectors
      (the second coordinate of each 2-D block negated)
  F4  flipping beta alone = counting depth the other way

Each check is also run once broken on purpose (F2 without reversing the vector, F3 without
mirroring, F4 with depths unchanged), to show it can fail.  Rows: test floors, metric max_gap
(the largest absolute difference).

The identities hold by algebra for every variant and activity, so each corpus is checked on
N_VARIANTS of its variants (drawn once with the shared seed; all of them if it has fewer) and F2
on three activities, the first, middle and last name in sorted order.

    python evaluation/experiments/28_floors.py                   # every synthetic corpus
    python evaluation/experiments/28_floors.py length_9 length_65
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

from evaluation import config, results  # noqa: E402
from evaluation import synthetic  # noqa: E402
from evaluation import universe as U  # noqa: E402
from evaluation.methods import hrr_ranges  # noqa: E402
from rotation_hrr.encoder import RotationHRREncoder  # noqa: E402
from rotation_hrr.tree_utils import tree_to_positioned_sequence  # noqa: E402

G = config.GRID
SETTINGS = list(itertools.product(G["alpha"], G["beta"], G["d"]))
N_VARIANTS = 200


class Transformed(RotationHRREncoder):
    """The same encoder, with each random vector passed through f(label, v)."""

    def __init__(self, f, **kw):
        super().__init__(**kw)
        self._f = f

    def get_label_vector(self, activity):
        return self._f(activity, super().get_label_vector(activity))


def mirror(v):
    out = v.copy()
    out[..., 1::2] *= -1
    return out


RANGES: dict = {}


def enc(d, seed, labels, f=None):
    n_max, n_max_depth = RANGES["current"]
    kw = dict(d=d, n_max=n_max, n_max_depth=n_max_depth, seed=seed)
    e = Transformed(f, **kw) if f else RotationHRREncoder(**kw)
    for a in labels:                       # the same draw order for every encoder
        e.get_label_vector(a)
    return e


def bundles(e, trees, **kw):
    return np.stack([e.encode_tree(t, **kw) for t in trees])


def sims(X):
    Xn = X / np.linalg.norm(X, axis=1, keepdims=True)
    return Xn @ Xn.T


def checks(trees, labels, a, b, d, seed) -> dict:
    out = {}
    rng = np.random.default_rng(0)
    w = {lab: float(x) for lab, x in zip(labels, rng.uniform(0.1, 3.0, len(labels)))}
    e = enc(d, seed, labels)
    S = sims(bundles(e, trees, alpha=a, beta=b, activity_weights=w))
    out["F1 scale"] = max(float(np.abs(sims(bundles(e, trees, alpha=a, beta=b, activity_weights=
                                                   {k: c * x for k, x in w.items()})) - S).max())
                          for c in (0.25, 3.0, 4.0, -1.0))
    f2 = f2_broken = 0.0
    for lab in sorted({labels[0], labels[len(labels) // 2], labels[-1]}):
        neg = bundles(e, trees, alpha=a, beta=b, activity_weights={lab: -2.0})
        rev = enc(d, seed, labels, lambda x, v, lab=lab: -v if x == lab else v)
        pos = bundles(rev, trees, alpha=a, beta=b, activity_weights={lab: 2.0})
        f2 = max(f2, float(np.abs(neg - pos).max()))
        f2_broken = max(f2_broken, float(np.abs(
            neg - bundles(e, trees, alpha=a, beta=b, activity_weights={lab: 2.0})).max()))
    out["F2 negative weight"], out["F2 broken"] = f2, f2_broken
    flipped = bundles(e, trees, alpha=-a, beta=-b)
    mirrored = bundles(enc(d, seed, labels, lambda x, v: mirror(v)), trees, alpha=a, beta=b)
    out["F3 flip both"] = float(np.abs(flipped - mirror(mirrored)).max())
    out["F3 broken"] = float(np.abs(flipped - bundles(e, trees, alpha=a, beta=b)).max())
    f4 = f4_broken = 0.0
    for t in trees:
        items = tree_to_positioned_sequence(t)[0]
        lab = [x for x, _, _ in items]
        p = np.array([x for _, x, _ in items])
        dep = np.array([x for _, _, x in items])
        lhs = e.encode_tree(t, alpha=a, beta=-b)
        f4 = max(f4, float(np.abs(lhs - e.encode(lab, positions=p, depths=-dep, alpha=a, beta=b)).max()))
        f4_broken = max(f4_broken, float(np.abs(
            lhs - e.encode(lab, positions=p, depths=dep, alpha=a, beta=b)).max()))
    out["F4 flip beta"], out["F4 broken"] = f4, f4_broken
    return out


def main() -> None:
    commit = results.commit()
    for name in synthetic.expand(sys.argv[1:]) or synthetic.names():
        trees = synthetic.load(name).trees
        RANGES["current"] = hrr_ranges(trees)         # the whole corpus's, as everywhere else
        if len(trees) > N_VARIANTS:
            pick = config.rng_for(config.DEFAULT_SEED, "pairs").choice(len(trees), N_VARIANTS, replace=False)
            trees = [trees[i] for i in sorted(pick)]
        t0 = time.time()
        labels = sorted({x for t in trees for x in U._labels(t)})
        rows = []
        for (a, b, d), s in itertools.product(SETTINGS, config.SEEDS):
            for check, gap in checks(list(trees), labels, a, b, d, s).items():
                rows.append({"method": "hrr", "log": name, "seed": s, "knob": "alpha,beta,d",
                             "value": f"{a:g},{b:g},{d}", "test": "floors", "edit": check,
                             "metric": "max_gap", "result": gap, "commit": commit})
        results.write(rows)
        worst = {}
        for r in rows:
            worst[r["edit"]] = max(worst.get(r["edit"], 0.0), r["result"])
        print(f"{name}: " + ", ".join(f"{k} {v:.1e}" for k, v in worst.items())
              + f"  ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
