"""
Many trees at once, exactly as ``RotationHRREncoder.encode_tree`` encodes them.

A tree's vector is the sum over its activities of the activity's vector turned by
alpha * position * theta + beta * depth * theta'.  Positions and depths depend on neither the
seed nor a knob, so they are computed once per tree.  The same (activity, position, depth)
recurs across trees, so each distinct one is turned once per seed and setting, and a sparse sum
gives every tree's vector.  Only the order of the final sum differs from ``encode_tree``, so the
two agree to rounding (tests/test_batch_hrr.py).
"""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix

from rotation_hrr.tree_utils import tree_to_positioned_sequence


class Batch:
    """The positioned leaves of *trees*, ready to encode under any seed and setting."""

    def __init__(self, trees):
        index: dict = {}
        labels: dict = {}
        lab, pos, dep = [], [], []
        indptr, indices = [0], []
        for t in trees:
            items = tree_to_positioned_sequence(t)[0]
            for label, p, dp in items:
                key = (label, p, dp)
                j = index.get(key)
                if j is None:
                    j = index[key] = len(pos)
                    lab.append(labels.setdefault(label, len(labels)))
                    pos.append(p)
                    dep.append(dp)
                indices.append(j)
            indptr.append(len(indices))
        self.n = len(trees)
        self.labels = list(labels)
        self.lab = np.array(lab, dtype=np.intp)
        self.pos = np.array(pos, dtype=np.float64)
        self.dep = np.array(dep, dtype=np.float64)
        S = csr_matrix((np.ones(len(indices)), np.array(indices, dtype=np.intp),
                        np.array(indptr, dtype=np.intp)), shape=(self.n, len(pos)))
        S.sum_duplicates()                     # an activity twice at one place counts twice
        self.S = S.tocsc()

    def vectors(self, enc, alpha: float, beta: float, chunk: int | None = None,
                rows: int = 2048) -> np.ndarray:
        """(n, d): each tree's vector under *enc* (its seed, d and frequency banks).  Works in
        blocks of *chunk* distinct leaves and *rows* trees, so no temporary is larger than
        max(chunk, rows) x d; by default chunk x d is 2^23 (larger blocks are slower at large d)."""
        chunk = chunk or max(256, (1 << 23) // enc.d)
        L = np.stack([enc.get_label_vector(label) for label in self.labels])
        S = self.S
        X = np.zeros((self.n, enc.d))
        for a in range(0, len(self.pos), chunk):
            b = min(a + chunk, len(self.pos))
            angles = (np.outer(self.pos[a:b], alpha * enc.thetas)
                      + np.outer(self.dep[a:b], beta * enc.depth_thetas))
            c, s = np.cos(angles), np.sin(angles)
            V = L[self.lab[a:b]]
            x, y = V[:, 0::2], V[:, 1::2]
            rot = np.empty((b - a, enc.d))
            rot[:, 0::2] = c * x - s * y
            rot[:, 1::2] = s * x + c * y
            S_ab = S[:, a:b].tocsr()
            for r in range(0, self.n, rows):
                X[r:r + rows] += S_ab[r:r + rows] @ rot
        return X


def angular(X: np.ndarray, i: np.ndarray, j: np.ndarray, block: int = 4096) -> np.ndarray:
    """Angular distance arccos(cos) / pi between rows i and j of X (the pipeline's distance),
    in blocks of pairs."""
    n = np.linalg.norm(X, axis=1)
    out = np.empty(len(i))
    for a in range(0, len(i), block):
        ii, jj = i[a:a + block], j[a:a + block]
        c = np.einsum("ij,ij->i", X[ii], X[jj]) / (n[ii] * n[jj])
        out[a:a + block] = np.arccos(np.clip(c, -1.0, 1.0)) / np.pi
    return out


def pair_distances(pairs, ranges: tuple[int, int], settings, seeds, d: int,
                   max_trees: int = 6000) -> np.ndarray:
    """(pairs, seeds, settings): the angular distance of every (tree, tree) pair under every
    encoder seed and (alpha, beta) setting, with frequency ranges *ranges*.  Pairs are
    taken in order and their distinct trees encoded in chunks of at most *max_trees*, so memory
    stays bounded however many pairs there are."""
    from rotation_hrr.encoder import RotationHRREncoder
    from rotation_hrr.variant_enumeration import canon

    encs = [RotationHRREncoder(d=d, n_max=ranges[0], n_max_depth=ranges[1], seed=s) for s in seeds]
    out = np.empty((len(pairs), len(seeds), len(settings)))
    start = 0
    while start < len(pairs):
        index: dict = {}
        trees: list = []
        ia, ib = [], []
        stop = start
        while stop < len(pairs) and (len(trees) < max_trees or stop == start):
            for t, side in ((pairs[stop][0], ia), (pairs[stop][1], ib)):
                k = canon(t)
                if k not in index:
                    index[k] = len(trees)
                    trees.append(t)
                side.append(index[k])
            stop += 1
        batch = Batch(trees)
        ia, ib = np.array(ia), np.array(ib)
        for si, enc in enumerate(encs):
            for ki, (a, b) in enumerate(settings):
                out[start:stop, si, ki] = angular(batch.vectors(enc, a, b), ia, ib)
        start = stop
    return out
