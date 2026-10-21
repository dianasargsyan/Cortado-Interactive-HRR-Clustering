"""
Concurrency trees as positioned activities.

Cortado's trees alternate sequences and parallel blocks, and a parallel block has at most one
sequence child.  A Fallthrough node is read as a parallel block: Cortado makes one when part of a
partial order is neither a sequence nor a parallel block (overlapping intervals) and lists its
activities alphabetically, so their order is already lost.  Read as a sequence, the names would
set the order and renaming an activity would change the vector.  A Loop node is read as a
sequence (none of the logs has one).
"""

from __future__ import annotations

from cortado_core.subprocess_discovery.concurrency_trees.cTrees import ConcurrencyTree, cTreeOperator

_PARALLEL = (cTreeOperator.Concurrent, cTreeOperator.Fallthrough)


def _count_leaves(tree: ConcurrencyTree) -> int:
    if tree.label is not None:
        return 1
    return sum(_count_leaves(c) for c in tree.children)


def tree_to_positioned_sequence(tree: ConcurrencyTree, _start: float = 0.0, _depth: int = 0,
                                _scale: float = 1.0) -> tuple[list[tuple[str, float, int]], int]:
    """Every activity with its position and depth: ([(label, position, depth)], leaf count).

    Depth counts the operator nodes between the root and the activity: the root's own leaves are
    at depth 0, and every step into an operator child adds one.

        ->(A, B, C)              A, B, C at 0
        ->(A, /\\(B, C))          A at 0; B, C at 1
        /\\(A, ->(B, /\\(C, D)))    A at 0, B at 1, C, D at 2

    Position is the activity's average place (from 0) over every order the variant allows, each
    order counted once.  Two exact rules map a child's own places into its parent's:

    - in a sequence, a child's places move up by the number of activities before it;
    - in a parallel block of N activities, a child with n activities takes a uniformly random n
      of the N places, whatever its own order, so its place q maps to (q + 1)(N + 1)/(n + 1) - 1,
      the mean of the (q + 1)-th smallest of n places drawn from N.  A single activity lands on
      the block's centre, (N - 1)/2.

    Both maps are affine, so each subtree reaches the variant through one map, carried down as
    (_start, _scale).  ValueError if a parallel block has more than one sequence child.
    """
    if tree.label is not None:
        return [(tree.label, float(_start), _depth)], 1

    if tree.op in _PARALLEL:
        if sum(c.op == cTreeOperator.Sequential for c in tree.children) > 1:
            raise ValueError("a parallel block has more than one sequence child")
        counts = [_count_leaves(c) for c in tree.children]
        N = sum(counts)
        items: list[tuple[str, float, int]] = []
        for child, n in zip(tree.children, counts):
            s = (N + 1) / (n + 1)
            child_items, _ = tree_to_positioned_sequence(
                child, _start=_start + _scale * (s - 1),
                _depth=_depth if child.label is not None else _depth + 1, _scale=_scale * s)
            items.extend(child_items)
        return items, N

    items = []
    pos = 0
    for child in tree.children:
        child_items, n = tree_to_positioned_sequence(
            child, _start=_start + _scale * pos,
            _depth=_depth if child.label is not None else _depth + 1, _scale=_scale)
        items.extend(child_items)
        pos += n
    return items, pos


def tree_to_sequence(tree: ConcurrencyTree) -> list[str]:
    """The activities left to right; in a parallel block the activities sorted by repr and the
    sequence child last.  The linear form the sequence baselines read."""
    if tree.label is not None:
        return [tree.label]
    children = tree.children
    if tree.op in _PARALLEL:
        children = (sorted((c for c in children if c.op != cTreeOperator.Sequential), key=repr)
                    + [c for c in children if c.op == cTreeOperator.Sequential])
    return [a for c in children for a in tree_to_sequence(c)]
