"""
k-medoids on a precomputed distance matrix, through the ``kmedoids`` package (Schubert &
Rousseeuw 2021).  It never averages points, so every method, with vectors or only distances,
clusters through the same code.
"""

from __future__ import annotations

import numpy as np


def kmedoids_cluster(dist_matrix: np.ndarray, n_clusters: int, algorithm: str = "pam",
                     seed: int = 0, max_iter: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """(medoids, labels): the sorted medoid indices and each variant's cluster, 1-indexed.

    algorithm "pam" is exact PAM (Kaufman & Rousseeuw 1990), "fasterpam" its fast variant
    (Schubert & Rousseeuw 2021), whose eager swaps can reach a different local optimum.  Both
    start from BUILD, which is deterministic; *seed* only breaks ties, so a change in the
    clustering after an edit comes from the edit, not from the start.
    """
    import kmedoids as _km

    if algorithm not in ("pam", "fasterpam"):
        raise ValueError(f"algorithm must be 'pam' or 'fasterpam', got {algorithm!r}")
    D = np.asarray(dist_matrix, dtype=np.float64)
    n = len(D)
    if n_clusters >= n:
        return np.arange(n), np.arange(1, n + 1)
    fn = _km.pam if algorithm == "pam" else _km.fasterpam
    res = fn(D, n_clusters, init="build", max_iter=max_iter, random_state=seed)
    medoids = np.sort(np.asarray(res.medoids, dtype=int))
    labels = np.argmin(D[medoids], axis=0) + 1
    return medoids, labels
