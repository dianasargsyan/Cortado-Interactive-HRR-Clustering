"""
tree_to_positioned_sequence() and the encode() / encode_tree() methods that use its output, on
hand-built trees (conftest.py); the expected positions and depths follow the rules in
rotation_hrr/tree_utils.py.
"""

import pytest
import numpy as np

from evaluation.tests.conftest import make_leaf, make_seq, make_par, make_loop
from rotation_hrr.tree_utils import tree_to_positioned_sequence
from rotation_hrr.encoder import RotationHRREncoder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _positions(tree):
    items, _ = tree_to_positioned_sequence(tree)
    return {label: pos for label, pos, _ in items}


def _depths(tree):
    items, _ = tree_to_positioned_sequence(tree)
    return {label: depth for label, _, depth in items}


def _pos_list(tree):
    items, _ = tree_to_positioned_sequence(tree)
    return [(label, pos, depth) for label, pos, depth in items]


# ---------------------------------------------------------------------------
# Pure sequence
# ---------------------------------------------------------------------------

def test_pure_sequence_positions():
    """seq(A,B,C,D,E,F) → positions 0..5, all depth 0."""
    t = make_seq(make_leaf("A"), make_leaf("B"), make_leaf("C"),
                 make_leaf("D"), make_leaf("E"), make_leaf("F"))
    items, n = tree_to_positioned_sequence(t)
    assert n == 6
    labels = [x[0] for x in items]
    assert labels == ["A", "B", "C", "D", "E", "F"]
    for i, (label, pos, depth) in enumerate(items):
        assert pos == pytest.approx(float(i)), f"{label}: expected {i}, got {pos}"
        assert depth == 0


# ---------------------------------------------------------------------------
# Flat PAR: center assignment
# ---------------------------------------------------------------------------

def test_flat_par_center_two():
    """seq(A, par(B,C), D, E) → B@1.5, C@1.5; D@3, E@4."""
    t = make_seq(
        make_leaf("A"),
        make_par(make_leaf("B"), make_leaf("C")),
        make_leaf("D"),
        make_leaf("E"),
    )
    p = _positions(t)
    assert p["A"] == pytest.approx(0.0)
    assert p["B"] == pytest.approx(1.5)
    assert p["C"] == pytest.approx(1.5)
    assert p["D"] == pytest.approx(3.0)
    assert p["E"] == pytest.approx(4.0)


