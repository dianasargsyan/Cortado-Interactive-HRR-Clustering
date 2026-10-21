"""
variant_enumeration.py and the encoder on every small tree.

The main check: an independent enumerator, every tree reachable from one start by single edits
(turn an operator, swap two neighbours in a sequence, rename, delete or repeat an activity, change
the nesting), run until it finds nothing new, reaches exactly the trees full_enumeration lists.
So full_enumeration, and the universe built on it, misses no tree.
"""

from __future__ import annotations

import pytest

from rotation_hrr.encoder import RotationHRREncoder
from rotation_hrr.variant_enumeration import (PAR, SEQ, canon, canonicalize, deep_copy, full_enumeration,
                                 is_leaf, is_valid, leaf, n_leaves, par, seq)
from cortado_core.subprocess_discovery.concurrency_trees.cTrees import ConcurrencyTree


def _paths(t, path=()):
    """(operator paths, leaf paths) of *t*."""
    if is_leaf(t):
        return [], [path]
    ops, leaves = [path], []
    for i, c in enumerate(t.children):
        o, lv = _paths(c, path + (i,))
        ops += o
        leaves += lv
    return ops, leaves


def _node(t, path):
    for i in path:
        t = t.children[i]
    return t


def _flips(t, alphabet):
    out = []
    for p in _paths(t)[0]:
        new = deep_copy(t)
        n = _node(new, p)
        n.op = PAR if n.op == SEQ else SEQ
        out.append(canonicalize(new))
    return out


def _nestings(t, alphabet):
    """A run of 2 to k - 1 adjacent children wrapped in the other operator, or a child of the
    other operator lifted into its parent."""
    out = []
    for p in _paths(t)[0]:
        ref = _node(t, p)
        opp = PAR if ref.op == SEQ else SEQ
        k = len(ref.children)
        for size in range(2, k):
            for i in range(k - size + 1):
                new = deep_copy(t)
                n = _node(new, p)
                window = n.children[i:i + size]
                wrapped = ConcurrencyTree(children=list(window), op=opp)
                for c in window:
                    c.parent = wrapped
                n.children[i:i + size] = [wrapped]
                wrapped.parent = n
                out.append(canonicalize(new))
        for i, c in enumerate(ref.children):
            if is_leaf(c) or c.op != opp:
                continue
            new = deep_copy(t)
            n = _node(new, p)
            kids = n.children[i].children
            n.children[i:i + 1] = kids
            for g in kids:
                g.parent = n
            out.append(canonicalize(new))
    return out


def _swaps(t, alphabet):
    out = []
    for p in _paths(t)[0]:
        if _node(t, p).op != SEQ:
            continue
        for i in range(len(_node(t, p).children) - 1):
            new = deep_copy(t)
            kids = _node(new, p).children
            kids[i], kids[i + 1] = kids[i + 1], kids[i]
            out.append(canonicalize(new))
    return out


def _renames(t, alphabet):
    out = []
    for p in _paths(t)[1]:
        for a in alphabet:
            if a != _node(t, p).label:
                new = deep_copy(t)
                _node(new, p).label = a
                out.append(canonicalize(new))
    return out


def _deletes(t, alphabet):
    out = []
    for p in _paths(t)[1]:
        if p:
            new = deep_copy(t)
            del _node(new, p[:-1]).children[p[-1]]
            out.append(canonicalize(new))
    return out


def _repeats(t, alphabet):
    out = []
    for p in _paths(t)[1]:
        if not p:
            out.append(canonicalize(seq(deep_copy(t), deep_copy(t))))
            continue
        new = deep_copy(t)
        parent = _node(new, p[:-1])
        copy = ConcurrencyTree(label=parent.children[p[-1]].label, op=None)
        copy.parent = parent
        parent.children.insert(p[-1] + 1, copy)
        out.append(canonicalize(new))
    return out


EDITS = {
    "flip": _flips,
    "swap": _swaps,
    "rename": _renames,
    "delete": _deletes,
    "repeat": _repeats,
    "nesting": _nestings,
}


