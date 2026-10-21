"""
evaluation.batch_hrr encodes many trees exactly as RotationHRREncoder.encode_tree does: the same
vectors to rounding, at every setting of the grid and beyond, for every shape up to 6 activities,
trees with repeated activities, and edited trees from the probe paths.
"""

from __future__ import annotations

import numpy as np
import pytest

from evaluation import config, probes
from evaluation.batch_hrr import Batch, angular
from evaluation.methods import angular as pipeline_angular
from rotation_hrr.encoder import RotationHRREncoder
from rotation_hrr.variant_enumeration import leaf, par, seq


def trees():
    out = [t for n in range(1, 7) for t in probes.shapes(n)]
    out += [seq(leaf("A"), leaf("A"), par(leaf("A"), leaf("B"))), par(leaf("A"), leaf("A")),
            seq(leaf("A"), par(leaf("B"), seq(leaf("A"), leaf("A"))))]
    for t in probes.shapes(5)[::7]:
        for steps in probes.paths_on(t).values():
            out += [e.edited for e in steps]
    return out


@pytest.mark.parametrize("alpha,beta", [(0.0, 0.0), (0.5, 1.0), (1.0, 0.5), (1.5, 1.0), (2.0, 2.0)])
@pytest.mark.parametrize("seed", config.SEEDS[:2])
def test_b1_batch_equals_encode_tree(alpha, beta, seed):
    T = trees()
    enc = RotationHRREncoder(d=256, n_max=40, n_max_depth=16, seed=seed)
    X = Batch(T).vectors(enc, alpha, beta, chunk=97)          # small chunks: the seams are tested
    Y = np.stack([enc.encode_tree(t, alpha=alpha, beta=beta) for t in T])
    assert np.max(np.abs(X - Y)) <= 1e-12 * max(1.0, np.max(np.abs(Y)))


def test_b2_pair_distance_equals_the_pipeline_distance():
    T = trees()[:300]
    enc = RotationHRREncoder(d=256, n_max=40, n_max_depth=16, seed=42)
    X = Batch(T).vectors(enc, 1.0, 1.0)
    i, j = np.triu_indices(len(T), 1)
    # arccos turns rounding just below cos = 1 into ~1e-8 for two identical trees; away from 0
    # the two agree to ~1e-15
    a, b = angular(X, i, j), pipeline_angular(X)[i, j]
    assert np.max(np.abs(a - b)) < 1e-7
    far = b > 1e-3
    assert np.max(np.abs(a[far] - b[far])) < 1e-12


def test_b3_pair_distances_in_chunks_equal_one_batch():
    from evaluation.batch_hrr import pair_distances
    T = trees()[:400]
    pairs = [(T[i], T[(i * 7 + 3) % len(T)]) for i in range(len(T))]
    settings = [(0.5, 1.0), (1.0, 0.0)]
    small = pair_distances(pairs, (40, 16), settings, config.SEEDS[:2], d=256, max_trees=50)
    whole = pair_distances(pairs, (40, 16), settings, config.SEEDS[:2], d=256, max_trees=10 ** 6)
    # arccos near cos = 1 turns rounding of 1e-16 into about 1e-8 (a pair with identical vectors),
    # and the order of a sum depends on the maths library
    assert np.max(np.abs(small - whole)) < 1e-8
    enc = RotationHRREncoder(d=256, n_max=40, n_max_depth=16, seed=config.SEEDS[1])
    ref = [np.arccos(np.clip(x @ y / np.linalg.norm(x) / np.linalg.norm(y), -1, 1)) / np.pi
           for x, y in ((enc.encode_tree(a, alpha=1.0, beta=0.0), enc.encode_tree(b, alpha=1.0, beta=0.0))
                        for a, b in pairs)]
    assert np.max(np.abs(small[:, 1, 1] - ref)) < 1e-7
