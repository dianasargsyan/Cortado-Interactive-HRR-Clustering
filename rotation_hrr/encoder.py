"""
Rotation-HRR: a concurrency tree as one vector.

Each activity a has a fixed random unit vector v_a.  A variant's vector is the sum over its
activities of v_a turned by an angle that depends on where the activity sits:

    E(t) = sum_i  R(alpha * p_i * theta + beta * k_i * theta') v_{a_i}

p_i is the activity's average position over every order the variant allows and k_i its nesting
depth (tree_utils.tree_to_positioned_sequence).  R turns each of the d/2 two-dimensional blocks
of a vector by its own angle.  The block frequencies theta (position) and theta' (depth) are
spread geometrically from theta_max down to pi / (1.5 n), as in rotary position embeddings
(Su et al. 2024), with n the longest variant (or the deepest nesting) the encoder is built for.

The blocks come in pairs with the same position frequency; depth turns the first block of a pair
by +theta' and the second by -theta'.  Averaged over a pair, an activity moved by (dp, dk) then
contributes cos(alpha dp theta) cos(beta dk theta'), so a move scores the same whichever way the
depth changed.

alpha and beta (0 to 1) scale how much order and nesting count: alpha = beta = 0 gives a bag of
activities.  Variants are compared by the angle between their vectors.
"""

from __future__ import annotations

import hashlib
from typing import Optional

import numpy as np


class RotationHRREncoder:
    """Encodes concurrency trees as d-dimensional vectors.

    Parameters
    ----------
    d : int
        Dimension, a multiple of 4 (two-dimensional blocks, in pairs).
    n_max : int
        Longest variant to tell positions apart in; sets the slowest position frequency.
    theta_max : float
        Fastest frequency, in radians per position step.
    seed : int
        Seed of the activity vectors.
    n_max_depth : int
        Deepest nesting to tell apart; sets the slowest depth frequency.
    theta_max_depth : float, optional
        Fastest depth frequency (theta_max if not given).
    """

    def __init__(self, d: int = 512, n_max: int = 100, theta_max: float = 1.0, seed: int = 42,
                 n_max_depth: int = 8, theta_max_depth: Optional[float] = None):
        if d % 4 != 0:
            raise ValueError(f"d must be a multiple of 4 (blocks come in pairs), got {d}")
        self.d = d
        self.n_max = n_max
        self.theta_max = theta_max
        self.seed = seed
        self.n_max_depth = n_max_depth
        self.theta_max_depth = theta_max if theta_max_depth is None else theta_max_depth

        m = d // 4
        k = np.arange(m, dtype=np.float64)
        theta_min = np.pi / (n_max * 1.5)
        pos = np.array([theta_max]) if m == 1 else theta_max * (theta_min / theta_max) ** (k / (m - 1))
        self.thetas = np.repeat(pos, 2)

        theta_min_depth = np.pi / (self.n_max_depth * 1.5)
        dep = (np.array([self.theta_max_depth]) if m == 1 else
               self.theta_max_depth * (theta_min_depth / self.theta_max_depth) ** (k / (m - 1)))
        self.depth_thetas = np.repeat(dep, 2) * np.tile([1.0, -1.0], m)

        self._label_table: dict[str, np.ndarray] = {}

    def _label_seed(self, label: str) -> int:
        """A seed from (encoder seed, label).  hashlib, since Python salts hash() per process."""
        h = hashlib.blake2b(f"{self.seed}\x00{label}".encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(h, "big")

    def get_label_vector(self, activity: str) -> np.ndarray:
        """The activity's unit vector.  Each label draws from its own generator, so its vector
        does not depend on which labels were seen before it."""
        if activity not in self._label_table:
            v = np.random.default_rng(self._label_seed(activity)).standard_normal(self.d)
            self._label_table[activity] = v / np.linalg.norm(v)
        return self._label_table[activity]

    def encode(self, activities: list[str], positions: Optional[np.ndarray] = None,
               depths: Optional[np.ndarray] = None, alpha: float = 1.0, beta: float = 1.0,
               activity_weights: Optional[dict[str, float]] = None) -> np.ndarray:
        """The (unnormalised) vector of activities at the given positions (default 0, 1, 2, ...)
        and depths (default 0), each label vector scaled by its weight (default 1)."""
        n = len(activities)
        if n == 0:
            return np.zeros(self.d)
        V = np.stack([self.get_label_vector(a) for a in activities])
        if activity_weights:
            V = V * np.array([activity_weights.get(a, 1.0) for a in activities])[:, None]
        pos = np.arange(n, dtype=np.float64) if positions is None else np.asarray(positions, dtype=np.float64)
        dep = np.zeros(n) if depths is None else np.asarray(depths, dtype=np.float64)

        angles = np.outer(pos, alpha * self.thetas) + np.outer(dep, beta * self.depth_thetas)
        c, s = np.cos(angles), np.sin(angles)
        x, y = V[:, 0::2], V[:, 1::2]
        rotated = np.empty((n, self.d))
        rotated[:, 0::2] = c * x - s * y
        rotated[:, 1::2] = s * x + c * y
        return rotated.sum(axis=0)

    def encode_tree(self, tree, alpha: float = 1.0, beta: float = 1.0,
                    activity_weights: Optional[dict[str, float]] = None) -> np.ndarray:
        """The vector of a concurrency tree: each activity at its average position and depth."""
        from .tree_utils import tree_to_positioned_sequence
        items, _ = tree_to_positioned_sequence(tree)
        return self.encode([x[0] for x in items],
                           positions=np.array([x[1] for x in items], dtype=float),
                           depths=np.array([x[2] for x in items], dtype=int),
                           alpha=alpha, beta=beta, activity_weights=activity_weights)

    @staticmethod
    def similarity(u: np.ndarray, v: np.ndarray) -> float:
        """Cosine between two vectors (0 if either is zero)."""
        nu, nv = np.linalg.norm(u), np.linalg.norm(v)
        if nu < 1e-12 or nv < 1e-12:
            return 0.0
        return float(u @ v / (nu * nv))
