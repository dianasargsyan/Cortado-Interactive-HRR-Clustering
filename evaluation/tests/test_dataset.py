"""
evaluation/dataset.py builds the synthetic dataset exactly: the rule's shapes and their counts per
length, the repeat versions (same shape, at least three different activities), the loop paths
(copies s places apart), the sizes per length and the all-pairs sample at 9.
"""

from __future__ import annotations

from collections import Counter

import pytest

from evaluation import dataset as DS
from evaluation import probe_sets, probes, synthetic
from rotation_hrr.variant_enumeration import PAR, SEQ, canon, is_valid, n_leaves, shape_sig

RULE_COUNTS = {6: 11, 9: 16, 12: 28, 15: 30, 20: 46, 30: 56, 45: 60, 65: 60}
BLOCK_SIZES = {12: [2, 3, 6], 15: [2, 3, 7], 20: [2, 5, 10], 30: [2, 3, 7, 15],
               45: [2, 5, 11, 22], 65: [2, 8, 16, 32]}
DEPTHS = {12: [2, 3, 4], 15: [2, 3, 4], 20: [2, 3, 4, 8], 30: [2, 3, 4, 8], 45: [2, 3, 4, 8],
          65: [2, 3, 4, 8]}


@pytest.mark.parametrize("n", sorted(RULE_COUNTS))
def test_d1_rule_counts(n):
    assert len(DS.rule_shapes(n)) == RULE_COUNTS[n]


@pytest.mark.parametrize("n", sorted(BLOCK_SIZES))
def test_d2_block_sizes_and_depths(n):
    assert DS.block_sizes(n) == BLOCK_SIZES[n]
    assert DS.rule_depths(n) == DEPTHS[n]


def _blocks(t):
    return [c for c in t.children if c.label is None] if t.label is None else []


@pytest.mark.parametrize("n", sorted(RULE_COUNTS))
def test_d3_rule_shapes_are_what_their_family_says(n):
    shapes = DS.rule_shapes(n)
    assert len({canon(t) for _, t in shapes}) == len(shapes)
    for fam, t in shapes:
        assert n_leaves(t) == n and DS.different(t) == n and is_valid(t)
        d, words = probes.depth_of(t), fam.split()
        if fam.startswith("all in"):
            assert d == 0
        elif fam.endswith("alongside a sequence"):
            w = int(words[0])
            assert t.op == PAR and sum(c.label is not None for c in t.children) == w
            assert [n_leaves(c) for c in _blocks(t)] == [n - w]
        elif fam == "one block of each width":
            assert sorted(len(b.children) for b in _blocks(t)) == DS.block_sizes(n)
        elif fam == "one nest of each depth":
            assert sorted(probes.depth_of(b) + 1 for b in _blocks(t)) == DS.rule_depths(n)
        elif fam == "one depth-2 nest of each form":
            assert d == 2 and len(_blocks(t)) > 1
        elif "nest" in fam:
            k, depth = int(words[0]), int(words[-1])
            form = " ".join(words[1:words.index("of") - 1]) or "smallest"
            assert d == depth and len(_blocks(t)) == k
            assert all(n_leaves(b) == DS.nest_size(depth, *DS.nest_widths(n, form)) for b in _blocks(t))
        else:
            k, w = int(words[0]), int(words[-1])
            assert d == 1 and len(_blocks(t)) == k and all(len(b.children) == w for b in _blocks(t))


@pytest.mark.parametrize("form", DS.NEST_FORMS)
@pytest.mark.parametrize("d", DS.RULE_DEPTHS)
def test_d3b_nest_forms(form, d):
    """Blocks hold w activities and chains c steps besides the next level, at every level."""
    w, c = DS.nest_widths(40, form)
    t = DS._nest(d, w, c, DS.labels(DS.nest_size(d, w, c)))
    assert n_leaves(t) == DS.nest_size(d, w, c) and is_valid(t)
    level, node = 1, t
    while True:
        leaves = sum(x.label is not None for x in node.children)
        inner = [x for x in node.children if x.label is None]
        assert node.op == (PAR if level % 2 else SEQ)
        if level == d:
            assert leaves == (w if level % 2 else c) + 1 and not inner
            break
        assert leaves == (w if level % 2 else c) and len(inner) == 1
        node, level = inner[0], level + 1


