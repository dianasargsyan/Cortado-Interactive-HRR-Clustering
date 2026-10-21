"""
Rewrites of concurrency trees: Cortado's variants as sorted trees, renaming activities, removing
activities.  Every function returns a new tree and leaves its input unchanged.
"""

from __future__ import annotations

from cortado_core.subprocess_discovery.concurrency_trees.cTrees import (
    ConcurrencyTree,
    cTreeFromcGroup,
    cTreeOperator,
)


def _leaf(label: str) -> ConcurrencyTree:
    return ConcurrencyTree(label=label, op=None)


def _node(op: cTreeOperator, children: list[ConcurrencyTree]) -> ConcurrencyTree:
    n = ConcurrencyTree(children=list(children), op=op)
    for c in children:
        c.parent = n
    return n


def _deep_copy(tree: ConcurrencyTree) -> ConcurrencyTree:
    if tree.label is not None:
        return _leaf(tree.label)
    return _node(tree.op, [_deep_copy(c) for c in tree.children])


def _sort_parallel_in_place(tree: ConcurrencyTree) -> None:
    for child in tree.children:
        _sort_parallel_in_place(child)
    if tree.op == cTreeOperator.Concurrent:
        seqs = sorted((c for c in tree.children if c.op == cTreeOperator.Sequential), key=repr)
        rest = sorted((c for c in tree.children if c.op != cTreeOperator.Sequential), key=repr)
        tree.children = rest + seqs


def sort_parallel(tree: ConcurrencyTree) -> ConcurrencyTree:
    """A copy with every parallel block's children in one fixed order: the activities sorted by
    repr, the sequence child last.  Order-sensitive methods (tree edit distance, pq-grams) then
    give a block the same answer however it was written."""
    t = _deep_copy(tree)
    _sort_parallel_in_place(t)
    return t


def groups_to_trees(groups: list) -> list[ConcurrencyTree]:
    """Cortado's variants (``Group`` objects, the keys of ``get_concurrency_variants``) as
    concurrency trees with every parallel block sorted."""
    trees = []
    for group in groups:
        g = group.sort()
        tree = cTreeFromcGroup(group=g, infix_type=g.infix_type)
        _sort_parallel_in_place(tree)
        trees.append(tree)
    return trees


def drop_activities(tree: ConcurrencyTree, ignored: set) -> ConcurrencyTree | None:
    """The tree without the activities in *ignored*, in normal form ("pretend it never
    happened"): the activities after a removed one move up, an operator left with one child is
    replaced by it, and a block left inside an operator of its own kind is merged into it, so
    →(A, ∧(X, →(B, C))) without X is →(A, B, C).  None if no activity is left."""
    if not ignored:
        return _deep_copy(tree)
    if tree.label is not None:
        return None if tree.label in ignored else _leaf(tree.label)
    kept = []
    for c in (drop_activities(ch, ignored) for ch in tree.children):
        if c is None:
            continue
        if c.label is None and c.op == tree.op:
            kept.extend(c.children)
        else:
            kept.append(c)
    if not kept:
        return None
    if len(kept) == 1:
        return kept[0]
    return _node(tree.op, kept)


def relabel(tree: ConcurrencyTree, mapping: dict) -> ConcurrencyTree:
    """A copy with every activity renamed through *mapping* (the others unchanged): "these two
    are the same"."""
    if tree.label is not None:
        return _leaf(mapping.get(tree.label, tree.label))
    return _node(tree.op, [relabel(c, mapping) for c in tree.children])
