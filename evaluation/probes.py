"""
Probe trees: known edits of known variants, for the capability tests.  The trees follow Cortado's
grammar (a sequence's children are activities or parallel blocks; a parallel block's children are
activities and at most one sequence).

  shapes(n)         every valid tree with n activities, labelled A, B, C, ... once
  single_edits(t)   each edit applied at every place it can go in t
  paths_on(t)       each edit grown one step at a time from one place of t

Every edit records where it happened: its position (first, middle or last slot of the sequence it
sits in, or "whole"; an activity inside a parallel block takes the block's slot) and its depth
(the encoder's depth of the edited activities).

Thinned (thin=True, the long bases: evaluation.probe_sets.thinned): single edits at every slot of a
sequence of at most FULL_UP_TO children and at PLACES evenly spaced slots of a longer one (the
start, a quarter, the middle, three quarters, the end); paths at the sizes 1, 2, 4, 8, ... and
their largest size.  Every position and depth a result is reported by is still edited.
"""

from __future__ import annotations

import itertools
import string
from dataclasses import dataclass

from rotation_hrr.tree_rewrites import sort_parallel
from rotation_hrr.variant_enumeration import (
    PAR,
    SEQ,
    canon,
    canonicalize,
    deep_copy,
    enumerate_shapes,
    is_leaf,
    leaf,
    n_leaves,
    par,
    seq,
    tree_str,
)

EDITS: dict[str, str] = {
    "move": "one activity moves k slots within its sequence",
    "missing": "one activity is absent",
    "relabel": "one activity is replaced by one not in the variant",
    "repetition": "one activity occurs one more time, next to itself",
    "seq_to_par": "adjacent activities of a sequence become a new parallel block",
    "joins": "an activity next to a parallel block joins it",
    "nesting": "activities of a parallel block become an ordered chain inside it",
    "alongside": "an activity runs alongside the chain next to it: →(A, B, C) to ∧(A, →(B, C))",
}

POSITIONS = ("start", "middle", "end", "whole")
FULL_UP_TO = 8
PLACES = 5


@dataclass(frozen=True, eq=False)
class Edit:
    edit: str           # a key of EDITS
    base: object        # ConcurrencyTree, children in linearisation order
    edited: object      # ConcurrencyTree, children in linearisation order
    size: int           # slots moved, activities affected, or block width
    position: str       # one of POSITIONS
    depth: int          # encoder depth of the edited activities (in base)
    where: str          # plain words, e.g. "C moves 2 right"
    touched: frozenset = frozenset()   # labels of the activities the edit involves
    op: tuple = ()                     # the edit as an operation on labels (evaluation/phase2_probes.py)
    slot: tuple = ()                   # (slot, children) in the sequence it sits in; () for "whole"


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------


def order(t):
    """A copy with parallel children in the order the linearisation reads them."""
    return sort_parallel(t)


def shapes(n: int) -> list:
    """Every valid tree with n activities, labelled A, B, C, ... left to right."""
    if n > 25:
        raise ValueError("labelled shapes use single letters; n must be at most 25")
    out = []
    for skeleton in enumerate_shapes(n):
        t = order(skeleton)
        for slot, label in zip(_leaves(t), string.ascii_uppercase):
            slot.label = label
        out.append(order(t))
    return out


def depth_of(t) -> int:
    """Deepest activity's encoder depth."""
    return max(max(len(p) - 1, 0) for p in _leaf_paths(t))


# ---------------------------------------------------------------------------
# Single edits, at every place they can go
# ---------------------------------------------------------------------------


def single_edits(t, smallest: bool = False, thin: bool = False) -> list[Edit]:
    """Every edit in EDITS applied at every place it can go in *t*.  With *smallest*, each edit
    only at its smallest size (a move of one slot, two activities becoming parallel, two
    becoming ordered inside a block, a chain of two alongside): every subset of a wide block
    would otherwise be enumerated (2^k nesting edits for a block of k activities).  With *thin*,
    only at the kept slots of each sequence (kept_slots)."""
    t = order(t)
    out: list[Edit] = []
    for fn in (_move, _missing, _relabel, _repetition, _seq_to_par, _joins, _nesting, _alongside):
        if fn in (_move, _seq_to_par, _nesting, _alongside):
            fn(t, out, smallest)
        else:
            fn(t, out)
    if thin:
        out = [e for e in out if not e.slot or e.slot[0] in kept_slots(e.slot[1])]
    seen: set = set()          # one entry per edited tree: "A right 1" and "B left 1" are one swap
    return [e for e in out if (e.edit, canon(e.edited)) not in seen
            and not seen.add((e.edit, canon(e.edited)))]


