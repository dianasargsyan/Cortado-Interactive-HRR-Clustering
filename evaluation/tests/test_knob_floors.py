"""
Where each knob's range starts: do the scale and the sign of α, β and the activity weights matter?

Every check compares HRR with itself, so no expected distance is needed.  Where a sign flip is
claimed to add nothing, the check is exact: the flipped encoding equals the unflipped one with the
random vectors transformed, and the transformed vectors are as likely a draw as the originals.

  F1  scaling every activity weight by c leaves every similarity unchanged
  F2  a negative weight on one activity = a positive weight with that activity's random vector
      reversed
  F3  flipping α and β together = the mirror image of the encoding with mirrored random vectors
      (the second coordinate of each 2-D block negated)
  F4  flipping β alone = counting depth the other way
  F5  with the paired banks, flipping β alone is a duplicate too: it equals the encoding with the
      two blocks of every pair swapped, in the random vectors and in the result; so no move, in
      position, depth or both, changes its expected similarity when β changes sign
"""

import numpy as np
import pytest

from evaluation import probes
from evaluation.config import DEFAULT_SEED, HRR_DEFAULTS
from evaluation.methods import hrr_ranges
from rotation_hrr.encoder import RotationHRREncoder
from rotation_hrr.tree_utils import tree_to_positioned_sequence
from rotation_hrr.variant_enumeration import tree_str

ALPHA, BETA = HRR_DEFAULTS["alpha"], HRR_DEFAULTS["beta"]
TOL = 1e-12

# Every shape with 1-4 activities, plus their repetition edits (repeated activities).
TREES = [t for n in range(1, 5) for t in probes.shapes(n)] + [
    e.edited for n in range(1, 4) for t in probes.shapes(n)
    for e in probes.single_edits(t) if e.edit == "repetition"
]
LABELS = sorted({lab for t in TREES for lab, _, _ in tree_to_positioned_sequence(t)[0]})


class _Transformed(RotationHRREncoder):
    """The same encoder, with each random vector passed through f(label, v)."""

    def __init__(self, f, **kw):
        super().__init__(**kw)
        self._f = f

    def get_label_vector(self, activity):
        return self._f(activity, super().get_label_vector(activity))


def _encoder(f=None):
    n_max, n_max_depth = hrr_ranges(TREES)
    kw = dict(d=HRR_DEFAULTS["d"], n_max=n_max, n_max_depth=n_max_depth, seed=DEFAULT_SEED)
    return _Transformed(f, **kw) if f else RotationHRREncoder(**kw)


def _bundles(enc, **kw):
    return np.stack([enc.encode_tree(t, **kw) for t in TREES])


def _similarities(X):
    Xn = X / np.linalg.norm(X, axis=1, keepdims=True)
    return Xn @ Xn.T


def _mirror(v):
    """Negate the second coordinate of every 2-D block: R(θ) becomes R(-θ)."""
    out = v.copy()
    out[1::2] *= -1
    return out


# ---------------------------------------------------------------------------
# F1  Only the ratios between weights matter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("c", [0.25, 4.0, -1.0])
def test_scaling_all_weights_changes_no_similarity(c):
    # Every activity is named: activities left out default to 1 and would not be scaled.
    rng = np.random.default_rng(0)
    w = {lab: float(x) for lab, x in zip(LABELS, rng.uniform(0.1, 3.0, len(LABELS)))}
    enc = _encoder()
    S = _similarities(_bundles(enc, alpha=ALPHA, beta=BETA, activity_weights=w))
    S_c = _similarities(_bundles(enc, alpha=ALPHA, beta=BETA,
                                 activity_weights={a: c * x for a, x in w.items()}))
    np.testing.assert_allclose(S_c, S, rtol=0, atol=TOL)


# ---------------------------------------------------------------------------
# F2  A negative weight is a positive weight with the vector reversed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a", LABELS)
def test_negative_weight_is_the_reversed_vector(a):
    negative = _bundles(_encoder(), alpha=ALPHA, beta=BETA, activity_weights={a: -2.0})
    reversed_a = _encoder(lambda lab, v: -v if lab == a else v)
    positive = _bundles(reversed_a, alpha=ALPHA, beta=BETA, activity_weights={a: 2.0})
    np.testing.assert_allclose(negative, positive, rtol=0, atol=TOL)


# ---------------------------------------------------------------------------
# F3  Flipping α and β together mirrors every vector
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alpha, beta", [(ALPHA, BETA), (ALPHA, -BETA), (0.5, 2.0)])
def test_flipping_alpha_and_beta_together_is_a_mirror_image(alpha, beta):
    flipped = _bundles(_encoder(), alpha=-alpha, beta=-beta)
    mirrored = _bundles(_encoder(lambda lab, v: _mirror(v)), alpha=alpha, beta=beta)
    np.testing.assert_allclose(flipped, np.apply_along_axis(_mirror, 1, mirrored),
                               rtol=0, atol=TOL)
    np.testing.assert_allclose(_similarities(flipped), _similarities(mirrored),
                               rtol=0, atol=TOL)


# ---------------------------------------------------------------------------
# F4  Flipping β alone counts depth the other way
# ---------------------------------------------------------------------------

def test_flipping_beta_is_counting_depth_the_other_way():
    enc = _encoder()
    for t in TREES:
        items = tree_to_positioned_sequence(t)[0]
        labels = [lab for lab, _, _ in items]
        positions = np.array([p for _, p, _ in items])
        depths = np.array([d for _, _, d in items])
        np.testing.assert_allclose(
            enc.encode_tree(t, alpha=ALPHA, beta=-BETA),
            enc.encode(labels, positions=positions, depths=-depths, alpha=ALPHA, beta=BETA),
            rtol=0, atol=TOL, err_msg=tree_str(t),
        )


# ---------------------------------------------------------------------------
# F5  ... which matters only for a move in both position and depth
# ---------------------------------------------------------------------------

def _expected_self_similarity(enc, dp, dd, beta):
    """Similarity of an activity to itself moved by (dp, dd), averaged over its
    random vector: the mean over blocks of cos(dp*α*θ_k + dd*β*θ'_k)."""
    return float(np.mean(np.cos(dp * ALPHA * enc.thetas + dd * beta * enc.depth_thetas)))


def _swap_pairs(v):
    """Swap the two 2-D blocks of every pair (the paired layout's two depth directions)."""
    return v.reshape(*v.shape[:-1], -1, 2, 2)[..., ::-1, :].reshape(v.shape)


@pytest.mark.parametrize("alpha, beta", [(ALPHA, BETA), (0.5, 2.0), (2.0, 0.5)])
def test_flipping_beta_alone_swaps_the_blocks_of_each_pair(alpha, beta):
    flipped = _bundles(_encoder(), alpha=alpha, beta=-beta)
    swapped = _bundles(_encoder(lambda lab, v: _swap_pairs(v)), alpha=alpha, beta=beta)
    np.testing.assert_allclose(flipped, _swap_pairs(swapped), rtol=0, atol=TOL)


@pytest.mark.parametrize("dp, dd", [(0.5, 0), (2.0, 0), (0, 1), (0, 2),
                                    (0.5, 1), (1.0, 1), (2.0, 1), (1.0, 2)])
def test_flipping_beta_alone_changes_no_expected_similarity(dp, dd):
    enc = _encoder()
    gap = abs(_expected_self_similarity(enc, dp, dd, BETA)
              - _expected_self_similarity(enc, dp, dd, -BETA))
    assert gap < TOL
