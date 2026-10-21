"""
Building, normalising and enumerating concurrency trees.

Trees follow Cortado's grammar: sequences and parallel blocks alternate (no sequence directly
inside a sequence, no block directly inside a block), and a parallel block has at most one
sequence child.  ``canonicalize`` restores the grammar after an edit, ``canon`` gives a key that
is the same for trees that differ only in the order of a block's children, and
``full_enumeration`` lists every tree up to a size.
"""

from __future__ import annotations

import itertools
from collections import Counter
from typing import Iterable

from cortado_core.subprocess_discovery.concurrency_trees.cTrees import ConcurrencyTree, cTreeOperator

SEQ = cTreeOperator.Sequential
PAR = cTreeOperator.Concurrent

OP_SYM = {SEQ: "→", PAR: "∧"}


def leaf(label: str) -> ConcurrencyTree:
    return ConcurrencyTree(label=label, op=None)


def seq(*children: ConcurrencyTree) -> ConcurrencyTree:
    n = ConcurrencyTree(children=list(children), op=SEQ)
    for c in children:
        c.parent = n
    return n


def par(*children: ConcurrencyTree) -> ConcurrencyTree:
    n = ConcurrencyTree(children=list(children), op=PAR)
    for c in children:
        c.parent = n
    return n


def deep_copy(t: ConcurrencyTree) -> ConcurrencyTree:
    if t.label is not None:
        return ConcurrencyTree(label=t.label, op=None)
    new = ConcurrencyTree(children=[], op=t.op)
    for c in t.children:
        nc = deep_copy(c)
        nc.parent = new
        new.children.append(nc)
    return new


def is_leaf(t: ConcurrencyTree) -> bool:
    return t.label is not None


def n_leaves(t: ConcurrencyTree) -> int:
    if is_leaf(t):
        return 1
    return sum(n_leaves(c) for c in t.children)


def tree_str(t: ConcurrencyTree) -> str:
    """The tree as written, e.g. →(A, ∧(B, C))."""
    if is_leaf(t):
        return t.label
    return f"{OP_SYM[t.op]}({', '.join(tree_str(c) for c in t.children)})"


def canon(t: ConcurrencyTree) -> str:
    """A key equal for trees that differ only in the order of a block's children."""
    if is_leaf(t):
        return t.label
    child_strs = [canon(c) for c in t.children]
    if t.op == PAR:
        child_strs.sort()
    return f"{OP_SYM[t.op]}({','.join(child_strs)})"


def shape_sig(t: ConcurrencyTree) -> str:
    """``canon`` with every label replaced by L: the tree's shape."""
    if is_leaf(t):
        return "L"
    child_strs = [shape_sig(c) for c in t.children]
    if t.op == PAR:
        child_strs.sort()
    return f"{OP_SYM[t.op]}({','.join(child_strs)})"


def is_valid(t: ConcurrencyTree) -> bool:
    """Whether the tree follows the grammar (no same-type nesting, at most one sequence in a
    block)."""
    if is_leaf(t):
        return True
    if not t.children:
        return False
    if t.op == PAR:
        if sum(1 for c in t.children if not is_leaf(c) and c.op == SEQ) > 1:
            return False
        if any((not is_leaf(c)) and c.op == PAR for c in t.children):
            return False
    if t.op == SEQ:
        if any((not is_leaf(c)) and c.op == SEQ for c in t.children):
            return False
    return all(is_valid(c) for c in t.children)


def canonicalize(t: ConcurrencyTree) -> ConcurrencyTree | None:
    """The tree in normal form: a child of the same type as its parent is merged into it, an
    operator with one child is replaced by the child, an empty operator disappears.  None if
    nothing is left or the result breaks the grammar."""
    if is_leaf(t):
        return deep_copy(t)
    new_children = []
    for c in t.children:
        cc = canonicalize(c)
        if cc is None:
            continue
        if (not is_leaf(cc)) and cc.op == t.op:
            new_children.extend(cc.children)
        else:
            new_children.append(cc)
    if not new_children:
        return None
    if len(new_children) == 1:
        return new_children[0]
    new = ConcurrencyTree(children=new_children, op=t.op)
    for c in new_children:
        c.parent = new
    if not is_valid(new):
        return None
    return new


def _ordered_partitions(n: int, min_parts: int = 2) -> Iterable[tuple[int, ...]]:
    """Every tuple of positive integers summing to n, with at least min_parts parts."""
    def rec(remaining: int, parts: tuple) -> Iterable[tuple]:
        if remaining == 0:
            if len(parts) >= min_parts:
                yield parts
            return
        for first in range(1, remaining + 1):
            yield from rec(remaining - first, parts + (first,))
    yield from rec(n, ())


