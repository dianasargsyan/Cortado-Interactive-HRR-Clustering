"""
Each comparison method (evaluation/baselines.py) against its paper's own worked example, then the
properties every distance must have (0 for the same tree, symmetric) and the input rule (a
block's children in another order are the same variant to every method).
"""

from collections import Counter

import numpy as np
import pytest

from conftest import make_leaf, make_par, make_seq
from evaluation import baselines as B
from evaluation import config
from evaluation.corpus import from_trees
from evaluation.methods import represent


class N:
    """A node of the papers' example trees: every node, inner ones too, carries a label."""

    def __init__(self, lab, *children):
        self.lab, self.children = lab, list(children)


LAB = dict(label=lambda n: n.lab, leaf=lambda n: not n.children)
D, E = B.DUMMY, B.EPSILON


# ---------------------------------------------------------------------------
# pq-grams: Augsten, Boehlen & Gamper 2010, figures 3 and 8, example 6.3
# ---------------------------------------------------------------------------

T1 = N("a", N("a", N("e"), N("b")), N("b"), N("c"))
T2 = N("a", N("a", N("e"), N("b")), N("b"), N("d"))


def _tuples(rows):
    return Counter(tuple(D if x == "*" else x for x in r.split(",")) for r in rows)


FIG8_T1 = _tuples(["*,a,*,*,a", "a,a,*,*,e", "a,e,*,*,*", "a,a,*,e,b", "a,b,*,*,*", "a,a,e,b,*",
                   "a,a,b,*,*", "*,a,*,a,b", "a,b,*,*,*", "*,a,a,b,c", "a,c,*,*,*", "*,a,b,c,*",
                   "*,a,c,*,*"])
FIG8_T2 = _tuples(["*,a,*,*,a", "a,a,*,*,e", "a,e,*,*,*", "a,a,*,e,b", "a,b,*,*,*", "a,a,e,b,*",
                   "a,a,b,*,*", "*,a,*,a,b", "a,b,*,*,*", "*,a,a,b,d", "a,d,*,*,*", "*,a,b,d,*",
                   "*,a,d,*,*"])


def test_pq_index_is_figure_8():
    assert B.pq_index(T1, 2, 3, **LAB) == FIG8_T1
    assert B.pq_index(T2, 2, 3, **LAB) == FIG8_T2


def test_normalised_pq_distance_is_example_6_3():
    """|I1 + I2| = 26, |I1 & I2| = 9, so (26 - 18) / (26 - 9) = 0.47."""
    I1, I2 = B.pq_index(T1, **LAB), B.pq_index(T2, **LAB)
    X, Y = B.matrices([I1], [I2])
    L1 = B.pairwise_l1(X, Y)[0, 0]
    S = sum(I1.values()) + sum(I2.values())
    assert S == 26 and (S - L1) // 2 == 9
    assert 2 * L1 / (S + L1) == pytest.approx(8 / 17)


# ---------------------------------------------------------------------------
# Binary branches: Yang, Kalnis & Tung 2005, figures 1-3
# ---------------------------------------------------------------------------

Y1 = N("a", N("b", N("c"), N("d")), N("b", N("c"), N("d")), N("e"))
Y2 = N("a", N("b", N("c"), N("d"), N("b", N("e"))), N("c"), N("d"), N("e"))
# the paper's branches in its column order (figure 3), u u1 u2 with epsilon for none
COLUMNS = [("a", "b", E), ("b", "c", "b"), ("b", "c", "c"), ("b", "c", "e"), ("b", "e", E),
           ("c", E, "d"), ("d", E, "b"), ("d", E, "e"), ("d", E, E), ("e", E, E)]


def test_binary_branch_vectors_are_figure_3():
    v1 = [B.binary_branches(Y1, **LAB).get(c, 0) for c in COLUMNS]
    v2 = [B.binary_branches(Y2, **LAB).get(c, 0) for c in COLUMNS]
    assert v1 == [1, 1, 0, 1, 0, 2, 0, 0, 2, 1]
    assert v2 == [1, 0, 1, 0, 1, 2, 1, 1, 0, 2]
    assert sum(B.binary_branches(Y1, **LAB).values()) == 8        # one branch per node
    assert sum(B.binary_branches(Y2, **LAB).values()) == 9


def test_bdist_is_the_l1_of_the_figure_3_vectors():
    X, Y = B.matrices([B.binary_branches(Y1, **LAB)], [B.binary_branches(Y2, **LAB)])
    assert B.pairwise_l1(X, Y)[0, 0] == 9


# ---------------------------------------------------------------------------
# 3-grams: Bose & van der Aalst 2009, section 3.2
# ---------------------------------------------------------------------------


def seq(word):
    return make_seq(*[make_leaf(c) for c in word])


def test_3grams_of_abacaab():
    assert B.kgrams(list("abacaab")) == Counter({tuple("aba"): 1, tuple("bac"): 1,
                                                  tuple("aca"): 1, tuple("caa"): 1,
                                                  tuple("aab"): 1})


def test_3gram_distance_is_euclidean_on_counts():
    """ABCD has ABC, BCD; ABDC has ABD, BDC: four 3-grams differ by one, so sqrt(4) = 2."""
    D3 = B.trigram_distances([seq("ABCD"), seq("ABDC")])
    assert D3[0, 1] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Every method: 0 to itself, symmetric, the same variant written differently is 0
# ---------------------------------------------------------------------------