def reachable(base, alphabet, max_size) -> set[str]:
    """canon() of every tree reachable from *base* by single edits, up to *max_size* activities."""
    seen, frontier = {canon(base)}, [base]
    while frontier:
        nxt = []
        for t in frontier:
            for edit in EDITS.values():
                for u in edit(t, alphabet):
                    if u is None or n_leaves(u) > max_size or canon(u) in seen:
                        continue
                    seen.add(canon(u))
                    nxt.append(u)
        frontier = nxt
    return seen


BASES = [
    seq(leaf("A"), leaf("B")),
    seq(leaf("A"), leaf("B"), leaf("C")),
    par(leaf("A"), leaf("B")),
    par(leaf("A"), leaf("B"), leaf("C")),
    seq(leaf("A"), par(leaf("B"), leaf("C"))),
    par(leaf("A"), seq(leaf("B"), leaf("C"))),
    seq(leaf("A"), par(leaf("B"), leaf("C")), leaf("D")),
]


@pytest.mark.parametrize("base", BASES, ids=lambda t: canon(t))
@pytest.mark.parametrize("name", list(EDITS))
def test_every_edit_gives_a_valid_tree(base, name):
    for u in EDITS[name](base, ["A", "B", "C", "D"]):
        assert u is None or is_valid(u), f"{name} on {canon(base)} gave {canon(u)}"


def test_canon_ignores_the_order_inside_a_block():
    assert canon(par(leaf("A"), leaf("B"))) == canon(par(leaf("B"), leaf("A")))


def test_canon_keeps_the_order_of_a_sequence():
    assert canon(seq(leaf("A"), leaf("B"))) != canon(seq(leaf("B"), leaf("A")))


@pytest.mark.parametrize("n,alphabet,start", [
    (2, ["A", "B"], lambda: seq(leaf("A"), leaf("B"))),
    (3, ["A", "B", "C"], lambda: seq(leaf("A"), leaf("B"), leaf("C"))),
    (3, ["A", "B"], lambda: seq(leaf("A"), leaf("B"))),
], ids=["N2_AB", "N3_ABC", "N3_AB"])
def test_single_edits_reach_exactly_the_full_enumeration(n, alphabet, start):
    reached = reachable(start(), alphabet, n)
    direct = {canon(t) for t in full_enumeration(n, alphabet)}
    assert reached == direct, (f"missed {sorted(direct - reached)[:5]}, "
                               f"extra {sorted(reached - direct)[:5]}")


@pytest.mark.parametrize("n,alphabet,count", [
    (1, ["A", "B"], 2), (2, ["A", "B"], 9), (3, ["A", "B"], 41), (3, ["A", "B", "C"], 118),
])
def test_full_enumeration_counts(n, alphabet, count):
    assert len(full_enumeration(n, alphabet)) == count


@pytest.fixture(scope="module")
def encoder():
    return RotationHRREncoder(d=512, n_max=100, seed=42)


def test_a_tree_is_identical_to_itself(encoder):
    for t in full_enumeration(3, ["A", "B", "C"]):
        b = encoder.encode_tree(t, alpha=1.0, beta=1.0)
        assert encoder.similarity(b, b) >= 0.9999, canon(t)


def _first_par(node, path=()):
    if is_leaf(node):
        return None
    if node.op == PAR:
        return path
    for i, c in enumerate(node.children):
        found = _first_par(c, path + (i,))
        if found is not None:
            return found
    return None


def test_the_order_inside_a_block_does_not_change_the_vector(encoder):
    fails = []
    for t in full_enumeration(4, ["A", "B"]):
        path = _first_par(t)
        if path is None:
            continue
        swapped = deep_copy(t)
        node = _node(swapped, path)
        node.children[0], node.children[1] = node.children[1], node.children[0]
        sim = encoder.similarity(encoder.encode_tree(t), encoder.encode_tree(swapped))
        if sim < 0.999:
            fails.append((canon(t), sim))
    assert not fails, fails[:5]
