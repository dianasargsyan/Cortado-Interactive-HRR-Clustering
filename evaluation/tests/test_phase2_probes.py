"""
The capability probes (evaluation/phase2_probes.py): stacked edits hold exactly the number of edits they
claim, on separate activities; the named cases relate their pairs as they say; every base kind of
the dataset builds without error.
"""

from collections import Counter

import pytest

from conftest import make_leaf as L, make_par as P, make_seq as S
from evaluation import dataset, phase2_probes as Q, probe_sets
from rotation_hrr.tree_utils import tree_to_sequence
from rotation_hrr.variant_enumeration import PAR, canon, is_leaf


def word(w):
    return S(*[L(c) for c in w])


def n_blocks(t):
    return int(not is_leaf(t) and t.op == PAR) + (0 if is_leaf(t) else sum(n_blocks(c) for c in t.children))


def inversions(seq_, ref):
    pos = {a: i for i, a in enumerate(ref)}
    s = [pos[a] for a in seq_]
    return sum(1 for i in range(len(s)) for j in range(i + 1, len(s)) if s[i] > s[j])


def test_tag_untag_round_trip():
    t = S(L("A"), P(L("B"), L("C")), L("A"))
    assert canon(Q.untag(Q.tag(t))) == canon(t)
    labs = tree_to_sequence(Q.tag(t))
    assert len(set(labs)) == len(labs)


@pytest.fixture(scope="module")
def flat():
    pid = [0]
    return Q.probes_of(word("ABCDEFGHIJKL"), pid, Q.rename_map(list("ABCDEFGHIJKL")))


def test_count_paths_hold_exactly_k_separate_edits(flat):
    ref = list("ABCDEFGHIJKL")
    for p in (x for x in flat if x.kind == "count"):
        seq_ = tree_to_sequence(p.b)
        if p.edit == "move":
            assert inversions(seq_, ref) == p.size            # k separate adjacent swaps
        elif p.edit == "missing":
            assert len(seq_) == 12 - p.size
        elif p.edit == "seq_to_par":
            assert n_blocks(p.b) == p.size
        elif p.edit == "repetition":
            assert len(seq_) == 12 + p.size


def test_count_paths_double(flat):
    for p in (x for x in flat if x.kind == "count"):
        assert p.size in Q.COUNTS


def test_every_count_path_starts_at_one(flat):
    by_path = {}
    for p in (x for x in flat if x.kind == "count"):
        by_path.setdefault(p.path, []).append(p.size)
    assert all(sizes[0] == 1 and len(sizes) >= 2 for sizes in by_path.values())


def test_combo_second_edit_is_on_other_activities(flat):
    by_path = {}
    for p in (x for x in flat if x.kind == "combo"):
        by_path.setdefault(p.path, []).append(p)
    for first, second in by_path.values():
        assert first.size == 1 and second.size == 2 and second.expect == "not_closer"
        assert canon(first.b) != canon(second.b) != canon(first.a)


def test_renamed_twins_share_the_one_step_id(flat):
    one = {p.path: p for p in flat if p.kind == "one_step"}
    ren = [p for p in flat if p.kind == "renamed"]
    assert ren and all(p.path in one for p in ren)


def test_swap_inside_a_new_block_is_the_same_variant(flat):
    cases = [p for p in flat if p.kind == "named" and p.expect == "same"]
    assert cases and all(canon(p.a) == canon(p.b) and repr(p.a) != repr(p.b) for p in cases)


def test_nesting_plus_a_swap_on_a_block():
    pid = [0]
    t = S(L("X"), P(L("A"), L("B"), L("C")), L("Y"))
    cases = [p for p in Q.probes_of(t, pid) if p.edit == "nesting plus a swap"]
    assert cases and all(canon(p.a) != canon(p.b) for p in cases)


def test_blocks_reversed_form_on_a_variant_with_a_block():
    pid = [0]
    t = S(L("X"), P(L("A"), L("B")), L("Y"))
    forms = [p for p in Q.probes_of(t, pid) if p.kind == "form"]
    assert len(forms) == 1 and canon(forms[0].a) == canon(forms[0].b)


def test_every_base_kind_builds():
    """A few bases of every layer kind: the universe, every dataset length, a real base."""
    bases = [t for _, t in probe_sets.universe(4)[:20]]
    for n in dataset.LENGTHS:
        rows = dataset.sample_9() if n == 9 else dataset.variants(n)
        bases += [r[-1] for r in rows[:3]]
    pid = [0]
    kinds = Counter()
    for t in bases:
        kinds.update(p.kind for p in Q.probes_of(t, pid, Q.rename_map(tree_to_sequence(t))))
    assert {"paths", "one_step", "count", "combo", "named", "renamed"} <= set(kinds)


def test_no_apart_pair_is_the_same_variant():
    """Two copies of one activity swapped (or any edit that changes nothing once the tags are
    removed) is no edit: every pair that should differ does differ."""
    pid = [0]
    for t in [S(L("A"), L("A"), L("B")), S(L("A"), L("A"), L("A"), L("B")), S(L("A"), P(L("B"), L("B")), L("A"))]:
        for p in Q.probes_of(t, pid, Q.rename_map(tree_to_sequence(t))):
            if p.kind in ("one_step", "count", "combo") or (p.kind == "named" and p.expect == "apart"):
                assert canon(p.a) != canon(p.b), (p.kind, p.edit)
