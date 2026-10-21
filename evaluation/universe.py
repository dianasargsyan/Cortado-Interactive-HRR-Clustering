"""
The probe universe: every variant at small lengths, each compared with every other, like a log.

  universe_4         every valid variant with 2, 3 or 4 activities over the first 2, 3 or 4
                     letters, repeats included
  universe_5_<set>   five activities: every valid variant over one activity set per repeat
                     pattern (AAAAA, AAAAB, AAABB, AAABC, AABBC, AABCD, ABCDE), so variants with
                     the same activities differ only in order, parallel blocks and nesting (all
                     72,001 variants with five activities would be 2.8 billion pairs)

Each variant is kept in one written form (``probes.order``).  Every pair is described by which
properties differ.  The flags describe and group pairs; they never say what a distance should be,
and two different variants can agree on every flag.

  length        number of activities
  activities    which activities occur (as a set)
  n_distinct    number of different activities
  repeats       how often each activity occurs (→(A, A, B) against →(A, B, B))
  shape         the tree with its activities erased
  order         for the activities both variants contain: whether some pair of their
                occurrences that is ordered in both is ordered the other way
  parallel      for the activities both variants contain: whether some pair of their
                occurrences runs in parallel in one variant and not in the other
  (Both include two occurrences of the same activity: A before A, or A in parallel with A.)
  concurrency   whether the variant has a parallel block
  depth         the deepest activity's depth
"""

from __future__ import annotations

import itertools
import string
from collections import Counter
from functools import lru_cache
from itertools import combinations_with_replacement

import numpy as np
import pandas as pd

from evaluation import probes
from evaluation.orders import leaf_depths, precedence
from rotation_hrr.tree_rewrites import relabel
from rotation_hrr.variant_enumeration import (PAR, canon, canonicalize, deep_copy, full_enumeration_fixed_multiset,
                                 leaf, seq, shape_sig, tree_str)

L_MIN, L_REPEATS = 2, 4
SETS_5 = ("AAAAA", "AAAAB", "AAABB", "AAABC", "AABBC", "AABCD", "ABCDE")
FLAGS = ("length", "activities", "n_distinct", "repeats", "shape", "order", "parallel",
         "concurrency", "depth")
LETTERS = string.ascii_uppercase[:5]
LABEL_PAIRS = list(combinations_with_replacement(LETTERS, 2))


def _ordered(trees) -> list:
    out = {}
    for t in trees:
        u = probes.order(t)
        out[canon(u)] = u
    return [out[k] for k in sorted(out)]


def variants(n: int) -> list:
    """Every valid variant with n activities over the first n letters, one form each."""
    alpha = string.ascii_uppercase[:n]
    return _ordered(t for ms in combinations_with_replacement(alpha, n)
                    for t in full_enumeration_fixed_multiset(n, Counter(ms)))


@lru_cache(maxsize=1)
def corpora() -> dict[str, tuple]:
    """Corpus name -> its variants; each corpus is compared all-pairs."""
    out = {"universe_4": tuple(t for n in range(L_MIN, L_REPEATS + 1) for t in variants(n))}
    for s in SETS_5:
        out[f"universe_5_{s}"] = tuple(_ordered(full_enumeration_fixed_multiset(5, Counter(s))))
    return out


def _labels(t):
    return [t.label] if t.label is not None else [x for c in t.children for x in _labels(c)]


def _has_par(t):
    return t.label is None and (t.op == PAR or any(_has_par(c) for c in t.children))


def relations(t) -> dict:
    """For each pair of labels (x <= y) in t: the set of relations between their occurrences,
    each 'x<y', 'y<x' or 'x||y'.  Two occurrences of one label count as 'x<y' if ordered."""
    labs = _labels(t)
    n, pred = precedence(t)
    rel: dict = {}
    for i in range(n):
        for j in range(n):
            a, b = labs[i], labs[j]
            if a > b or (a == b and i >= j):
                continue
            ordered_ij, ordered_ji = pred[j] >> i & 1, pred[i] >> j & 1
            if a == b:
                r = "x<y" if ordered_ij or ordered_ji else "x||y"
            else:
                r = "x<y" if ordered_ij else "y<x" if ordered_ji else "x||y"
            rel.setdefault((a, b), set()).add(r)
    return {k: frozenset(v) for k, v in rel.items()}