def test_d3c_the_smallest_nests_are_the_old_rule():
    """With one activity per level, a nest is the smallest of its depth: d + 1 activities."""
    for d in DS.RULE_DEPTHS:
        assert DS.nest_size(d, 1, 1) == d + 1


@pytest.mark.parametrize("n", [6, 9, 12, 65])
def test_d4_repeat_versions_keep_the_shape(n):
    for i, (_, t) in enumerate(DS.base_shapes(n)):
        if i % 50:
            continue
        versions = DS.repeat_versions(t)
        assert [v for v, _ in versions] == list(DS.VERSIONS[:6 if n < DS.HEAVY_FROM else 8])
        for name, v in versions:
            assert shape_sig(v) == shape_sig(t) and n_leaves(v) == n
            assert DS.different(v) >= DS.MIN_DIFFERENT
            assert DS.extra_copies(v) == {"loop": 1, "middle": 1, "far": 1, "loop+1": 2, "middle+1": 2,
                                          "far+1": 2, "quarter": n // 4, "half": n // 2}[name]


def test_d5_three_activity_rule_drops_small_versions():
    t = probes.shapes(4)[0]                                   # ->(A, B, C, D)
    assert [v for v, _ in DS.repeat_versions(t)] == ["loop", "middle", "far"]


@pytest.mark.parametrize("n", [6, 9, 12])
def test_d6_loop_paths(n):
    for i, (_, t) in enumerate(DS.base_shapes(n)):
        if i % 40:
            continue
        a = DS._leaves(DS._with_labels(t))[0].label
        for c, steps in DS.loop_paths(t).items():
            assert [s for s, _ in steps] == list(range(1, len(steps) + 1))
            for s, v in steps:
                assert n_leaves(v) == n + c and Counter(x.label for x in DS._leaves(v))[a] == c + 1


def test_d7_loop_spacing_on_a_sequence():
    from rotation_hrr.variant_enumeration import leaf, seq
    t = seq(*[leaf(x) for x in "ABCDEF"])
    for c, steps in DS.loop_paths(t).items():
        for s, v in steps:
            pos = [k for k, x in enumerate(DS._leaves(v)) if x.label == "A"]
            assert pos == [k * s for k in range(c + 1)]


def test_d8_sizes():
    assert [len(DS.variants(n)) for n in DS.UNIVERSE] == [7, 100, 2279]
    assert len(DS.variants(6)) == 132 * 7
    assert {n: len(DS.variants(n)) for n in DS.RULE} == {n: 9 * RULE_COUNTS[n] for n in DS.RULE}


def test_d9_sample_at_9():
    S = DS.sample_9()
    shapes = {i for i, *_ in S}
    by_depth = Counter(probes.depth_of(DS.base_shapes(9)[i][1]) for i in shapes)
    assert by_depth == {0: 2, **{d: DS.SAMPLE_9_PER_DEPTH for d in range(1, 8)}}
    assert len(S) == 7 * len(shapes)
    assert DS.sample_9() == S                                  # the same draw every time


def test_d10_corpora_and_bins():
    assert synthetic.names() == ["universe_4"] + [f"length_{n}" for n in DS.LENGTHS]
    assert len(synthetic.load("universe_4").trees) == 2386
    assert len(synthetic.load("length_12").trees) == 9 * RULE_COUNTS[12]
    assert probe_sets.length_bins() == {6: (6, 6), 9: (9, 9), 12: (11, 13), 15: (14, 17),
                                        20: (18, 24), 30: (25, 36), 45: (37, 54), 65: (55, 10 ** 6)}
