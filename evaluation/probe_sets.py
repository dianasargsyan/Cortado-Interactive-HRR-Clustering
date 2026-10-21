"""
The probe bases on the synthetic dataset (evaluation/dataset.py) and on the logs.

  constructed   at each length of dataset.LENGTHS: every shape (6, 9) or the shapes chosen by
                rule (12 to 65), each with its repeat versions; with_groups() names each base's
                group (depth or family, and repeat version)
  universe      the universe at 2, 3, 4, one lettering per pattern: a variant and its renamings
                (→(A, B) and →(B, A); →(A, A, B) and →(A, A, C)) are one probe base, so no pair
                is counted once per lettering
  check         the rule's shapes at 6 and 9, to compare with every shape there
  real          per log and length bin, the variants each seed's probe stream draws (R_BASES per
                bin per seed), each distinct variant once; the bins sit around the dataset's
                lengths (exact at 6 and 9, between geometric midpoints beyond)

A method is scored on these bases with every encoder seed, so every probe is seen under all five
seeds.  From 12 on (the rule's lengths and their real bins) the probes are thinned
(evaluation/probes.py): the universe and every shape at 6 and 9 keep every place and every size.
"""

from __future__ import annotations

import math

import numpy as np

from evaluation import config, dataset, probes

LENGTHS = dataset.LENGTHS                # 6, 9, 12, 15, 20, 30, 45, 65
EXHAUSTIVE = dataset.EVERY_SHAPE         # 6, 9: every shape
R_BASES = 5


def thinned(n: int) -> bool:
    """Whether the probes on bases of dataset length (or real bin) n are thinned."""
    return n not in EXHAUSTIVE


def bins() -> dict[int, tuple[int, int]]:
    """Each rule length's range of real lengths: between the geometric midpoints."""
    out = {}
    for i, n in enumerate(LENGTHS):
        if n in EXHAUSTIVE:
            continue
        lo = math.floor(math.sqrt(LENGTHS[i - 1] * n)) + 1
        hi = math.floor(math.sqrt(n * LENGTHS[i + 1])) if i + 1 < len(LENGTHS) else 10 ** 6
        out[n] = (lo, hi)
    return out


def length_bins() -> dict[int, tuple[int, int]]:
    """The real-base bins: exactly 6 and exactly 9, then the rule lengths' ranges."""
    b = {n: (n, n) for n in EXHAUSTIVE}
    b.update(bins())
    return dict(sorted(b.items()))


def with_groups(n: int) -> list[tuple[str, object]]:
    """(group, base) at length n: group = "depth d" (6, 9) or the rule family (12 ... 65), and
    the repeat version ("no repeats", "loop", "middle", ...)."""
    return [(f"{fam}, {version}", t) for _, fam, version, t in dataset.variants(n)]


def lettering_key(t, letters) -> str:
    """The canonical form of *t* under the renaming of *letters* that makes it smallest: equal for
    a variant and every renaming of it."""
    import itertools

    from rotation_hrr.tree_rewrites import relabel
    from rotation_hrr.variant_enumeration import canon
    return min(canon(relabel(t, dict(zip(letters, perm)))) for perm in itertools.permutations(letters))


def universe(n: int) -> list[tuple[str, object]]:
    """(group, variant) of the universe at n = 2, 3, 4, one lettering per pattern: of a
    variant and its renamings over the universe's letters, only the one whose canonical form is
    the smallest is kept.  group = depth, and whether it repeats."""
    from rotation_hrr.variant_enumeration import canon
    letters = [chr(ord("A") + i) for i in range(n)]
    out = []
    for *_, t in dataset.variants(n):
        if canon(t) == lettering_key(t, letters):
            out.append((f"depth {probes.depth_of(t)}, {'repeats' if dataset.extra_copies(t) else 'no repeats'}", t))
    return out


def check(n: int) -> list[tuple[str, object]]:
    """(family, shape) of the rule at n (6 or 9), to compare with every shape at n."""
    return [(f"{fam}, no repeats", t) for fam, t in dataset.check_shapes(n)]


def real(lengths: np.ndarray) -> dict[int, list[int]]:
    """Per length bin, the indices of a log's variants drawn on every seed's probe stream,
    pooled (*lengths*: each variant's number of activities)."""
    out = {}
    for n, (lo, hi) in length_bins().items():
        idx = np.flatnonzero((lengths >= lo) & (lengths <= hi))
        picked: list[int] = []
        for seed in config.SEEDS:
            rng = config.rng_for(seed, "probe")
            for i in (rng.choice(idx, size=min(R_BASES, len(idx)), replace=False) if len(idx) else []):
                if int(i) not in picked:
                    picked.append(int(i))
        out[n] = picked
    return out


def group(t) -> str:
    """A tree's group from the tree alone: its depth, and how many extra copies it holds."""
    k = dataset.extra_copies(t)
    return f"depth {probes.depth_of(t)}, " + ("no repeats" if not k else f"{k} extra cop{'y' if k == 1 else 'ies'}")
