"""
The probe-tree generator (evaluation/probes.py) builds what it says it builds.

  G1  shapes(n) is every valid shape: checked against an independent generator written straight
      from the grammar, and against every small real variant
  G2  every edited tree is valid and differs from its base
  G3  each edit changes exactly what its name says
"""

from collections import Counter
from functools import lru_cache
from itertools import product

import pytest

from evaluation import probes
from rotation_hrr.variant_enumeration import canon, is_valid, n_leaves, shape_sig


# --- an independent generator, written from the grammar alone ----------------
#   sequence: >= 2 children, each an activity or a parallel block (ordered)
#   parallel: >= 2 children, activities and at most one sequence (unordered)

def _compositions(n):
    if n == 0:
        yield ()
        return
    for first in range(1, n + 1):
        for rest in _compositions(n - first):
            yield (first,) + rest


@lru_cache(maxsize=None)
def _seqs(n):
    out = set()
    for parts in _compositions(n):
        if len(parts) < 2:
            continue
        pools = [["L"] if s == 1 else sorted(_pars(s)) for s in parts]
        out |= {"→(" + ",".join(c) + ")" for c in product(*pools)}
    return frozenset(out)


@lru_cache(maxsize=None)
def _pars(n):
    out = {"∧(" + ",".join(["L"] * n) + ")"} if n >= 2 else set()
    for s in range(2, n):                        # one sequence of s, plus n - s activities
        out |= {"∧(" + ",".join(sorted(["L"] * (n - s) + [q])) + ")" for q in _seqs(s)}
    return frozenset(out)


def _grammar_shapes(n):
    return {"L"} if n == 1 else set(_seqs(n)) | set(_pars(n))


@pytest.mark.parametrize("n", range(1, 8))
def test_g1_shapes_match_the_grammar(n):
    got = [shape_sig(t) for t in probes.shapes(n)]
    assert len(got) == len(set(got)), "a shape appears twice"
    assert set(got) == _grammar_shapes(n)
    assert all(is_valid(t) and n_leaves(t) == n for t in probes.shapes(n))


def test_g1_every_small_real_variant_has_an_enumerated_shape():
    from evaluation.corpus import load_log
    try:
        corpus = load_log("sepsis")
    except FileNotFoundError:
        pytest.skip("no Sepsis variant cache")
    for t in corpus.trees:
        if n_leaves(t) <= 6:
            assert shape_sig(t) in _grammar_shapes(n_leaves(t))


SMALL = [t for n in range(1, 6) for t in probes.shapes(n)]


def test_g2_edited_trees_are_valid_and_different():
    for t in SMALL:
        for e in probes.single_edits(t):
            assert is_valid(e.edited), (e.where, canon(t))
            assert canon(e.edited) != canon(e.base)
            assert e.position in probes.POSITIONS and e.depth >= 0 and e.size >= 1


def _labels(t):
    return Counter(leaf.label for leaf in probes._leaves(t))


def test_g3_each_edit_changes_what_it_says():
    for t in SMALL:
        before = _labels(t)
        for e in probes.single_edits(t):
            after = _labels(e.edited)
            if e.edit in ("move", "seq_to_par", "joins", "nesting", "alongside"):
                assert after == before, e.where
            elif e.edit == "missing":
                assert sum((before - after).values()) == 1 and not (after - before)
            elif e.edit == "relabel":
                assert sum(after.values()) == sum(before.values())
                assert sum((after - before).values()) == 1
                assert next(iter(after - before)) not in before      # a new activity
            elif e.edit == "repetition":
                extra = after - before
                assert sum(extra.values()) == 1 and next(iter(extra)) in before


def _changed(base, edited):
    """Pairs of activities whose order relation (before / after / parallel, per occurrence
    pair) differs between the two trees, or that only one of them has (a behavioural profile)."""
    from evaluation.universe import relations
    a, b = relations(base), relations(edited)
    return {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)}


@pytest.mark.parametrize("n", [5, 6, 7])
def test_g5_paths_on_every_shape_grow_and_hold_the_rest(n):
    for t in probes.shapes(n):
        for key, steps in probes.paths_on(t).items():
            sizes = [e.size for e in steps]
            assert sizes == sorted(set(sizes)), key          # strictly growing
            assert len({canon(e.base) for e in steps}) == 1   # one fixed reference
            assert all(is_valid(e.edited) for e in steps)
            assert len({e.depth for e in steps}) == 1
            prev = set()
            for e in steps:                                   # each step contains the last
                if key[0] == "relabel":                       # new names: which were replaced
                    now = set(_labels(e.base)) - set(_labels(e.edited))
                else:
                    now = _changed(e.base, e.edited)
                assert prev <= now, (key, e.where)
                prev = now


def test_g6_alongside_makes_a_block_with_the_chain_inside():
    from rotation_hrr.variant_enumeration import leaf, seq, tree_str
    t = seq(leaf("A"), leaf("B"), leaf("C"))
    got = {tree_str(e.edited) for e in probes.single_edits(t) if e.edit == "alongside"}
    assert got == {"∧(A, →(B, C))", "∧(C, →(A, B))"}


def test_g7_thinned_probes_keep_the_kept_places_and_sizes():
    from rotation_hrr.variant_enumeration import leaf, seq
    t = seq(*[leaf(c) for c in "ABCDEFGHIJKL"])                # 12 children: slots 0, 3, 6, 8, 11
    assert probes.kept_slots(12) == {0, 3, 6, 8, 11}
    assert probes.kept_slots(probes.FULL_UP_TO) == set(range(probes.FULL_UP_TO))
    full, thin = probes.single_edits(t, smallest=True), probes.single_edits(t, smallest=True, thin=True)
    assert thin and len(thin) < len(full)
    assert all(e.slot[0] in probes.kept_slots(12) for e in thin)
    assert {(e.edit, canon(e.edited)) for e in thin} <= {(e.edit, canon(e.edited)) for e in full}
    assert {e.position for e in thin} == {e.position for e in full}
    for key, steps in probes.paths_on(t, thin=True).items():
        full_steps = probes.paths_on(t)[key]
        assert [e.size for e in steps] == [e.size for e in full_steps
                                           if e.size & (e.size - 1) == 0 or e is full_steps[-1]]
