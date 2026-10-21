"""
HRR's positions: every activity sits at its average place over every order the variant allows,
each order counted once.

The reference is evaluation/orders.py, which works only from which activity must come before which (it
never sees the tree formula in rotation_hrr/tree_utils.py), and is itself checked here against
enumerating every order.  Every check runs on every shape up to N_MAX activities
(evaluation/probes.shapes); evaluation/experiments/21_positions.py runs the same checks up to 9 activities.  Positions
use no random numbers and no knob, so nothing here depends on a seed.

  exact      position = average place over every order
  order      an activity that must come before another is placed before it
  bounds     every position lies between the earliest and latest place possible
  reversal   reading the variant backwards maps place p to n - 1 - p
  forms      every way of writing the variant (any order of a block's children) gives the same
             positions
  depth      depth = number of operators between the root and the activity
"""

from fractions import Fraction

import pytest

from evaluation import probes
from evaluation.orders import (all_orders, backwards, leaf_depths, mean_positions, place_bounds,
                         precedence, violations, written_forms)
from rotation_hrr.tree_utils import tree_to_positioned_sequence
from rotation_hrr.variant_enumeration import leaf, par, seq, tree_str

N_MAX = 7          # every shape up to here; evaluation/experiments/21_positions.py goes to 9
N_BRUTE = 6        # the reference itself is checked against every order up to here
TOL = 1e-12

SHAPES = [t for n in range(1, N_MAX + 1) for t in probes.shapes(n)]


def positions(t):
    return [p for _, p, _ in tree_to_positioned_sequence(t)[0]]


def by_label(t):
    return {a: (p, d) for a, p, d in tree_to_positioned_sequence(t)[0]}


# ---------------------------------------------------------------------------
# The reference
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(1, N_BRUTE + 1))
def test_reference_equals_every_order_enumerated(n):
    for t in probes.shapes(n):
        orders = list(all_orders(t))
        brute = [Fraction(sum(o.index(j) for o in orders), len(orders)) for j in range(n)]
        assert mean_positions(t) == brute, tree_str(t)


def test_reference_on_a_hand_count():
    # ∧(A, →(B, C)) allows ABC, BAC, BCA: A at 0, 1, 2; B at 1, 0, 0; C at 2, 2, 1.
    t = par(leaf("A"), seq(leaf("B"), leaf("C")))
    assert mean_positions(t) == [Fraction(1), Fraction(1, 3), Fraction(5, 3)]


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", range(1, N_MAX + 1))
def test_position_is_the_average_place_over_every_order(n):
    for t in probes.shapes(n):
        err = max(abs(p - float(m)) for p, m in zip(positions(t), mean_positions(t)))
        assert err < TOL, f"{tree_str(t)}: off by {err}"


def test_nested_case_the_previous_rule_got_wrong():
    # ∧(A, →(B, ∧(C, →(D, E)))): B comes before C, D and E, and D before E.  A can
    # stand anywhere, and C anywhere after B.  Counting the 10 orders: A 2, B 0.2,
    # C 2.6, D 1.8, E 3.4.  The previous rule spaced D and E by the inner block
    # alone: D 1.933, E 3.267.
    t = par(leaf("A"), seq(leaf("B"), par(leaf("C"), seq(leaf("D"), leaf("E")))))
    p = {a: x for a, (x, _) in by_label(t).items()}
    assert p == pytest.approx({"A": 2.0, "B": 0.2, "C": 2.6, "D": 1.8, "E": 3.4}, abs=TOL)


@pytest.mark.parametrize("t", SHAPES, ids=tree_str)
def test_order_is_kept(t):
    n, pred = precedence(t)
    p = positions(t)
    for j in range(n):
        for i in range(n):
            if pred[j] >> i & 1:
                assert p[i] < p[j]


@pytest.mark.parametrize("t", SHAPES, ids=tree_str)
def test_position_between_earliest_and_latest_place(t):
    for p, (lo, hi) in zip(positions(t), place_bounds(t)):
        assert lo - TOL <= p <= hi + TOL


@pytest.mark.parametrize("t", SHAPES, ids=tree_str)
def test_reading_backwards_mirrors_positions(t):
    fwd, rev = by_label(t), by_label(backwards(t))
    n = len(fwd)
    for a, (p, d) in fwd.items():
        assert rev[a][0] == pytest.approx(n - 1 - p, abs=TOL)
        assert rev[a][1] == d


@pytest.mark.parametrize("t", SHAPES, ids=tree_str)
def test_every_written_form_gets_the_same_positions(t):
    ref = by_label(t)
    for form in written_forms(t):
        assert by_label(form) == ref, tree_str(form)


@pytest.mark.parametrize("t", SHAPES, ids=tree_str)
def test_depth_counts_operators_above(t):
    assert [d for _, _, d in tree_to_positioned_sequence(t)[0]] == leaf_depths(t)


# ---------------------------------------------------------------------------
# The checks can fail: correct positions, broken on purpose
# ---------------------------------------------------------------------------

def test_checks_flag_broken_positions():
    t = seq(leaf("A"), par(leaf("B"), seq(leaf("C"), leaf("D"))), leaf("E"))
    items = tree_to_positioned_sequence(t)[0]
    assert violations(t, items) == {"max_error": pytest.approx(0, abs=TOL), "order": 0, "bounds": 0}
    swapped = [items[0], items[1], items[3], items[2], items[4]]      # C and D change places
    swapped = [(a, p, d) for (a, _, d), (_, p, _) in zip(items, swapped)]
    v = violations(t, swapped)
    assert v["order"] > 0 and v["max_error"] > 0.1
    late = [(a, p + (3.0 if a == "A" else 0.0), d) for a, p, d in items]  # A after its latest place
    v = violations(t, late)
    assert v["bounds"] == 1 and v["order"] > 0
