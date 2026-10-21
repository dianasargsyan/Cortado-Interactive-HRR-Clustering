"""
The probe universe (evaluation/universe.py): its size, and the pair flags on cases small enough to check
by hand.
"""

import pytest

from evaluation import universe as U
from rotation_hrr.variant_enumeration import canon, leaf as L, par, seq


def test_sizes():
    c = U.corpora()
    assert len(c["universe_4"]) == 7 + 100 + 2279
    assert {k: len(v) for k, v in c.items() if k != "universe_4"} == {
        "universe_5_AAAAA": 42, "universe_5_AAAAB": 154, "universe_5_AAABB": 267,
        "universe_5_AAABC": 493, "universe_5_AABBC": 689, "universe_5_AABCD": 1277,
        "universe_5_ABCDE": 2371}
    for trees in c.values():
        assert len({canon(t) for t in trees}) == len(trees)      # one written form each


CASES = [   # (a, b, flags that differ)
    (seq(L("A"), L("B")), seq(L("B"), L("A")), {"order"}),
    (seq(L("A"), L("B")), par(L("A"), L("B")), {"shape", "parallel", "concurrency"}),
    (seq(L("A"), L("A")), par(L("A"), L("A")), {"shape", "parallel", "concurrency"}),
    (seq(L("A"), L("A"), L("B")), seq(L("A"), L("B"), L("B")), {"repeats"}),
    (seq(L("A"), L("B"), L("A")), seq(L("A"), L("A"), L("B")), {"order"}),
    (seq(L("A"), L("B")), seq(L("A"), L("B"), L("A")), {"length", "repeats", "shape", "order"}),
    # every relation switches between ordered and parallel; none is ordered both ways
    (seq(L("A"), par(L("B"), L("C"))), par(L("A"), seq(L("B"), L("C"))), {"shape", "parallel"}),
    (seq(L("A"), L("B"), L("C")), seq(L("A"), par(L("B"), L("C"))),
     {"shape", "parallel", "concurrency", "depth"}),
]


@pytest.mark.parametrize("a, b, differ", CASES)
def test_flags(a, b, differ):
    P = U.pair_flags(U.features([a, b]))
    assert {f for f in U.FLAGS if P[f][0, 1]} == differ
    assert all(P[f][0, 1] == P[f][1, 0] for f in U.FLAGS)
