"""
Tree factories shared by the tests (make_leaf, make_seq, make_par, make_loop): Cortado trees built
directly, without an event log.  Plain functions, not fixtures, so test modules can call them at
module level.  rSib pointers are left as None: the encoder, the tree utilities and the baselines
only traverse node.children.
"""

import os
import sys

# pytest.ini sets the path; this covers running a test file directly
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_tests = os.path.dirname(__file__)
for _p in [_root, _tests]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cortado_core.subprocess_discovery.concurrency_trees.cTrees import (
    ConcurrencyTree,
    cTreeOperator,
)


# ---------------------------------------------------------------------------
# Tree factory functions
# ---------------------------------------------------------------------------

def make_leaf(label: str) -> ConcurrencyTree:
    """Create a leaf (activity) node."""
    return ConcurrencyTree(label=label, op=None)


def make_seq(*children: ConcurrencyTree) -> ConcurrencyTree:
    """Create a SEQ (Sequential) operator node with the given children."""
    node = ConcurrencyTree(children=list(children), op=cTreeOperator.Sequential)
    for child in children:
        child.parent = node
    return node


def make_par(*children: ConcurrencyTree) -> ConcurrencyTree:
    """Create a PAR (Concurrent) operator node with the given children."""
    node = ConcurrencyTree(children=list(children), op=cTreeOperator.Concurrent)
    for child in children:
        child.parent = node
    return node


def make_loop(*children: ConcurrencyTree) -> ConcurrencyTree:
    """Create a LOOP operator node with the given children."""
    node = ConcurrencyTree(children=list(children), op=cTreeOperator.Loop)
    for child in children:
        child.parent = node
    return node