FNS = {"onehot": B.onehot_distances, "trigram": B.trigram_distances, "pqgram": B.pq_distances,
       "binary_branch": B.binary_branch_distances, "apted": lambda ts: B.apted_distances(ts, n_jobs=1)}
TREES = [seq("ABCD"), seq("ABDC"), make_seq(make_leaf("A"), make_par(make_leaf("B"), make_leaf("C")),
                                            make_leaf("D")),
         make_par(make_leaf("A"), make_seq(make_leaf("B"), make_leaf("C"))), seq("AAB")]


@pytest.mark.parametrize("name", list(FNS))
def test_zero_diagonal_and_symmetric(name):
    Dm = FNS[name](TREES)
    assert np.allclose(np.diag(Dm), 0.0, atol=0)
    assert np.array_equal(Dm, Dm.T)
    assert (Dm >= 0).all()


@pytest.mark.parametrize("name", list(FNS))
def test_block_children_order_is_the_same_variant(name):
    """∧(A, B, C) and ∧(C, A, B) are one variant written two ways."""
    a = make_seq(make_leaf("X"), make_par(make_leaf("A"), make_leaf("B"), make_leaf("C")))
    b = make_seq(make_leaf("X"), make_par(make_leaf("C"), make_leaf("A"), make_leaf("B")))
    assert FNS[name]([a, b])[0, 1] == 0.0


def test_what_each_method_sees_of_a_swap():
    """→(A, B, C) against →(B, A, C): every method in the set reads order and sees it (3-grams:
    ABC against BAC)."""
    a, b = seq("ABC"), seq("BAC")
    seen = {name: FNS[name]([a, b])[0, 1] > 1e-9 for name in FNS}
    assert seen == {"onehot": False, "trigram": True, "pqgram": True, "binary_branch": True,
                    "apted": True}


def test_onehot_counts_repeats():
    """The activity profile counts: AAB is (2, 1), AB is (1, 1), so Song et al.'s Jaccard is
    1 - 3 / (5 + 2 - 3) = 0.25; as sets the two would be at 0."""
    assert B.onehot_distances([seq("AAB"), seq("AB")])[0, 1] == pytest.approx(0.25)


def test_apted_uses_unit_costs():
    """→(A, B) against ∧(A, B): one operator relabelled, cost 1."""
    assert B.apted_distances([seq("AB"), make_par(make_leaf("A"), make_leaf("B"))], n_jobs=1)[0, 1] == 1


@pytest.mark.parametrize("name", list(FNS))
def test_pair_distances_match_the_square_matrix(name):
    """The probes' per-pair distances equal the all-pairs ones."""
    full = FNS[name](TREES)
    ia, ib = np.triu_indices(len(TREES), 1)
    method = {"apted": "apted"}.get(name, name)
    assert np.allclose(B.pair_distances(method, TREES, ia, ib), full[ia, ib])


@pytest.mark.parametrize("p,q", config.PQ_SWEEP)
def test_pq_sweep_pair_distances_match_the_square_matrix(p, q):
    """At every setting of the sweep, the probes' pq-gram distances equal the all-pairs ones, and
    the registered method passes the setting through."""
    full = B.pq_distances(TREES, p=p, q=q)
    ia, ib = np.triu_indices(len(TREES), 1)
    assert np.allclose(B.pair_distances("pqgram", TREES, ia, ib, p=p, q=q), full[ia, ib])
    C = from_trees("pq_sweep_test", TREES)
    assert np.array_equal(represent("pqgram", C, use_cache=False, p=p, q=q).distances, full)


def test_pq_window_sets_how_far_a_move_is_seen():
    """A moved k places right in ->(A, ..., J): at q = 3 the distance stops growing after two
    places; at q = 1 no sibling order is seen at all."""
    letters = list("ABCDEFGHIJ")

    def moved(k):
        s = letters[1:]
        s.insert(k, "A")
        return seq("".join(s))

    d = {q: [B.pq_distances([seq("ABCDEFGHIJ")], [moved(k)], p=2, q=q)[0, 0] for k in range(1, 10)]
         for q in (1, 3)}
    assert all(x == 0.0 for x in d[1])
    assert d[3][0] < d[3][1] and len(set(d[3][1:])) == 1


def test_cross_distances_match_the_square_matrix():
    """Distances between two lists equal the corresponding block of one list's matrix."""
    for name, fn in (("trigram", B.trigram_distances), ("pqgram", B.pq_distances),
                     ("binary_branch", B.binary_branch_distances)):
        full = fn(TREES)
        part = fn(TREES[:2], TREES[2:])
        assert np.allclose(part, full[:2, 2:]), name


def test_java_apted_equals_the_python_port():
    """The authors' Java APTED (evaluation/java_apted/) and the Python port (the apted package) give the same
    distance on every pair of every tree with up to 4 activities over A, B, C."""
    from apted import APTED, Config
    from rotation_hrr.variant_enumeration import full_enumeration

    class Plain:
        def __init__(self, t):
            self.name = B.node_label(t)
            self.children = [] if t.label is not None else [Plain(c) for c in t.children]

    trees = full_enumeration(4, ["A", "B", "C"])[::7]
    java = B.apted_distances(trees)
    plain = [Plain(B.sorted_tree(t)) for t in trees]
    for i in range(len(trees)):
        for j in range(i + 1, len(trees)):
            assert java[i, j] == APTED(plain[i], plain[j], Config()).compute_edit_distance()
