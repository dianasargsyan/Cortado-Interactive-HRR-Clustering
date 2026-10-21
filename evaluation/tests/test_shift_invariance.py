"""
Shift invariance of the HRR distance: if every position in two variants is offset by the same
delta, the distance between them is unchanged,

    d(shift_delta(X), shift_delta(Y)) == d(X, Y).

It is exact, not approximate: a uniform offset turns every vector by the same rotation R(delta),
and the cosine is invariant under a rotation applied to both arguments.  So if a log gains a step
at the front of every case, no pair of variants moves relative to any other.  The property is
structural, not the default of a knob: no setting turns it off, which the parametrisation over
alpha, beta and activity weights below checks.

A variant against its own shifted self is a different question and is not zero: the shifted
variant has other absolute positions.  It is only near (test_self_shift_is_near_not_identical).
"""

import numpy as np
import pytest

from evaluation.tests.conftest import make_leaf, make_seq, make_par
from rotation_hrr.encoder import RotationHRREncoder
from rotation_hrr.tree_utils import tree_to_positioned_sequence

TREES = [
    make_seq(make_leaf("A"), make_leaf("B"), make_leaf("C")),
    make_seq(make_leaf("C"), make_leaf("B"), make_leaf("A")),
    make_par(make_leaf("A"), make_leaf("B")),
    make_seq(make_leaf("A"), make_par(make_leaf("B"), make_leaf("C"))),
    make_par(make_leaf("X"), make_seq(make_leaf("Y"), make_leaf("Z"))),
    make_seq(make_leaf("A"), make_leaf("B"), make_leaf("A"), make_leaf("C")),
]

DELTAS = [1.0, 3.0, 7.5, 100.0]


def _distance(encoder, tree, offset=0.0, **kwargs):
    """Cosine distance input: encode a tree with every position offset equally."""
    items, _ = tree_to_positioned_sequence(tree)
    labels = [label for label, _, _ in items]
    positions = np.array([pos + offset for _, pos, _ in items])
    depths = np.array([depth for _, _, depth in items])
    v = encoder.encode(labels, positions=positions, depths=depths, **kwargs)
    return v / np.linalg.norm(v)


def _cos_distance(u, v):
    return 1.0 - float(u @ v)


@pytest.mark.parametrize("delta", DELTAS)
@pytest.mark.parametrize("i,j", [(i, j) for i in range(len(TREES))
                                 for j in range(i + 1, len(TREES))])
def test_uniform_offset_preserves_distance(i, j, delta):
    """d(shift(X), shift(Y)) == d(X, Y), to floating-point precision."""
    enc = RotationHRREncoder()
    before = _cos_distance(_distance(enc, TREES[i]), _distance(enc, TREES[j]))
    after = _cos_distance(_distance(enc, TREES[i], offset=delta),
                          _distance(enc, TREES[j], offset=delta))
    assert after == pytest.approx(before, abs=1e-12)


@pytest.mark.parametrize("alpha,beta,weights", [
    (1.0, 1.0, None),                    # defaults
    (0.5, 1.0, None),
    (1.0, 0.0, None),
    (1.0, 1.0, {"A": 2.0, "C": 0.5}),    # weights attach to activities, not positions
    (2.0, 2.0, {"B": 3.0}),
])
def test_invariance_holds_at_every_setting(alpha, beta, weights):
    """No hyperparameter turns shift invariance off: it is structural."""
    enc = RotationHRREncoder()
    kw = dict(alpha=alpha, beta=beta, activity_weights=weights)
    x, y = TREES[0], TREES[3]
    before = _cos_distance(_distance(enc, x, **kw), _distance(enc, y, **kw))
    after = _cos_distance(_distance(enc, x, offset=5.0, **kw),
                          _distance(enc, y, offset=5.0, **kw))
    assert after == pytest.approx(before, abs=1e-12)


@pytest.mark.parametrize("tree", TREES)
def test_self_shift_is_near_not_identical(tree):
    """A variant and its shifted self are close, but not the same variant.

    Guards against the opposite error: an encoder that ignored position would
    score 0 here and would also be perfectly 'shift invariant', which is why
    invariance is never a property worth asserting on its own.
    """
    enc = RotationHRREncoder()
    d_self = _cos_distance(_distance(enc, tree), _distance(enc, tree, offset=1.0))
    d_other = max(
        _cos_distance(_distance(enc, tree), _distance(enc, other))
        for other in TREES if other is not tree
    )
    assert d_self >= 0.0
    assert d_self < d_other, "a shifted copy must be nearer than a different variant"