def kept_slots(k: int) -> set[int]:
    """The slots a thinned sequence of k children is edited at."""
    if k <= FULL_UP_TO:
        return set(range(k))
    return {round(j * (k - 1) / (PLACES - 1)) for j in range(PLACES)}


def _move(t, out, smallest=False):
    for q in _operator_paths(t, SEQ):
        kids = _node(t, q).children
        for i, c in enumerate(kids):
            if not is_leaf(c):
                continue
            for j in range(len(kids)):
                if j == i or (smallest and abs(j - i) != 1):
                    continue
                new = deep_copy(t)
                nk = list(_node(new, q).children)
                nk.insert(j, nk.pop(i))
                _set_children(_node(new, q), nk)
                nb = kids[j] if abs(j - i) == 1 else None
                swap = nb is not None and is_leaf(nb)
                _emit(out, "move", 0, t, new, abs(j - i), q + (i,), 1,
                      f"{c.label} moves {abs(j - i)} {'right' if j > i else 'left'}",
                      touched={c.label, nb.label} if swap else {c.label},
                      op=("swap", c.label, nb.label) if swap else ("move", c.label, j - i))


def _missing(t, out):
    for p in _leaf_paths(t):
        if not p:
            continue                                   # a one-activity variant has nothing left
        new = deep_copy(t)
        nk = list(_node(new, p[:-1]).children)
        gone = nk.pop(p[-1])
        _set_children(_node(new, p[:-1]), nk)
        _emit(out, "missing", -1, t, new, 1, p, 1, f"{gone.label} missing",
              touched={gone.label}, op=("remove", gone.label))


def _relabel(t, out):
    fresh = _fresh(t)
    for p in _leaf_paths(t):
        new = deep_copy(t)
        old = _node(new, p).label
        _node(new, p).label = fresh
        _emit(out, "relabel", 0, t, new, 1, p, 1, f"{old} → {fresh}",
              touched={old}, op=("relabel", old))


def _repetition(t, out):
    for p in _leaf_paths(t):
        label = _node(t, p).label
        if not p:
            new = seq(deep_copy(t), leaf(label))
        else:
            new = deep_copy(t)
            nk = list(_node(new, p[:-1]).children)
            nk.insert(p[-1] + 1, leaf(label))
            _set_children(_node(new, p[:-1]), nk)
        _emit(out, "repetition", 1, t, new, 1, p, 1, f"{label} twice",
              touched={label}, op=("repeat", label))


def _seq_to_par(t, out, smallest=False):
    for q in _operator_paths(t, SEQ):
        kids = _node(t, q).children
        for w in range(2, 3 if smallest else len(kids) + 1):
            for i in range(len(kids) - w + 1):
                if not all(is_leaf(c) for c in kids[i:i + w]):
                    continue
                new = deep_copy(t)
                nk = list(_node(new, q).children)
                nk[i:i + w] = [par(*nk[i:i + w])]
                _set_children(_node(new, q), nk)
                labs = tuple(c.label for c in kids[i:i + w])
                _emit(out, "seq_to_par", 0, t, new, w, q + (i,), w,
                      f"{', '.join(labs)} become parallel", touched=set(labs), op=("par",) + labs)


def _joins(t, out):
    for q in _operator_paths(t, SEQ):
        kids = _node(t, q).children
        for i, c in enumerate(kids):
            if not is_leaf(c):
                continue
            for j in (i - 1, i + 1):
                if not (0 <= j < len(kids)) or is_leaf(kids[j]) or kids[j].op != PAR:
                    continue
                lo, hi = min(i, j), max(i, j)
                new = deep_copy(t)
                nk = list(_node(new, q).children)
                nk[lo:hi + 1] = [par(*nk[lo:hi + 1])]
                _set_children(_node(new, q), nk)
                _emit(out, "joins", 0, t, new, len(kids[j].children) + 1, q + (i,), 1,
                      f"{c.label} joins {tree_str(kids[j])}",
                      touched={c.label} | {x.label for x in _leaves(kids[j])},
                      op=("join", c.label, j - i))


def _nesting(t, out, smallest=False):
    for q in _operator_paths(t, PAR):
        kids = _node(t, q).children
        if not all(is_leaf(c) for c in kids):
            continue                                   # a block holds at most one ordered chain
        for w in range(2, min(3, len(kids)) if smallest else len(kids)):  # the whole block: seq_to_par reversed
            for combo in itertools.combinations(range(len(kids)), w):
                new = deep_copy(t)
                nk = list(_node(new, q).children)
                chain = seq(*[nk[i] for i in combo])
                _set_children(_node(new, q), [c for i, c in enumerate(nk) if i not in combo] + [chain])
                labs = tuple(kids[i].label for i in combo)
                _emit(out, "nesting", 0, t, new, w, q + (combo[0],), 1,
                      f"{', '.join(labs)} become ordered inside the block",
                      touched=set(labs), op=("chain",) + labs)


