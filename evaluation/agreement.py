"""
Rank agreement between two runs: Kendall's tau-b over all pairwise distances.  For every two
pairs of variants it asks whether both runs agree on which is closer; without ties, (1 + tau) / 2
is the share of comparisons on which they agree, and tau-b corrects for ties.  O(n log n)
(Knight 1966, as implemented in scipy).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import kendalltau


def tau_b(x, y) -> float:
    """Kendall's tau-b of two equally long arrays (values or ranks: the result is the same);
    NaN if either is constant."""
    x, y = np.asarray(x), np.asarray(y)
    if x.size < 2 or np.all(x == x.flat[0]) or np.all(y == y.flat[0]):
        return float("nan")
    return float(kendalltau(x, y).statistic)
