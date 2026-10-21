"""
A log's variants under the analyst's edits, applied in one fixed order so the result never
depends on the order the analyst made them in:

  1. equivalences   every alias renamed to its canonical name; everything after this sees
                    canonical names only
  2. ignore         the ignored activities removed from the trees, which stay in normal form
  3. alpha, beta    the structural knobs

The frequency ranges come from the log as loaded and d from config.D: no edit changes either.  A
variant whose every activity is ignored has no vector left; it is at distance 0 from another such
variant and 0.5 (unrelated) from every other.
"""

from __future__ import annotations

import numpy as np

from rotation_hrr.domain_knowledge import DomainKnowledge
from evaluation import config
from evaluation.batch_hrr import Batch
from evaluation.methods import hrr_ranges
from rotation_hrr.encoder import RotationHRREncoder
from rotation_hrr.tree_rewrites import drop_activities, relabel


class EditedLog:
    """*trees* under the edits in *dk*, encoded with seed *seed* at dimension *d*."""

    def __init__(self, trees, dk: DomainKnowledge | None = None, d: int = config.D, seed: int = 42,
                 ranges: tuple[int, int] | None = None):
        dk = dk or DomainKnowledge()
        self.dk, self.n = dk, len(trees)
        self.ranges = ranges or hrr_ranges(trees)
        canonical = {a: c for c, aliases in dk.activity_equivalences.items() for a in aliases}
        renamed = [relabel(t, canonical) for t in trees] if canonical else list(trees)      # 1
        ignored = {canonical.get(a, a) for a in dk.ignored_activities}
        if ignored:                                                                        # 2
            renamed = [drop_activities(t, ignored) for t in renamed]
        self.trees = renamed
        self.kept = np.array([t is not None for t in renamed])
        self.batch = Batch([t for t in renamed if t is not None])
        self.d, self.seed, self._encs = d, seed, {}

    def encoder(self, seed: int) -> RotationHRREncoder:
        """The encoder for one seed (the trees do not depend on it)."""
        if seed not in self._encs:
            self._encs[seed] = RotationHRREncoder(d=self.d, n_max=self.ranges[0],
                                                  n_max_depth=self.ranges[1], seed=seed)
        return self._encs[seed]

    def vectors(self, alpha: float, beta: float, seed: int | None = None) -> np.ndarray:
        """(n, d): every variant's vector at (alpha, beta); zero for a variant with none left."""
        X = np.zeros((self.n, self.d))
        X[self.kept] = self.batch.vectors(self.encoder(self.seed if seed is None else seed), alpha, beta)
        return X

    def similarities(self, alpha: float, beta: float, seed: int | None = None) -> np.ndarray:
        """(n, n) cosines between every pair of variants."""
        X = self.vectors(alpha, beta, seed)
        nrm = np.linalg.norm(X, axis=1, keepdims=True)
        Xn = X / np.where(nrm < 1e-12, 1.0, nrm)
        return Xn @ Xn.T

    def distances(self, alpha: float, beta: float, seed: int | None = None) -> np.ndarray:
        """(n, n) angular distances, arccos(cos) / pi."""
        D = np.arccos(np.clip(self.similarities(alpha, beta, seed), -1.0, 1.0)) / np.pi
        empty = ~self.kept
        if empty.any():
            D[np.ix_(empty, empty)] = 0.0
        np.fill_diagonal(D, 0.0)
        return D

    def has_vector(self) -> np.ndarray:
        """Which variants still have a vector (not every activity ignored)."""
        return self.kept.copy()
