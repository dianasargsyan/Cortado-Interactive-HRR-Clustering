"""
The probe universe (evaluation/universe.py): every variant, and every pair described by which
properties differ.

  universe_4         every valid variant with 2 to 4 activities over the first 2 to 4 letters,
                     repeats included; all pairs
  universe_5_<set>   every valid variant with five activities over one activity set per repeat
                     pattern; all pairs within the set

Output in cache/variants/:

  universe_variants.csv     one row per variant: corpus, tree, length, activities, repeats,
                            pattern, shape, concurrency, depth
  universe_pairs.csv        pair counts per corpus, nesting level (the deeper variant of the
                            pair: flat, one level, two or more) and combination of differing flags
  universe_same_flags.csv   every pair of different variants that agrees on every flag

Two independent enumerators give the same variants (checked below).  The flags describe pairs;
they never say what a distance should be.

    python evaluation/experiments/22_universe.py
"""

from __future__ import annotations

import string
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import CACHE, require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from evaluation import universe as U  # noqa: E402
from rotation_hrr.variant_enumeration import canon, full_enumeration, n_leaves  # noqa: E402

OUT_VARIANTS = CACHE / "universe_variants.csv"
OUT_PAIRS = CACHE / "universe_pairs.csv"
OUT_SAME = CACHE / "universe_same_flags.csv"
LEVELS = {0: "flat", 1: "one level"}


def check_enumeration() -> None:
    """universe_4 equals an independent enumerator (full_enumeration over all labellings)."""
    ours = {canon(t) for t in U.corpora()["universe_4"]}
    theirs = {canon(t) for n in range(U.L_MIN, U.L_REPEATS + 1)
              for t in full_enumeration(n, list(string.ascii_uppercase[:n])) if n_leaves(t) == n}
    assert ours == theirs, f"{len(ours ^ theirs)} variants differ between the enumerators"
    for s in U.SETS_5:
        tree_labels = {tuple(sorted(U._labels(t))) for t in U.corpora()[f"universe_5_{s}"]}
        assert tree_labels == {tuple(s)}, s
    print(f"universe_4: {len(ours):,} variants, the same from both enumerators")


def main() -> None:
    check_enumeration()
    var_rows, pair_rows, same_rows = [], [], []
    for name, trees in U.corpora().items():
        F = U.features(trees)
        F.insert(0, "corpus", name)
        var_rows.append(F.drop(columns="relations"))
        P = U.pair_flags(F)
        iu = np.triu_indices(len(F), 1)
        level = np.maximum.outer(F["depth"].to_numpy(), F["depth"].to_numpy())[iu]
        combo = np.zeros(len(iu[0]), dtype=np.int64)
        for k, f in enumerate(U.FLAGS):
            combo |= P[f][iu].astype(np.int64) << k
        for (lv, c), cnt in Counter(zip(np.minimum(level, 2), combo)).items():
            pair_rows.append({"corpus": name, "level": LEVELS.get(lv, "two or more"),
                              "differs": " + ".join(f for k, f in enumerate(U.FLAGS) if c >> k & 1)
                              or "nothing",
                              **{f: bool(c >> k & 1) for k, f in enumerate(U.FLAGS)},
                              "pairs": cnt})
        for i, j in zip(iu[0][combo == 0], iu[1][combo == 0]):
            same_rows.append({"corpus": name, "a": F["tree"][i], "b": F["tree"][j],
                              "shape": F["shape"][i], "pattern": F["pattern"][i]})
        by_flag = {f: int(P[f][iu].sum()) for f in U.FLAGS}
        print(f"{name:<18} {len(F):>6,} variants  {len(iu[0]):>10,} pairs  "
              + "  ".join(f"{f} {v:,}" for f, v in by_flag.items()))
    V = pd.concat(var_rows, ignore_index=True)
    Pd = pd.DataFrame(pair_rows).sort_values(["corpus", "level", "pairs"], ascending=[True, True, False])
    V.to_csv(OUT_VARIANTS, index=False)
    Pd.to_csv(OUT_PAIRS, index=False)
    pd.DataFrame(same_rows).to_csv(OUT_SAME, index=False)
    same = Pd[Pd["differs"] == "nothing"]["pairs"].sum()
    print(f"\n{len(V):,} variants, {Pd['pairs'].sum():,} pairs; pairs of different variants "
          f"that agree on every flag: {same:,}")
    print(f"Wrote {OUT_VARIANTS.name}, {OUT_PAIRS.name}, {OUT_SAME.name}")


if __name__ == "__main__":
    main()