def test_three_way_par():
    """seq(A, par(B,C,D), E) → B,C,D all @2, E@4."""
    t = make_seq(
        make_leaf("A"),
        make_par(make_leaf("B"), make_leaf("C"), make_leaf("D")),
        make_leaf("E"),
    )
    p = _positions(t)
    assert p["A"] == pytest.approx(0.0)
    assert p["B"] == pytest.approx(2.0)
    assert p["C"] == pytest.approx(2.0)
    assert p["D"] == pytest.approx(2.0)
    assert p["E"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# PAR with SEQ child: order statistic formula
# ---------------------------------------------------------------------------

def test_par_with_seq_child():
    """seq(A, par(B,C, seq(D,E)), F) → B@2.5, C@2.5, D@5/3, E@10/3, F@5."""
    t = make_seq(
        make_leaf("A"),
        make_par(
            make_leaf("B"),
            make_leaf("C"),
            make_seq(make_leaf("D"), make_leaf("E")),
        ),
        make_leaf("F"),
    )
    p = _positions(t)
    assert p["A"] == pytest.approx(0.0)
    assert p["B"] == pytest.approx(2.5)
    assert p["C"] == pytest.approx(2.5)
    assert p["D"] == pytest.approx(5 / 3)
    assert p["E"] == pytest.approx(10 / 3)
    assert p["F"] == pytest.approx(5.0)


def test_par_with_seq_child_two():
    """seq(A, par(B, seq(C,D,E))) → B@2.5, C@1.25, D@2.5, E@3.75."""
    t = make_seq(
        make_leaf("A"),
        make_par(
            make_leaf("B"),
            make_seq(make_leaf("C"), make_leaf("D"), make_leaf("E")),
        ),
    )
    p = _positions(t)
    assert p["A"] == pytest.approx(0.0)
    assert p["B"] == pytest.approx(2.5)
    assert p["C"] == pytest.approx(1.25)
    assert p["D"] == pytest.approx(2.5)
    assert p["E"] == pytest.approx(3.75)


def test_par_with_only_seq_child_collapses():
    """seq(A, par(seq(B,C,D))) → B@1, C@2, D@3 (degenerate: collapses to seq positions)."""
    t = make_seq(
        make_leaf("A"),
        make_par(make_seq(make_leaf("B"), make_leaf("C"), make_leaf("D"))),
    )
    p = _positions(t)
    assert p["A"] == pytest.approx(0.0)
    assert p["B"] == pytest.approx(1.0)
    assert p["C"] == pytest.approx(2.0)
    assert p["D"] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Nested PAR: depth assignment and center alignment
# ---------------------------------------------------------------------------

def test_par_root_leaves_depth_zero():
    """Direct leaf children of a root PAR have depth 0 (no operator change yet).
    par(A, seq(B,C)) → A=depth 0 (direct leaf of root PAR), B,C=depth 1.
    """
    t = make_par(make_leaf("A"), make_seq(make_leaf("B"), make_leaf("C")))
    d = _depths(t)
    assert d["A"] == 0
    assert d["B"] == 1
    assert d["C"] == 1


def test_depths_pure_seq_are_zero():
    """All activities in a pure SEQ have depth 0."""
    t = make_seq(make_leaf("A"), make_leaf("B"), make_leaf("C"))
    d = _depths(t)
    assert all(v == 0 for v in d.values())


def test_depths_inside_par_are_zero():
    """Direct leaf children of a root PAR have depth 0 (root operator = depth 0)."""
    t = make_par(make_leaf("A"), make_leaf("B"), make_leaf("C"))
    d = _depths(t)
    assert all(v == 0 for v in d.values())


# ---------------------------------------------------------------------------
# Constraint validation
# ---------------------------------------------------------------------------

def test_multiple_seq_children_raises():
    """par(seq(A,B), seq(C,D)) → ValueError (two SEQ children)."""
    t = make_par(
        make_seq(make_leaf("A"), make_leaf("B")),
        make_seq(make_leaf("C"), make_leaf("D")),
    )
    with pytest.raises(ValueError, match="more than one sequence child"):
        tree_to_positioned_sequence(t)


def test_seq_inside_par_with_par_grandchild():
    """par(A, seq(B, par(C,D), E)): PAR grandchild of SEQ inside PAR is supported.
    par has N=5 leaves. seq child has m=4 leaves, spacing=6/5=1.2.
    B (j=1): 0+1.2-1=0.2, depth=1.
    par(C,D): j_first=2, j_last=3, center=0+2.5*1.2-1=2.0, inner_start=1.5 → C,D@2.0 depth=2.
    E (j=4): 0+4.8-1=3.8, depth=1.
    A (leaf of root PAR): center=2.0, depth=0.
    """
    t = make_par(
        make_leaf("A"),
        make_seq(make_leaf("B"), make_par(make_leaf("C"), make_leaf("D")), make_leaf("E")),
    )
    p = _positions(t)
    d = _depths(t)
    assert p["A"] == pytest.approx(2.0)
    assert p["B"] == pytest.approx(0.2)
    assert p["C"] == pytest.approx(2.0)
    assert p["D"] == pytest.approx(2.0)
    assert p["E"] == pytest.approx(3.8)
    assert d["A"] == 0
    assert d["B"] == 1
    assert d["C"] == 2
    assert d["D"] == 2
    assert d["E"] == 1


# ---------------------------------------------------------------------------
# Counter advancement (no collateral shift)
# ---------------------------------------------------------------------------

def test_no_collateral_shift():
    """Activities after a PAR block land at the same position as in the fully sequential trace."""
    t_par = make_seq(
        make_leaf("A"),
        make_par(make_leaf("B"), make_leaf("C")),
        make_leaf("D"),
        make_leaf("E"),
    )
    t_seq = make_seq(
        make_leaf("A"), make_leaf("B"), make_leaf("C"),
        make_leaf("D"), make_leaf("E"),
    )
    p_par = _positions(t_par)
    p_seq = _positions(t_seq)
    # D and E must be at the same positions in both trees
    assert p_par["D"] == pytest.approx(p_seq["D"])
    assert p_par["E"] == pytest.approx(p_seq["E"])


# ---------------------------------------------------------------------------
# Encoding correctness
# ---------------------------------------------------------------------------

def test_order_invariance_within_par():
    """encode(seq(A,par(B,C),D)) == encode(seq(A,par(C,B),D)): similarity 1.0."""
    enc = RotationHRREncoder(d=512, seed=42)
    t1 = make_seq(make_leaf("A"), make_par(make_leaf("B"), make_leaf("C")), make_leaf("D"))
    t2 = make_seq(make_leaf("A"), make_par(make_leaf("C"), make_leaf("B")), make_leaf("D"))
    b1 = enc.encode_tree(t1)
    b2 = enc.encode_tree(t2)
    assert enc.similarity(b1, b2) == pytest.approx(1.0, abs=1e-10)


def test_equidistance_flat_par():
    """encode(seq(A,par(B,C),D)) is equidistant (within tol) from the two sequential orderings."""
    enc = RotationHRREncoder(d=512, seed=42)
    t_par = make_seq(make_leaf("A"), make_par(make_leaf("B"), make_leaf("C")), make_leaf("D"))
    t_bc  = make_seq(make_leaf("A"), make_leaf("B"), make_leaf("C"), make_leaf("D"))
    t_cb  = make_seq(make_leaf("A"), make_leaf("C"), make_leaf("B"), make_leaf("D"))

    b_par = enc.encode_tree(t_par)
    b_bc  = enc.encode_tree(t_bc)
    b_cb  = enc.encode_tree(t_cb)

    sim_bc = enc.similarity(b_par, b_bc)
    sim_cb = enc.similarity(b_par, b_cb)
    assert abs(sim_bc - sim_cb) < 0.05, (
        f"PAR bundle not equidistant: sim(par,BC)={sim_bc:.4f}, sim(par,CB)={sim_cb:.4f}"
    )


def test_par_vs_seq_different():
    """encode(par(A,B,C,D,E,F,G)) differs from encode(seq(A,B,C,D,E,F,G))."""
    enc = RotationHRREncoder(d=512, seed=42)
    t_seq = make_seq(*[make_leaf(c) for c in "ABCDEFG"])
    t_par = make_par(*[make_leaf(c) for c in "ABCDEFG"])
    b_seq = enc.encode_tree(t_seq)
    b_par = enc.encode_tree(t_par)
    assert enc.similarity(b_seq, b_par) < 0.999


def test_depth_distinguishes_nesting_levels():
    """Deeper nesting (higher depth activities) produces more distinct encodings.
    seq(A, par(B,C)) vs seq(A, par(B, seq(C, par(D,E)))): the deeper tree
    should differ more from pure seq(A,B,C,D,E) when beta > 0.
    """
    enc = RotationHRREncoder(d=512, seed=42)
    t_seq    = make_seq(*[make_leaf(x) for x in "ABCDE"])
    t_shallow = make_seq(make_leaf("A"), make_par(make_leaf("B"), make_leaf("C"),
                                                   make_leaf("D"), make_leaf("E")))
    t_deep   = make_seq(make_leaf("A"),
                        make_par(make_leaf("B"),
                                 make_seq(make_leaf("C"),
                                          make_par(make_leaf("D"), make_leaf("E")))))

    b_seq     = enc.encode_tree(t_seq, beta=1.0)
    b_shallow = enc.encode_tree(t_shallow, beta=1.0)
    b_deep    = enc.encode_tree(t_deep, beta=1.0)

    sim_shallow = enc.similarity(b_seq, b_shallow)
    sim_deep    = enc.similarity(b_seq, b_deep)
    assert sim_deep < sim_shallow, (
        f"Expected deeper nesting to differ more from pure seq: "
        f"sim(seq,shallow)={sim_shallow:.4f}, sim(seq,deep)={sim_deep:.4f}"
    )


def test_deep_nesting_example1():
    """seq(A,B, par(C,seq(D,E),F), par(G,seq(H,par(I,J),K),L)): full position+depth trace.

    First PAR (_start=2, N=4, center=3.5, PAR at depth 1):
      C,F → pos=3.5, depth=1
      seq(D,E): spacing=5/3 → D@8/3, E@13/3, depth=2

    Second PAR (_start=6, N=6, center=8.5, PAR at depth 1):
      G,L → pos=8.5, depth=1
      seq(H,par(I,J),K): spacing=1.4
        H (j=1) → 6.4, depth=2
        par(I,J): allocated_center=8.5, inner_start=8.0, depth=3 → I,J@8.5
        K (j=4) → 10.6, depth=2
    """
    t = make_seq(
        make_leaf("A"), make_leaf("B"),
        make_par(make_leaf("C"), make_seq(make_leaf("D"), make_leaf("E")), make_leaf("F")),
        make_par(make_leaf("G"),
                 make_seq(make_leaf("H"), make_par(make_leaf("I"), make_leaf("J")), make_leaf("K")),
                 make_leaf("L")),
    )
    p = _positions(t)
    d = _depths(t)

    assert p["A"] == pytest.approx(0.0)
    assert p["B"] == pytest.approx(1.0)
    assert p["C"] == pytest.approx(3.5)
    assert p["D"] == pytest.approx(8 / 3)
    assert p["E"] == pytest.approx(13 / 3)
    assert p["F"] == pytest.approx(3.5)
    assert p["G"] == pytest.approx(8.5)
    assert p["H"] == pytest.approx(6.4)
    assert p["I"] == pytest.approx(8.5)
    assert p["J"] == pytest.approx(8.5)
    assert p["K"] == pytest.approx(10.6)
    assert p["L"] == pytest.approx(8.5)

    assert d["A"] == 0
    assert d["B"] == 0
    assert d["C"] == 1
    assert d["D"] == 2
    assert d["E"] == 2
    assert d["F"] == 1
    assert d["G"] == 1
    assert d["H"] == 2
    assert d["I"] == 3
    assert d["J"] == 3
    assert d["K"] == 2
    assert d["L"] == 1


def test_deep_nesting_example2():
    """par(A,B, seq(C, par(D,E,seq(F,G),H))): full position+depth trace.

    Each child's own place q maps into its parent's: in a sequence, shifted by the
    activities before it; in a block of N, a child of n activities maps q to
    (q + 1)(N + 1)/(n + 1) - 1.
    Root PAR (N=8, depth 0):
      A,B (n=1) → (1)(9/2) - 1 = 3.5, depth=0
      seq(C, par(D,E,seq(F,G),H)) (n=6, map q → (q + 1)·9/7 - 1):
        own places: C 0; inner PAR (N=5) at 1..5:
          D,E,H (n=1) → 1 + 2 = 3; seq(F,G) (n=2, q → (q + 1)·2 - 1) → F 1 + 1, G 1 + 3
        C → 2/7≈0.286 (depth 1); D,E,H → 29/7≈4.143 (depth 2);
        F → 20/7≈2.857, G → 38/7≈5.429 (depth 3)
    (Before 1.3b the inner sequence was spaced by the inner block alone:
    F 22/7, G 36/7, not the average place over the variant's orders.)
    """
    t = make_par(
        make_leaf("A"), make_leaf("B"),
        make_seq(
            make_leaf("C"),
            make_par(make_leaf("D"), make_leaf("E"),
                     make_seq(make_leaf("F"), make_leaf("G")),
                     make_leaf("H")),
        ),
    )
    p = _positions(t)
    d = _depths(t)

    assert p["A"] == pytest.approx(3.5)
    assert p["B"] == pytest.approx(3.5)
    assert p["C"] == pytest.approx(2 / 7)
    assert p["D"] == pytest.approx(29 / 7)
    assert p["E"] == pytest.approx(29 / 7)
    assert p["F"] == pytest.approx(20 / 7)
    assert p["G"] == pytest.approx(38 / 7)
    assert p["H"] == pytest.approx(29 / 7)

    assert d["A"] == 0
    assert d["B"] == 0
    assert d["C"] == 1
    assert d["D"] == 2
    assert d["E"] == 2
    assert d["F"] == 3
    assert d["G"] == 3
    assert d["H"] == 2


def test_backward_compat_encode_no_positions():
    """encode(activities) without positions or depths equals explicit positions 0, 1, 2, ... at depth 0."""
    enc = RotationHRREncoder(d=64, seed=0)
    acts = ["A", "B", "C", "D"]
    b_default = enc.encode(acts)
    b_explicit = enc.encode(acts, positions=np.arange(4, dtype=float), depths=np.zeros(4))
    np.testing.assert_allclose(b_default, b_explicit)


# ---------------------------------------------------------------------------
# Fallthrough (Cortado's unstructured block) is read as PAR
# ---------------------------------------------------------------------------

def _fallthrough(*children):
    from cortado_core.subprocess_discovery.concurrency_trees.cTrees import ConcurrencyTree, cTreeOperator
    node = ConcurrencyTree(children=list(children), op=cTreeOperator.Fallthrough)
    for child in children:
        child.parent = node
    return node


def test_fallthrough_places_like_a_parallel_block():
    """→(A, ✕(B, C, D), E) gets exactly the places and depths of →(A, ∧(B, C, D), E): Cortado lists a
    Fallthrough's activities alphabetically, so no order is read from them."""
    from evaluation.tests.conftest import make_leaf, make_par, make_seq
    L = lambda *xs: [make_leaf(x) for x in xs]
    ft = make_seq(make_leaf("A"), _fallthrough(*L("B", "C", "D")), make_leaf("E"))
    par = make_seq(make_leaf("A"), make_par(*L("B", "C", "D")), make_leaf("E"))
    assert tree_to_positioned_sequence(ft)[0] == tree_to_positioned_sequence(par)[0]
    from rotation_hrr.tree_utils import tree_to_sequence
    assert tree_to_sequence(ft) == tree_to_sequence(par)


def test_fallthrough_order_and_names_change_nothing():
    """The same block listed in another order gives the same HRR vector, as for ∧, and the same as
    the block written as ∧."""
    import numpy as np
    from rotation_hrr.encoder import RotationHRREncoder
    from evaluation.tests.conftest import make_leaf, make_par, make_seq
    enc = RotationHRREncoder(d=256, n_max=20, seed=3)
    v1 = enc.encode_tree(make_seq(make_leaf("A"), _fallthrough(make_leaf("B"), make_leaf("C"))))
    v2 = enc.encode_tree(make_seq(make_leaf("A"), _fallthrough(make_leaf("C"), make_leaf("B"))))
    v3 = enc.encode_tree(make_seq(make_leaf("A"), make_par(make_leaf("B"), make_leaf("C"))))
    assert np.allclose(v1, v2) and np.allclose(v1, v3)
