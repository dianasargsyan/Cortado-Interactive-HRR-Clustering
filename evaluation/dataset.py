"""
The synthetic dataset, one for every step that uses synthetic data.  It builds trees; it scores
nothing.

  lengths 2, 3, 4      the universe: every variant over the first n letters (evaluation/universe.py)
  lengths 6, 9         every shape, activities A, B, C, ... left to right (evaluation/probes.shapes)
  lengths 12 to 65     the shapes chosen by rule (rule_shapes)
  from 6 on            each shape with its repeat versions (repeat_versions): 6 of them, from 12
                       on 8; at least three different activities
  loop paths           copies of a shape's first activity inserted, from adjacent to far apart
                       (loop_paths)

The rule for 12 to 65 covers every combination of a variant's global structure on a grid of
steps that grow with the length n; the probes add the local variety (every edit at every place).

  depth 0    all activities in sequence; all in one parallel block
  root       a parallel block at the root: w activities alongside a sequence of the rest,
             w in {1, n//8, n//4, n//2}
  depth 1    k parallel blocks of w activities, spread evenly along a sequence;
             w in {2, n//8, n//4, n//2} (at least 2), k = 1, 2, 4, 8, ... as many as fit
  nests      k nests of depth d in {2, 3, 4, 8}, spread evenly, in four forms: blocks of w
             activities and chains of c steps around the next level, (w, c) = (1, 1), the
             smallest; (s, 1), wide; (1, s), long; (s, s), wide and long; s = n//8, at least 3.
             A nest is used if it fits in half the length; k = 1, 2, 4, ... as many as fit
  mixed      one block of each width; one smallest nest of each depth; one depth-2 nest of each
             form (each where it fits)

Skipped on purpose: the widths, counts and depths between the steps; depths 5 to 7 (deeper than
any log; every shape at 6 and 9 has them); a parallel root over anything but a plain sequence
(no log variant has a parallel root); nests whose levels differ in width; blocks bunched at one
end (the probes edit at the start, the middle and the end).  check_shapes applies the rule at 6
and 9, where every shape exists, to show that the rule's shapes stand for all.

Corpora (every pair of a length compared, like a log): corpus(n).  At 9 a sample: the same
number of shapes from every depth (SAMPLE_9_PER_DEPTH, all if a depth has fewer), each with its
repeat versions; all 34,034 variants at 9 would need about 4.6 GB for the distances.
"""

from __future__ import annotations

import string
from functools import lru_cache

import numpy as np

from evaluation import config, probes
from rotation_hrr.variant_enumeration import canon, deep_copy, is_leaf, leaf, par, seq

UNIVERSE = (2, 3, 4)
EVERY_SHAPE = (6, 9)
RULE = (12, 15, 20, 30, 45, 65)
LENGTHS = EVERY_SHAPE + RULE                      # the lengths built from shapes
RULE_DEPTHS = (2, 3, 4, 8)                        # every depth of the logs, then a stress case
NEST_FORMS = ("smallest", "wide", "long", "wide and long")
CHECK_LENGTHS = (6, 9)                            # where the rule is checked against every shape
HEAVY_FROM = 12                                   # the two heavy repeat versions start here
MIN_DIFFERENT = 3                                 # no log variant of 6 or more has fewer
COPIES = (1, 2, 4, 8)                             # loop paths: extra copies
SAMPLE_9_PER_DEPTH = 20                           # shapes per depth in the all-pairs sample at 9

VERSIONS = ("loop", "middle", "far", "loop+1", "middle+1", "far+1", "quarter", "half")


# ---------------------------------------------------------------------------
# Labels and small tree helpers
# ---------------------------------------------------------------------------


def labels(n: int) -> list[str]:
    """A, B, C, ... up to 26 activities, A01, A02, ... beyond."""
    return list(string.ascii_uppercase[:n]) if n <= 26 else [f"A{i:02d}" for i in range(1, n + 1)]


def _leaves(t) -> list:
    """The activities of *t* in reading order (the order the linearisation reads them)."""
    if is_leaf(t):
        return [t]
    return [x for c in t.children for x in _leaves(c)]