def _alongside(t, out, smallest=False):
    for q in _operator_paths(t, SEQ):
        kids = _node(t, q).children
        for i, c in enumerate(kids):
            if not is_leaf(c):
                continue
            for lo, hi in ([(i, j) for j in range(i + 2, len(kids))]            # chain after it
                           + [(j, i) for j in range(0, i - 1)]):                # chain before it
                if smallest and hi - lo != 2:
                    continue
                chain = [x for k, x in enumerate(kids[lo:hi + 1], lo) if k != i]
                new = deep_copy(t)
                nk = list(_node(new, q).children)
                nk[lo:hi + 1] = [par(deep_copy(c), seq(*[deep_copy(x) for x in chain]))]
                _set_children(_node(new, q), nk)
                _emit(out, "alongside", 0, t, new, len(chain), q + (i,), 1,
                      f"{c.label} runs alongside {len(chain)}",
                      touched={c.label} | {x.label for x in chain},
                      op=("alongside", c.label, tuple(x.label for x in chain), "after" if lo == i else "before"))


def _emit(out, name, delta, base, new, size, p, width, where, touched=(), op=()):
    new = canonicalize(new)                            # lift, collapse; None if the grammar breaks
    if new is None or canon(new) == canon(base):
        return
    if n_leaves(new) != n_leaves(base) + delta:
        return          # variant_enumeration.canonicalize drops an invalid subtree instead of refusing
    out.append(Edit(name, base, order(new), size, _position(base, p, width),
                    max(len(p) - 1, 0), where, frozenset(touched), tuple(op), _slot(base, p)))


# ---------------------------------------------------------------------------
# Paths: one edit grown step by step at one place of a tree
# ---------------------------------------------------------------------------