def _unordered_partitions(n: int, min_parts: int = 2) -> Iterable[tuple[int, ...]]:
    """Every non-decreasing tuple of positive integers summing to n, with at least min_parts
    parts."""
    def rec(remaining: int, min_val: int, parts: tuple) -> Iterable[tuple]:
        if remaining == 0:
            if len(parts) >= min_parts:
                yield parts
            return
        for first in range(min_val, remaining + 1):
            yield from rec(remaining - first, first, parts + (first,))
    yield from rec(n, 1, ())


def _trees_of_size(n: int, allow_root: frozenset[str], alphabet: tuple[str, ...],
                   _cache: dict | None = None) -> list[ConcurrencyTree]:
    """Every tree with n activities whose root is one of allow_root ("leaf", "seq", "par"), one
    per ``canon`` key."""
    if _cache is None:
        _cache = {}
    key = (n, allow_root, alphabet)
    if key in _cache:
        return [deep_copy(t) for t in _cache[key]]   # copies, so a caller cannot change the cache

    out: dict[str, ConcurrencyTree] = {}

    if n == 1 and "leaf" in allow_root:
        for a in alphabet:
            t = leaf(a)
            out[canon(t)] = t

    if n >= 2:
        if "seq" in allow_root:           # a sequence's children: activities or blocks
            for partition in _ordered_partitions(n, min_parts=2):
                child_pools = [_trees_of_size(s, frozenset({"leaf"} if s == 1 else {"par"}), alphabet, _cache)
                               for s in partition]
                if any(not pool for pool in child_pools):
                    continue
                for combo in itertools.product(*child_pools):
                    t = seq(*[deep_copy(c) for c in combo])
                    k = canon(t)
                    if k not in out and is_valid(t):
                        out[k] = t

        if "par" in allow_root:           # a block's children: activities and at most one sequence
            for partition in _unordered_partitions(n, min_parts=2):
                gt1 = [s for s in partition if s > 1]
                if len(gt1) > 1:
                    continue
                num_leaves = sum(1 for s in partition if s == 1)
                seq_pool = (_trees_of_size(gt1[0], frozenset({"seq"}), alphabet, _cache)
                            if gt1 else [None])
                for seq_sub in seq_pool:
                    for combo in itertools.combinations_with_replacement(alphabet, num_leaves):
                        children = [leaf(a) for a in combo]
                        if seq_sub is not None:
                            children.append(deep_copy(seq_sub))
                        t = par(*children)
                        k = canon(t)
                        if k not in out and is_valid(t):
                            out[k] = t

    result = list(out.values())
    _cache[key] = [deep_copy(t) for t in result]
    return result


def full_enumeration(n_max: int, alphabet: list[str] | tuple[str, ...]) -> list[ConcurrencyTree]:
    """Every valid tree with 1 to n_max activities over *alphabet*, one per ``canon`` key."""
    alpha = tuple(alphabet)
    cache: dict = {}
    out: dict[str, ConcurrencyTree] = {}
    for n in range(1, n_max + 1):
        for t in _trees_of_size(n, frozenset({"leaf", "seq", "par"}), alpha, cache):
            out[canon(t)] = t
    return list(out.values())


def enumerate_shapes(n: int) -> list[ConcurrencyTree]:
    """Every shape with exactly n activities (all labelled X)."""
    return [t for t in full_enumeration(n, ["X"]) if n_leaves(t) == n]


def _leaf_slots(t: ConcurrencyTree) -> list[ConcurrencyTree]:
    """The leaves in stored left-to-right order."""
    if is_leaf(t):
        return [t]
    return [x for c in t.children for x in _leaf_slots(c)]


def label_shape_with_multiset(skeleton: ConcurrencyTree, target: dict[str, int] | Counter) -> list[ConcurrencyTree]:
    """Every distinct valid tree with the labels of *target* (label -> count) on the leaves of
    *skeleton*.  ``canon`` removes assignments that differ only inside a block."""
    items = [label for label, count in sorted(target.items()) for _ in range(count)]
    if len(items) != len(_leaf_slots(skeleton)):
        raise ValueError(f"{len(items)} labels for {len(_leaf_slots(skeleton))} leaves")
    seen: dict[str, ConcurrencyTree] = {}
    for perm in set(itertools.permutations(items)):
        new_tree = deep_copy(skeleton)
        for slot, label in zip(_leaf_slots(new_tree), perm):
            slot.label = label
        k = canon(new_tree)
        if k not in seen and is_valid(new_tree):
            seen[k] = new_tree
    return list(seen.values())


def full_enumeration_fixed_multiset(n: int, target: dict[str, int] | Counter) -> list[ConcurrencyTree]:
    """Every valid tree with exactly the activities of *target* (label -> count, summing to n):
    every shape, every arrangement."""
    if sum(target.values()) != n:
        raise ValueError(f"the counts sum to {sum(target.values())}, not {n}")
    out: dict[str, ConcurrencyTree] = {}
    for shape in enumerate_shapes(n):
        for t in label_shape_with_multiset(shape, target):
            out[canon(t)] = t
    return list(out.values())