def features(trees) -> pd.DataFrame:
    """One row per variant: the properties the pair flags compare."""
    rows = []
    for t in trees:
        labs = _labels(t)
        rows.append({"tree": tree_str(t), "length": len(labs),
                     "activities": "".join(sorted(set(labs))), "n_distinct": len(set(labs)),
                     "repeats": "".join(sorted(labs)),
                     "shape": shape_sig(t), "concurrency": _has_par(t),
                     "depth": max(leaf_depths(t)), "pattern": _pattern(labs),
                     "relations": relations(t)})
    return pd.DataFrame(rows)


def _pattern(labs) -> str:
    c = sorted(Counter(labs).values(), reverse=True)
    return "no repeats" if c[0] == 1 else "repeats " + "+".join(str(x) for x in c if x > 1)


def pair_flags(F: pd.DataFrame, rows=None) -> dict[str, np.ndarray]:
    """For each flag, a boolean matrix (len(rows) x len(F)): does the property differ?"""
    rows = np.arange(len(F)) if rows is None else np.asarray(rows)
    out = {}
    for f in ("length", "activities", "n_distinct", "repeats", "shape", "concurrency", "depth"):
        codes = pd.factorize(F[f])[0]
        out[f] = codes[rows, None] != codes[None, :]
    # order and parallel: compared only on the label pairs both variants contain
    for flag, part in (("order", lambda r: (r - {"x||y"}) or None),
                       ("parallel", lambda r: "x||y" in r)):
        codes = np.zeros((len(F), len(LABEL_PAIRS)), dtype=np.int64)       # 0 = pair absent
        index: dict = {}
        for v, rel in enumerate(F["relations"]):
            for k, lp in enumerate(LABEL_PAIRS):
                if lp in rel and part(rel[lp]) is not None:
                    codes[v, k] = index.setdefault(part(rel[lp]), len(index) + 1)
        a, b = codes[rows][:, None, :], codes[None, :, :]
        out[flag] = ((a > 0) & (b > 0) & (a != b)).any(axis=2)
    return out


# ---------------------------------------------------------------------------
# The same variant written differently: block orders and renamings
# ---------------------------------------------------------------------------


def order_cases(trees, index):
    """(variant, [indices of every written-out order]) for every block of activities that occur
    nowhere else in the variant: the block replaced by each order of its activities.  *index*
    maps canon() to a position in *trees*."""
    cases = []
    for v, t in enumerate(trees):
        for p in probes._operator_paths(t, PAR):
            node = probes._node(t, p)
            if not all(c.label is not None for c in node.children):
                continue
            labs = sorted({c.label for c in node.children})
            if len(labs) < len(node.children):
                continue                                          # a repeat inside the block
            if any(canon(relabel(t, dict(zip(labs, perm)))) != canon(t)
                   for perm in itertools.permutations(labs)):
                continue                                          # its activities occur elsewhere
            outs = []
            for perm in itertools.permutations(labs):
                u = deep_copy(t)
                block = seq(*[leaf(a) for a in perm])
                if not p:
                    u = block
                else:
                    parent = probes._node(u, p[:-1])
                    kids = list(parent.children)
                    kids[p[-1]] = block
                    probes._set_children(parent, kids)
                outs.append(index[canon(probes.order(canonicalize(u)))])
            cases.append((v, outs))
    return cases


def rename_groups(name, trees):
    """(group name, indices) whose renamings map the group onto itself: per length on
    universe_4, the whole corpus otherwise."""
    if name == "universe_4":
        lengths = np.array([len(_labels(t)) for t in trees])
        return [(f"{name}_n{n}", np.flatnonzero(lengths == n)) for n in sorted(set(lengths))]
    return [(name, np.arange(len(trees)))]


def renamings(trees, idx, index):
    """Every renaming of the group's letters that maps the group onto itself, as index arrays."""
    letters = sorted({a for i in idx for a in _labels(trees[i])})
    out = []
    for perm in itertools.permutations(letters):
        if list(perm) == letters:
            continue
        m = dict(zip(letters, perm))
        img = [index.get(canon(relabel(trees[i], m))) for i in idx]
        if all(j is not None for j in img):
            out.append((m, np.array(img)))
    return out


def mean_pair_gap(x: np.ndarray, axis: int) -> float:
    """Mean |x_i - x_j| over pairs i < j along *axis* (Gini's mean difference), averaged."""
    x = np.moveaxis(x, axis, 0)
    k = x.shape[0]
    return float(np.mean([np.abs(x[i] - x[j]).mean() for i in range(k) for j in range(i + 1, k)]))