def _relabelled(t, names: list[str]):
    """*t* with its activities named *names* in reading order."""
    t = probes.order(deep_copy(t))
    for x, a in zip(_leaves(t), names):
        x.label = a
    return probes.order(t)


def _with_labels(t):
    """*t* with A, B, C, ... (or A01, ...) left to right."""
    return _relabelled(t, labels(len(_leaves(t))))


def different(t) -> int:
    """How many different activities *t* has."""
    return len({x.label for x in _leaves(t)})


def extra_copies(t) -> int:
    """Activities minus different activities: how many extra copies *t* holds."""
    return len(_leaves(t)) - different(t)


# ---------------------------------------------------------------------------
# The rule for lengths 12 ... 65
# ---------------------------------------------------------------------------


def block_sizes(n: int) -> list[int]:
    """Activities per block at length n: 2, then an eighth, a quarter and half of n, rounded
    down; duplicates and sizes below 2 dropped."""
    return sorted({w for w in (2, n // 8, n // 4, n // 2) if w >= 2})


def rule_depths(n: int) -> list[int]:
    """Depths beyond 1 at length n: those of RULE_DEPTHS whose smallest nest (depth + 1
    activities) fits in half the length."""
    return [d for d in RULE_DEPTHS if nest_size(d, 1, 1) <= n // 2]


def nest_widths(n: int, form: str) -> tuple[int, int]:
    """(w, c) of a nest form at length n: activities per block and steps per chain."""
    s = max(3, n // 8)
    return {"smallest": (1, 1), "wide": (s, 1), "long": (1, s), "wide and long": (s, s)}[form]


def nest_size(d: int, w: int, c: int) -> int:
    """Activities in a nest of depth d with w activities per block and c steps per chain."""
    return sum(w if level % 2 else c for level in range(1, d + 1)) + 1


def _counts(fits) -> list[int]:
    """1, 2, 4, 8, ... while fits(k)."""
    out, k = [], 1
    while fits(k):
        out.append(k)
        k *= 2
    return out


def _nest(d: int, w: int, c: int, names: list[str], level: int = 1):
    """A nest of depth d >= 2 inside a sequence: blocks (odd levels) hold w activities and
    chains (even levels) c steps besides the next level; the operator at level d holds one
    more, so it has two children at least.  With w = c = 1, the smallest nest of its depth."""
    op, k = (par, w) if level % 2 == 1 else (seq, c)
    if level == d:
        return op(*[leaf(a) for a in names[:k + 1]])
    return op(*[leaf(a) for a in names[:k]], _nest(d, w, c, names[k:], level + 1))


def _spread(n_items: int, singles: int) -> list[int]:
    """How many single activities go before each of *n_items* items and after the last:
    *singles* spread as evenly as possible over n_items + 1 gaps."""
    gaps = n_items + 1
    base, extra = divmod(singles, gaps)
    # the extra ones go to the middle gaps first, so the layout is symmetric where it can be
    order = sorted(range(gaps), key=lambda g: (abs(g - (gaps - 1) / 2), g))
    out = [base] * gaps
    for g in order[:extra]:
        out[g] += 1
    return out


def _sequence_with(items_sizes: list[int], make, n: int):
    """A sequence of n activities: the items (each built by make(names) from items_sizes[i]
    activities) spread evenly, single activities between them; labelled A, B, ... left to
    right."""
    singles = n - sum(items_sizes)
    gaps = _spread(len(items_sizes), singles)
    names = labels(n)
    kids, pos = [], 0
    for i, size in enumerate(items_sizes):
        for _ in range(gaps[i]):
            kids.append(leaf(names[pos]))
            pos += 1
        kids.append(make(names[pos:pos + size]))
        pos += size
    for _ in range(gaps[-1]):
        kids.append(leaf(names[pos]))
        pos += 1
    return probes.order(kids[0] if len(kids) == 1 else seq(*kids))


def rule_shapes(n: int) -> list[tuple[str, object]]:
    """The shapes chosen by rule at length n: (family, tree)."""
    names = labels(n)
    blocks = lambda ns: par(*[leaf(a) for a in ns])
    out = [("all in sequence", probes.order(seq(*[leaf(a) for a in names]))),
           ("all in one block", probes.order(blocks(names)))]
    for w in sorted({1, n // 8, n // 4, n // 2} - {0}):
        if w < n - 1:
            out.append((f"{w} alongside a sequence",
                        probes.order(par(*[leaf(a) for a in names[:w]], seq(*[leaf(a) for a in names[w:]])))))
    for w in block_sizes(n):
        for k in _counts(lambda k: k * w <= n):
            out.append((f"{k} block{'s' if k > 1 else ''} of {w}", _sequence_with([w] * k, blocks, n)))
    for d in RULE_DEPTHS:
        for form in NEST_FORMS:
            w, c = nest_widths(n, form)
            size = nest_size(d, w, c)
            if size > n // 2:
                continue
            kind = "nest" if form == "smallest" else f"{form} nest"
            for k in _counts(lambda k: k * size <= n):
                out.append((f"{k} {kind}{'s' if k > 1 else ''} of depth {d}",
                            _sequence_with([size] * k, lambda ns, d=d, w=w, c=c: _nest(d, w, c, ns), n)))
    widths = block_sizes(n)
    if len(widths) > 1 and sum(widths) <= n:
        out.append(("one block of each width", _sequence_with(widths, blocks, n)))
    depths = rule_depths(n)
    if len(depths) > 1 and sum(nest_size(d, 1, 1) for d in depths) <= n:
        it = iter(depths)
        out.append(("one nest of each depth", _sequence_with([nest_size(d, 1, 1) for d in depths],
                                                             lambda ns: _nest(next(it), 1, 1, ns), n)))
    forms = [nest_widths(n, f) for f in NEST_FORMS if nest_size(2, *nest_widths(n, f)) <= n // 2]
    if len(forms) > 1 and sum(nest_size(2, w, c) for w, c in forms) <= n:
        it = iter(forms)
        out.append(("one depth-2 nest of each form", _sequence_with([nest_size(2, w, c) for w, c in forms],
                                                                    lambda ns: _nest(2, *next(it), ns), n)))
    seen, uniq = set(), []
    for fam, t in out:                            # a family can coincide with another at small n
        t = _with_labels(t)
        if canon(t) not in seen:
            seen.add(canon(t))
            uniq.append((fam, t))
    return uniq


# ---------------------------------------------------------------------------
# Repeat versions and loop paths
# ---------------------------------------------------------------------------


def repeat_versions(t) -> list[tuple[str, object]]:
    """The repeat versions of base tree *t* (all its activities different): the first activity's
    label given to later places, so the shape, length and depth stay the same.  Versions with
    fewer than MIN_DIFFERENT different activities are left out."""
    t = _with_labels(t)
    names = [x.label for x in _leaves(t)]
    n = len(names)
    if n < 2:
        return []
    mid = n // 2
    places = {"loop": [1], "middle": [mid], "far": [n - 1],
              "loop+1": [1, 2], "middle+1": [mid, mid + 1], "far+1": [n - 2, n - 1]}
    if n >= HEAVY_FROM:
        for name, q in (("quarter", n // 4), ("half", n // 2)):
            places[name] = sorted({int(round(x)) for x in np.linspace(1, n - 1, q)})
    out, seen = [], {canon(t)}
    for name in VERSIONS:
        if name not in places or any(p < 1 or p >= n for p in places[name]):
            continue
        new = list(names)
        for p in places[name]:
            new[p] = names[0]
        v = _relabelled(t, new)
        if len(set(new)) < MIN_DIFFERENT or canon(v) in seen:
            continue
        seen.add(canon(v))
        out.append((name, v))
    return out


def _insert_before(t, k: int, label: str):
    """*t* with a copy of *label* inserted before the k-th activity in reading order (after the
    last one if k equals the number of activities), as a sibling in that activity's parent; a
    copy whose place falls inside a parallel block joins it."""
    t = deep_copy(t)
    xs = _leaves(t)
    if is_leaf(t):
        return seq(t, leaf(label)) if k >= 1 else seq(leaf(label), t)
    anchor, after = (xs[k], False) if k < len(xs) else (xs[-1], True)
    parent = anchor.parent
    kids = list(parent.children)
    i = next(j for j, c in enumerate(kids) if c is anchor)
    kids.insert(i + 1 if after else i, leaf(label))
    parent.children = kids
    for c in kids:
        c.parent = parent
    return t


def loop_paths(t) -> dict[int, list[tuple[int, object]]]:
    """Loop paths of base tree *t* (all activities different): for c in COPIES (c < number of
    activities), c copies of the first activity inserted so that its occurrences sit s places
    apart in reading order, s = 1 (all adjacent: a loop), 2, 3, ... until the last copy reaches
    the end.  Returns {c: [(s, tree), ...]}."""
    t = _with_labels(t)
    names = [x.label for x in _leaves(t)]
    n, a = len(names), names[0]
    out: dict[int, list] = {}
    for c in COPIES:
        if c >= n:
            break
        steps = []
        s = 1
        while c * s <= n + c - 1:
            v = t
            for k in range(1, c + 1):            # occurrence k at reading position k*s
                v = _insert_before(v, k * s, a)
            steps.append((s, probes.order(v)))
            s += 1
        out[c] = steps
    return out


# ---------------------------------------------------------------------------
# The dataset per length
# ---------------------------------------------------------------------------


@lru_cache(maxsize=None)
def base_shapes(n: int) -> tuple:
    """(family, tree) of the shapes at length n: every shape at 6 and 9 (family = its depth),
    the rule's shapes at 12 ... 65.  Activities all different."""
    if n in EVERY_SHAPE:
        return tuple((f"depth {probes.depth_of(t)}", t) for t in probes.shapes(n))
    if n in RULE:
        return tuple(rule_shapes(n))
    raise ValueError(f"no shapes at length {n}")


@lru_cache(maxsize=None)
def variants(n: int) -> tuple:
    """Every variant of the dataset at length n: (shape index, family, version, tree), the base
    first ("no repeats") and then its repeat versions.  At 2, 3, 4 the universe."""
    if n in UNIVERSE:
        from evaluation import universe
        return tuple((i, f"depth {probes.depth_of(t)}", "universe", t)
                     for i, t in enumerate(universe.variants(n)))
    out = []
    for i, (fam, t) in enumerate(base_shapes(n)):
        out.append((i, fam, "no repeats", t))
        out += [(i, fam, name, v) for name, v in repeat_versions(t)]
    return tuple(out)


@lru_cache(maxsize=None)
def check_shapes(n: int) -> tuple:
    """The rule's shapes at a length of CHECK_LENGTHS, to compare with every shape there."""
    if n not in CHECK_LENGTHS:
        raise ValueError(f"the rule is checked at {CHECK_LENGTHS}, not {n}")
    return tuple(rule_shapes(n))


@lru_cache(maxsize=None)
def sample_9() -> tuple:
    """The all-pairs sample at 9: SAMPLE_9_PER_DEPTH shapes from every depth (all if a depth has
    fewer), drawn on the probe stream of the default seed, each with its repeat versions."""
    by_depth: dict[int, list] = {}
    for i, (_, t) in enumerate(base_shapes(9)):
        by_depth.setdefault(probes.depth_of(t), []).append(i)
    rng = config.rng_for(config.DEFAULT_SEED, "probe")
    keep = set()
    for d in sorted(by_depth):
        idx = by_depth[d]
        keep |= set(idx if len(idx) <= SAMPLE_9_PER_DEPTH
                    else rng.choice(idx, size=SAMPLE_9_PER_DEPTH, replace=False).tolist())
    return tuple(v for v in variants(9) if v[0] in keep)


def corpus(n: int) -> list:
    """The trees of the all-pairs corpus at length n (the sample at 9)."""
    rows = sample_9() if n == 9 else variants(n)
    return [t for *_, t in rows]


__all__ = ["CHECK_LENGTHS", "COPIES", "EVERY_SHAPE", "LENGTHS", "NEST_FORMS", "RULE", "RULE_DEPTHS",
           "UNIVERSE", "VERSIONS", "base_shapes", "block_sizes", "check_shapes", "corpus", "different",
           "extra_copies", "labels", "loop_paths", "nest_size", "nest_widths", "repeat_versions",
           "rule_depths", "rule_shapes", "sample_9", "variants"]