def paths_on(t, thin: bool = False) -> dict[tuple, list[Edit]]:
    """Every path on tree *t*.  A place is a sequence of *t* and an anchor in it (its first,
    middle or last child), or, for nesting, a block of activities.  Along a path the edit grows
    by one step at a time from the anchor and everything else is held fixed, so each step
    contains the previous one's change.  With *thin*, only the steps of size 1, 2, 4, 8, ... and
    the largest.  Keys: (edit, node path, anchor)."""
    t = order(t)
    used = {c.label for c in _leaves(t)}
    fresh = [f"z{i}" for i in range(1, 200) if f"z{i}" not in used]
    out: dict[tuple, list[Edit]] = {}

    def add(key, new, size, p, where, delta=0, width=1):
        new = canonicalize(new)
        if new is None or canon(new) == canon(t) or n_leaves(new) != n_leaves(t) + delta:
            return False
        out.setdefault(key, []).append(Edit(key[0], t, order(new), size, _position(t, p, width),
                                            max(len(p) - 1, 0), where))
        return True

    def with_kids(q, kids):
        new = deep_copy(t)
        _set_children(_node(new, q), [deep_copy(k) for k in kids])
        return new

    for q in _operator_paths(t, SEQ):
        kids = _node(t, q).children
        K = len(kids)
        for pos, a in (("start", 0), ("middle", K // 2), ("end", K - 1)):
            if not is_leaf(kids[a]):
                continue
            lab = kids[a].label
            step = -1 if pos == "end" else 1
            # move: the anchor's activity moves k slots toward the other end
            for k in range(1, (a if pos == "end" else K - 1 - a) + 1):
                nk = list(kids)
                nk.insert(a + step * k, nk.pop(a))
                add(("move", q, pos), with_kids(q, nk), k, q + (a,), f"{lab} moves {k}")
            # missing / relabel / seq_to_par: a run of the sequence's activities from the anchor
            for m in range(1, K):
                ix = _grow(K, pos, m)
                if not all(is_leaf(kids[i]) for i in ix):
                    break
                if m < K:
                    add(("missing", q, pos), with_kids(q, [c for i, c in enumerate(kids) if i not in ix]),
                        m, q + (ix[0],), f"{m} missing", delta=-m, width=m)
                rel = [leaf(fresh[ix.index(i)]) if i in ix else c for i, c in enumerate(kids)]
                add(("relabel", q, pos), with_kids(q, rel), m, q + (ix[0],), f"{m} relabelled",
                    width=m)
                if m >= 2:
                    blk = [c for i, c in enumerate(kids) if i < ix[0]] + [par(*[deep_copy(kids[i]) for i in ix])] \
                          + [c for i, c in enumerate(kids) if i > ix[-1]]
                    add(("seq_to_par", q, pos), with_kids(q, blk), m, q + (ix[0],),
                        f"{m} become parallel", width=m)
            # repetition: the anchor's activity occurs r more times, next to itself
            for r in range(1, K):
                nk = kids[:a + 1] + [leaf(lab) for _ in range(r)] + kids[a + 1:]
                add(("repetition", q, pos), with_kids(q, nk), r, q + (a,), f"{lab} {r + 1} times",
                    delta=r)
            # alongside: the anchor's activity runs alongside a growing chain next to it; below
            # the root the chain leaves one child out, or the new block would merge with the
            # block around this sequence
            for w in range(2, K if not q else K - 1):
                chain = list(range(a + 1, a + 1 + w)) if pos != "end" else list(range(a - w, a))
                if chain[0] < 0 or chain[-1] >= K:
                    break
                lo, hi = min(chain + [a]), max(chain + [a])
                nk = kids[:lo] + [par(deep_copy(kids[a]), seq(*[deep_copy(kids[j]) for j in chain]))] \
                    + kids[hi + 1:]
                add(("alongside", q, pos), with_kids(q, nk), w, q + (a,), f"{lab} runs alongside {w}")
        # joins: a block in this sequence takes in its neighbours, one at a time
        for b, blk in enumerate(kids):
            if is_leaf(blk) or blk.op != PAR:
                continue
            for side, rng_ in (("right", range(b + 1, K)), ("left", range(b - 1, -1, -1))):
                taken = []
                for j in rng_:
                    if not is_leaf(kids[j]):
                        break
                    taken.append(j)
                    lo, hi = min(taken + [b]), max(taken + [b])
                    grown = par(*[deep_copy(c) for c in blk.children], *[deep_copy(kids[i]) for i in taken])
                    nk = kids[:lo] + [grown] + kids[hi + 1:]
                    add(("joins", q + (b,), side), with_kids(q, nk), len(taken), q + (b,),
                        f"block takes in {len(taken)} ({side})")
    # nesting: a block's activities become an ordered chain inside it, one more at a time
    for q in _operator_paths(t, PAR):
        kids = _node(t, q).children
        if not all(is_leaf(c) for c in kids) or len(kids) < 3:
            continue
        for w in range(2, len(kids)):
            nk = [deep_copy(c) for c in kids[w:]] + [seq(*[deep_copy(c) for c in kids[:w]])]
            add(("nesting", q, "block"), with_kids(q, nk), w, q, f"{w} ordered inside the block")
    if thin:
        out = {k: [e for i, e in enumerate(v) if e.size & (e.size - 1) == 0 or i == len(v) - 1]
               for k, v in out.items()}
    return {k: v for k, v in out.items() if v}


def _grow(n: int, position: str, m: int) -> list[int]:
    """m contiguous indices of a sequence of n, anchored at *position*."""
    if position == "start":
        return list(range(m))
    if position == "end":
        return list(range(n - m, n))
    lo = max(0, min(n // 2 - m // 2, n - m))
    return list(range(lo, lo + m))


# ---------------------------------------------------------------------------
# Tree plumbing
# ---------------------------------------------------------------------------


def _node(t, p):
    for i in p:
        t = t.children[i]
    return t


def _paths(t, p=()):
    yield p
    if not is_leaf(t):
        for i, c in enumerate(t.children):
            yield from _paths(c, p + (i,))


def _leaf_paths(t):
    return [p for p in _paths(t) if is_leaf(_node(t, p))]


def _operator_paths(t, op):
    return [p for p in _paths(t) if not is_leaf(_node(t, p)) and _node(t, p).op == op]


def _leaves(t):
    return [_node(t, p) for p in _leaf_paths(t)]


def _set_children(node, children):
    node.children = list(children)
    for c in node.children:
        c.parent = node


def _position(t, p, width) -> str:
    """Slot of the node at *p* (and *width*-1 siblings after it) in its sequence."""
    while p and _node(t, p[:-1]).op == PAR:
        p, width = p[:-1], 1                           # inside a block: the block's slot
    if not p:
        return "whole"
    i, k = p[-1], len(_node(t, p[:-1]).children)
    first, last = i == 0, i + width == k
    return "whole" if first and last else "start" if first else "end" if last else "middle"


def _slot(t, p) -> tuple:
    """(slot, children) of the node at *p* in its sequence, a node inside a block taking the
    block's slot; () for the whole variant."""
    while p and _node(t, p[:-1]).op == PAR:
        p = p[:-1]
    return (p[-1], len(_node(t, p[:-1]).children)) if p else ()


def _fresh(t) -> str:
    used = {c.label for c in _leaves(t)}
    return next(a for a in ("Z", "Y", "W", "V") if a not in used)


__all__ = ["EDITS", "FULL_UP_TO", "PLACES", "POSITIONS", "Edit", "depth_of", "kept_slots", "n_leaves",
           "order", "paths_on", "shapes", "single_edits"]
