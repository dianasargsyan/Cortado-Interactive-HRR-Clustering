"""
The orders a variant allows, as a reference for HRR's positions.

A variant is a partial order on its activities: in a sequence every activity of an earlier child
comes before every activity of a later one; in a parallel block the children are unordered.  The
orders it allows are the linear extensions of that partial order.  HRR places every activity at
its average place over those orders, each counted once.  This module computes that average
without the tree formula in rotation_hrr/tree_utils.py, only from which activity must come before
which.

  precedence(tree)       leaves in walk order, and for each the set that must come before it
                         (bit masks)
  mean_positions(tree)   exact average place of every leaf over every allowed order, as
                         Fractions, counted over the prefixes of the partial order (a standard
                         dynamic programme; integers throughout)
  all_orders(tree)       every allowed order, one by one (brute force; small trees)
  place_bounds(tree)     the earliest and latest place each leaf can take

Leaves are identified by their index in walk order, never by label, so repeated activities are
handled like any other.  Only sequences and parallel blocks are defined here; a Loop or
Fallthrough node raises.
"""

from __future__ import annotations

from fractions import Fraction

from rotation_hrr.variant_enumeration import PAR, SEQ


def _leaf_paths(t, p=()):
    if t.label is not None:
        return [p]
    return [q for i, c in enumerate(t.children) for q in _leaf_paths(c, p + (i,))]


def _node(t, p):
    for i in p:
        t = t.children[i]
    return t


def precedence(tree) -> tuple[int, list[int]]:
    """(n, pred): pred[j] is the bit mask of the leaves that must come before leaf j."""
    paths = _leaf_paths(tree)
    n = len(paths)
    pred = [0] * n
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a, b = paths[i], paths[j]
            k = 0
            while a[k] == b[k]:
                k += 1
            op = _node(tree, a[:k]).op
            if op == SEQ:
                if a[k] < b[k]:
                    pred[j] |= 1 << i
            elif op != PAR:
                raise NotImplementedError(f"operator {op} has no order semantics here")
    return n, pred


def mean_positions(tree) -> list[Fraction]:
    """Exact average place (0-based) of every leaf over every order the variant allows.

    f[S]: orders of the prefix S (a set closed under `pred`); g[S]: ways to finish
    after S.  Leaf j stands at place |S| in f[S] * g[S + j] orders, for every prefix
    S that j can follow.
    """
    n, pred = precedence(tree)
    full = (1 << n) - 1
    f = {0: 1}
    layers = [[0]]
    for _ in range(n):
        nxt: dict[int, int] = {}
        for S in layers[-1]:
            for j in range(n):
                if not S >> j & 1 and pred[j] & S == pred[j]:
                    nxt[S | 1 << j] = nxt.get(S | 1 << j, 0) + f[S]
        f.update(nxt)
        layers.append(list(nxt))
    g = {full: 1}
    for layer in reversed(layers[:-1]):
        for S in layer:
            g[S] = sum(g[S | 1 << j] for j in range(n)
                       if not S >> j & 1 and pred[j] & S == pred[j])
    total = f[full]
    num = [0] * n
    for size, layer in enumerate(layers[:-1]):
        for S in layer:
            for j in range(n):
                if not S >> j & 1 and pred[j] & S == pred[j]:
                    num[j] += size * f[S] * g[S | 1 << j]
    return [Fraction(x, total) for x in num]


def all_orders(tree):
    """Every order the variant allows, as tuples of leaf indices (brute force)."""
    n, pred = precedence(tree)

    def extend(S, order):
        if len(order) == n:
            yield tuple(order)
            return
        for j in range(n):
            if not S >> j & 1 and pred[j] & S == pred[j]:
                order.append(j)
                yield from extend(S | 1 << j, order)
                order.pop()

    yield from extend(0, [])


def place_bounds(tree) -> list[tuple[int, int]]:
    """(earliest, latest) place of every leaf: how many must come before it, and after."""
    n, pred = precedence(tree)
    after = [sum(1 for k in range(n) if pred[k] >> j & 1) for j in range(n)]
    return [(bin(pred[j]).count("1"), n - 1 - after[j]) for j in range(n)]


# ---------------------------------------------------------------------------
# Checks on positions (tests/test_positions.py, evaluation/experiments/21_positions.py)
# ---------------------------------------------------------------------------

TOL = 1e-12


def violations(tree, items) -> dict:
    """What is wrong with *items* ((label, position, depth) per leaf, in walk order)."""
    n, pred = precedence(tree)
    p = [x[1] for x in items]
    return {
        "max_error": max(abs(a - float(b)) for a, b in zip(p, mean_positions(tree))),
        "order": sum(1 for j in range(n) for i in range(n)
                     if pred[j] >> i & 1 and not p[i] < p[j]),
        "bounds": sum(1 for a, (lo, hi) in zip(p, place_bounds(tree))
                      if not lo - TOL <= a <= hi + TOL),
    }


def backwards(tree):
    """The same variant read backwards in time: every sequence's children reversed."""
    from rotation_hrr.variant_enumeration import deep_copy
    t = deep_copy(tree)
    stack = [t]
    while stack:
        node = stack.pop()
        if node.label is None:
            if node.op == SEQ:
                node.children.reverse()
            stack.extend(node.children)
    return t


def written_forms(tree):
    """Every way of writing the variant: each block's children in every order."""
    import itertools
    from rotation_hrr.variant_enumeration import deep_copy, par, seq
    if tree.label is not None:
        yield tree
        return
    for kids in itertools.product(*[list(written_forms(c)) for c in tree.children]):
        for order in (itertools.permutations(kids) if tree.op == PAR else [kids]):
            yield (par if tree.op == PAR else seq)(*[deep_copy(k) for k in order])


def leaf_depths(tree) -> list[int]:
    """Operators strictly between the root and each leaf (0 directly under the root)."""
    return [max(len(p) - 1, 0) for p in _leaf_paths(tree)]
