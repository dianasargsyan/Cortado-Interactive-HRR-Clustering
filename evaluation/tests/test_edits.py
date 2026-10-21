"""
The analyst's two edits (domain_knowledge.py, evaluation/edited.py): "these are the same" and "I don't
care about this activity"; the trees they produce; and locality (an edit leaves every variant
without the edited activities exactly as it was).
"""

import numpy as np
import pytest

from rotation_hrr.domain_knowledge import DomainKnowledge
from evaluation.batch_hrr import Batch
from evaluation.edited import EditedLog
from rotation_hrr.tree_utils import tree_to_sequence
from evaluation.tests.conftest import make_leaf, make_par, make_seq
from rotation_hrr.tree_rewrites import drop_activities, relabel
from rotation_hrr.variant_enumeration import canon


def seq(s):
    return make_seq(*[make_leaf(c) for c in s])


def test_drop_keeps_the_normal_form():
    t = make_seq(make_leaf("A"), make_par(make_leaf("X"), seq("BC")), make_leaf("D"))
    assert canon(drop_activities(t, {"X"})) == canon(seq("ABCD"))
    assert drop_activities(seq("XX"), {"X"}) is None


def test_relabel():
    assert canon(relabel(seq("ABA"), {"A": "Z"})) == canon(seq("ZBZ"))


TREES = [seq("AXBC"), seq("ABC"), seq("AYC"), seq("AXC"), seq("BCD"), seq("XX"),
         make_seq(make_leaf("A"), make_par(make_leaf("B"), make_leaf("C")))]


def test_no_edit_equals_the_batch_encoder():
    E = EditedLog(TREES, d=256, seed=5)
    X = Batch(TREES).vectors(E.encoder(5), 1.0, 1.0)
    assert np.allclose(E.vectors(1.0, 1.0), X)


def test_equivalence_makes_alias_only_pairs_identical():
    E = EditedLog(TREES, DomainKnowledge(activity_equivalences={"X": ["Y"]}), d=256, seed=5)
    assert E.distances(1.0, 1.0)[2, 3] == pytest.approx(0.0, abs=1e-6)


def test_ignore_drops_the_activity():
    E = EditedLog(TREES, DomainKnowledge(ignored_activities={"X"}), d=256, seed=5)
    D = E.distances(1.0, 1.0)
    assert D[0, 1] == pytest.approx(0.0, abs=1e-6)          # →(A, X, B, C) = →(A, B, C)
    assert D[5, 5] == 0.0 and D[5, 1] == pytest.approx(0.5)   # →(X, X) has nothing left


@pytest.mark.parametrize("dk", [
    DomainKnowledge(activity_equivalences={"X": ["Y"]}),
    DomainKnowledge(ignored_activities={"X"}),
    DomainKnowledge(activity_equivalences={"X": ["Y"]}, ignored_activities={"A"}),
])
def test_variants_without_the_edited_activity_keep_their_vectors(dk):
    edited = set(dk.ignored_activities) | {a for c, al in dk.activity_equivalences.items() for a in [c, *al]}
    before = EditedLog(TREES, d=256, seed=5).vectors(1.0, 1.0)
    after = EditedLog(TREES, dk, d=256, seed=5).vectors(1.0, 1.0)
    untouched = [i for i, t in enumerate(TREES) if not (edited & set(tree_to_sequence(t)))]
    assert untouched
    assert np.allclose(before[untouched], after[untouched])


LOG = [seq("AXBC"), seq("ABC"), seq("AYC"), seq("AXC"), seq("BCD"), seq("XBYA"),
       make_seq(make_leaf("A"), make_par(make_leaf("X"), make_leaf("C")))]


def test_ignoring_one_name_of_an_equivalence_ignores_the_group():
    group = EditedLog(LOG, DomainKnowledge(activity_equivalences={"X": ["Y"]}, ignored_activities={"Y"}),
                      d=256, seed=5).vectors(1.0, 1.0)
    both = EditedLog(LOG, DomainKnowledge(ignored_activities={"X", "Y"}), d=256, seed=5).vectors(1.0, 1.0)
    assert np.allclose(group, both)
