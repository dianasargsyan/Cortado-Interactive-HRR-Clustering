"""
The methods HRR is compared with, each as its paper defines it, without tuning (registered in
evaluation/methods.py).  Sequence methods read a variant left to right with every parallel block's
activities sorted (tree_to_sequence); nothing is added for concurrency.  Tree methods get the
tree with every parallel block's children sorted (tree_rewrites.sort_parallel); operators are
node labels.

  one-hot        Song, Günther & van der Aalst 2009, sec. 3: the activity profile, how often each
                 activity occurs (the sum of the activities' one-hot vectors), and their Jaccard
                 distance (sec. 4.1) on these counts
  3-grams        Bose & van der Aalst 2009, sec. 3.2: counts of every run of three activities,
                 Euclidean distance
  pq-grams       Augsten, Böhlen & Gamper 2010, Def. 6.1 to 6.6: the bag of label tuples of
                 every pq-gram of the extended tree, the normalised pq-gram distance; p = 2,
                 q = 3 (the paper's running example and one of its experimental settings)
  binary branch  Yang, Kalnis & Tung 2005, Def. 2 to 4: counts of (node, first child, next
                 sibling) in the left-child right-sibling binary tree, epsilon for a missing one;
                 L1 distance (BDist)
  APTED          Pawlik & Augsten 2015, 2016: tree edit distance with unit costs, through the
                 authors' Java implementation (evaluation/java_apted/; the Python port, the apted package,
                 is kept as the tests' cross-check)

All counts are integers and every distance is computed in integer arithmetic before the final
division or square root, so identical representations give exactly 0.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse

from rotation_hrr.tree_utils import tree_to_sequence
from rotation_hrr.tree_rewrites import sort_parallel

#: Labels added by a method (pq-gram dummies, binary-branch epsilon, operator nodes) start with
#: NUL, which XML 1.0 forbids, so they can never equal an activity name read from an XES log.
DUMMY = "\x00*"
EPSILON = "\x00eps"


def _is_leaf(node) -> bool:
    return getattr(node, "label", None) is not None


def node_label(node) -> str:
    """An activity's name, or an operator's name marked as an operator."""
    return node.label if _is_leaf(node) else "\x00" + node.op.name


def sorted_tree(t):
    """The tree with every parallel block's children sorted."""
    return sort_parallel(t)


# ---------------------------------------------------------------------------
# Counting representations and their exact pairwise distances
# ---------------------------------------------------------------------------


def count_matrix(bags: list[Counter]) -> sparse.csr_matrix:
    """One row per bag, one column per distinct item, integer counts."""
    vocab: dict = {}
    rows, cols, vals = [], [], []
    for r, bag in enumerate(bags):
        for item, n in bag.items():
            rows.append(r)
            cols.append(vocab.setdefault(item, len(vocab)))
            vals.append(n)
    return sparse.csr_matrix((np.asarray(vals, dtype=np.int64), (rows, cols)),
                             shape=(len(bags), max(len(vocab), 1)), dtype=np.int64)


def pairwise_min_sum(X: sparse.csr_matrix, Y: sparse.csr_matrix | None = None) -> np.ndarray:
    """sum_k min(x_k, y_k) for every pair of rows, exactly: min(a, b) = sum over t >= 1 of
    [a >= t][b >= t], so the sum is a sum of binary sparse products, one per count level."""
    Y = X if Y is None else Y
    top = int(max(X.max() if X.nnz else 0, Y.max() if Y.nnz else 0))
    out = np.zeros((X.shape[0], Y.shape[0]), dtype=np.int64)
    for t in range(1, top + 1):
        A = (X >= t).astype(np.int64)
        B = (Y >= t).astype(np.int64)
        out += (A @ B.T).toarray()
    return out


def pairwise_l1(X: sparse.csr_matrix, Y: sparse.csr_matrix | None = None) -> np.ndarray:
    """L1 distance between every pair of count rows: |a| + |b| - 2 sum min(a, b)."""
    Y = X if Y is None else Y
    sx = np.asarray(X.sum(axis=1)).ravel()
    sy = np.asarray(Y.sum(axis=1)).ravel()
    return sx[:, None] + sy[None, :] - 2 * pairwise_min_sum(X, Y)


def pairwise_euclidean(X: sparse.csr_matrix, Y: sparse.csr_matrix | None = None) -> np.ndarray:
    """Euclidean distance between count rows, from integer dot products (exact zeros)."""
    Y = X if Y is None else Y
    nx = np.asarray(X.multiply(X).sum(axis=1)).ravel()
    ny = np.asarray(Y.multiply(Y).sum(axis=1)).ravel()
    sq = nx[:, None] + ny[None, :] - 2 * (X @ Y.T).toarray()
    return np.sqrt(np.maximum(sq, 0).astype(np.float64))


def matrices(bags_a: list[Counter], bags_b: list[Counter] | None = None):
    """Count matrices of two lists of bags over one shared vocabulary."""
    if bags_b is None:
        return count_matrix(bags_a), None
    M = count_matrix(list(bags_a) + list(bags_b))
    return M[: len(bags_a)], M[len(bags_a):]


# ---------------------------------------------------------------------------
# One-hot: the activity profile (Song, Günther & van der Aalst 2009)
# ---------------------------------------------------------------------------


def activity_counts(t) -> Counter:
    """How often each activity occurs in the variant (the activity profile, sec. 3)."""
    return Counter(tree_to_sequence(t))


def song_jaccard(X: sparse.csr_matrix, Y: sparse.csr_matrix | None = None) -> np.ndarray:
    """Sec. 4.1: 1 - x.y / (x.x + y.y - x.y) for every pair of count rows; on 0/1 rows this is
    the Jaccard distance of the two sets."""
    Y = X if Y is None else Y
    nx = np.asarray(X.multiply(X).sum(axis=1)).ravel()
    ny = np.asarray(Y.multiply(Y).sum(axis=1)).ravel()
    xy = (X @ Y.T).toarray()
    return 1.0 - xy / (nx[:, None] + ny[None, :] - xy)


def onehot_distances(trees, others=None) -> np.ndarray:
    a = [activity_counts(t) for t in trees]
    b = None if others is None else [activity_counts(t) for t in others]
    X, Y = matrices(a, b)
    return song_jaccard(X, Y)


# ---------------------------------------------------------------------------
# 3-grams (Bose & van der Aalst 2009)
# ---------------------------------------------------------------------------


def kgrams(seq: list[str], k: int = 3) -> Counter:
    """Every run of k consecutive activities, counted (sec. 3.2: for abacaab, the 3-grams are
    aba, bac, aca, caa, aab).  A variant with fewer than k activities has none."""
    return Counter(tuple(seq[i:i + k]) for i in range(len(seq) - k + 1))


def trigram_distances(trees, others=None) -> np.ndarray:
    a = [kgrams(tree_to_sequence(t)) for t in trees]
    b = None if others is None else [kgrams(tree_to_sequence(t)) for t in others]
    X, Y = matrices(a, b)
    return pairwise_euclidean(X, Y)


# ---------------------------------------------------------------------------
# pq-grams (Augsten, Boehlen & Gamper 2010)
# ---------------------------------------------------------------------------


def pq_index(t, p: int = 2, q: int = 3, label=node_label, leaf=_is_leaf) -> Counter:
    """Def. 6.4: the bag of label tuples of every pq-gram of the pq-extended tree (Def. 6.1:
    p - 1 dummy ancestors above the root, q - 1 dummy children before the first and after the
    last child of every inner node, q dummy children under every leaf).  Built by the shift
    registers of the paper's algorithm: the stem holds the p labels from an anchor's ancestors
    down to the anchor, the base the q labels of a window over the anchor's children.
    *label* and *leaf* read a node (concurrency trees by default; the tests pass the paper's
    trees, whose inner nodes carry labels)."""
    out: Counter = Counter()
    stack = [(t, (DUMMY,) * (p - 1) + (label(t),))]
    while stack:
        node, stem = stack.pop()
        if leaf(node):
            out[stem + (DUMMY,) * q] += 1
            continue
        base = (DUMMY,) * q
        for c in node.children:
            base = base[1:] + (label(c),)
            out[stem + base] += 1
            stack.append((c, stem[1:] + (label(c),)))
        for _ in range(q - 1):
            base = base[1:] + (DUMMY,)
            out[stem + base] += 1
    return out


def pq_distances(trees, others=None, p: int = 2, q: int = 3) -> np.ndarray:
    """Def. 6.6, the normalised pq-gram distance:
    (|I1 + I2| - 2 |I1 & I2|) / (|I1 + I2| - |I1 & I2|), with bag union + and bag intersection
    &.  With S = |I1| + |I2| and L1 the L1 distance of the count vectors, |I1 & I2| = (S - L1)/2,
    so the distance is 2 L1 / (S + L1)."""
    a = [pq_index(sorted_tree(t), p, q) for t in trees]
    b = None if others is None else [pq_index(sorted_tree(t), p, q) for t in others]
    X, Y = matrices(a, b)
    Y = X if Y is None else Y
    L1 = pairwise_l1(X, Y)
    S = np.asarray(X.sum(axis=1)).ravel()[:, None] + np.asarray(Y.sum(axis=1)).ravel()[None, :]
    return (2.0 * L1) / (S + L1)


# ---------------------------------------------------------------------------
# Binary branches (Yang, Kalnis & Tung 2005)
# ---------------------------------------------------------------------------


def binary_branches(t, label=node_label, leaf=_is_leaf) -> Counter:
    """Def. 2-3: for every node u, the branch (u, u's left child, u's right child) in the
    normalised left-child right-sibling binary tree, i.e. (u, u's first child, u's next sibling),
    epsilon where there is none; counted.  *label* and *leaf* as in pq_index."""
    out: Counter = Counter()
    stack = [(t, None)]                         # (node, its next sibling)
    while stack:
        node, nxt = stack.pop()
        first = None if leaf(node) or not node.children else node.children[0]
        out[(label(node),
             EPSILON if first is None else label(first),
             EPSILON if nxt is None else label(nxt))] += 1
        if not leaf(node):
            kids = node.children
            for i, c in enumerate(kids):
                stack.append((c, kids[i + 1] if i + 1 < len(kids) else None))
    return out


def binary_branch_distances(trees, others=None) -> np.ndarray:
    """Def. 4: BDist, the L1 distance between binary branch vectors."""
    a = [binary_branches(sorted_tree(t)) for t in trees]
    b = None if others is None else [binary_branches(sorted_tree(t)) for t in others]
    X, Y = matrices(a, b)
    return pairwise_l1(X, Y).astype(np.float64)


# ---------------------------------------------------------------------------
# APTED, the authors' Java implementation (evaluation/java_apted/)
# ---------------------------------------------------------------------------

JAVA = Path(__file__).resolve().parent / "java_apted"


def _workers(n_jobs) -> int:
    """Threads for APTED: all cores but two by default, so the laptop stays usable."""
    import os
    return max(1, (os.cpu_count() or 2) - 2) if n_jobs in (-1, None) else max(1, n_jobs)


def _java_classes() -> Path:
    """The compiled driver, built from evaluation/java_apted/ when missing or older than a source."""
    build = JAVA / "build"
    sources = [JAVA / "AllPairs.java", *sorted((JAVA / "src").rglob("*.java"))]
    target = build / "AllPairs.class"
    if not target.exists() or target.stat().st_mtime < max(p.stat().st_mtime for p in sources):
        subprocess.run(["javac", "-nowarn", "-d", str(build), "-sourcepath", str(JAVA / "src"),
                        str(JAVA / "AllPairs.java")], check=True, capture_output=True)
    return build


def _bracket(t, ids: dict) -> str:
    """The tree in bracket notation, every label replaced by an id (n0, n1, ...): unit costs only
    compare labels for equality, and ids need no escaping."""
    lab = ids.setdefault(node_label(t), f"n{len(ids)}")
    if _is_leaf(t):
        return "{" + lab + "}"
    return "{" + lab + "".join(_bracket(c, ids) for c in t.children) + "}"


def _java_apted(trees, pairs: np.ndarray | None = None, n_jobs: int = -1) -> np.ndarray:
    """Unit-cost APTED on the sorted trees: every pair i < j in numpy.triu_indices order, or the
    rows of *pairs* (m, 2)."""
    ids: dict = {}
    lines = [_bracket(sorted_tree(t), ids) for t in trees]
    with tempfile.TemporaryDirectory() as tmp:
        tree_file, out = Path(tmp) / "trees.txt", Path(tmp) / "out.bin"
        tree_file.write_text("\n".join(lines) + "\n")
        cmd = ["java", "-cp", str(_java_classes()), "AllPairs", str(tree_file), str(out), str(_workers(n_jobs))]
        if pairs is not None:
            pair_file = Path(tmp) / "pairs.bin"
            np.ascontiguousarray(pairs, dtype=">i4").tofile(pair_file)
            cmd.append(str(pair_file))
        subprocess.run(cmd, check=True)
        return np.fromfile(out, dtype=">i4").astype(np.float64)


def apted_distances(trees, n_jobs: int = -1) -> np.ndarray:
    """Tree edit distance (Pawlik & Augsten 2015, 2016) with unit costs (every insertion, deletion
    and relabelling costs 1), on the sorted trees, for every pair."""
    n = len(trees)
    D = np.zeros((n, n))
    if n > 1:
        D[np.triu_indices(n, 1)] = _java_apted(trees, n_jobs=n_jobs)
    return D + D.T


def apted_pair_distances(trees, ia, ib, n_jobs: int = -1) -> np.ndarray:
    """Unit-cost tree edit distance for every pair (trees[ia[k]], trees[ib[k]]), on the sorted
    trees; only the trees the pairs use are sent."""
    ia, ib = np.asarray(ia, dtype=int), np.asarray(ib, dtype=int)
    if not len(ia):
        return np.empty(0)
    used, inv = np.unique(np.concatenate([ia, ib]), return_inverse=True)
    pairs = np.stack([inv[:len(ia)], inv[len(ia):]], axis=1)
    return _java_apted([trees[i] for i in used], pairs, n_jobs)


# ---------------------------------------------------------------------------
# Distances for given pairs (the probes): each tree's representation once, then per pair
# ---------------------------------------------------------------------------


def _rows_l1(X, ia, ib) -> np.ndarray:
    return np.asarray(abs(X[ia] - X[ib]).sum(axis=1)).ravel()


def pair_distances(method: str, trees: list, ia, ib, p: int = 2, q: int = 3) -> np.ndarray:
    """*method*'s distance for every pair (trees[ia[k]], trees[ib[k]]), the same numbers as its
    all-pairs function gives (tests/test_baselines.py checks this).  *p* and *q* are read by
    pq-grams only."""
    ia, ib = np.asarray(ia), np.asarray(ib)
    if method == "length":
        n = np.array([len(tree_to_sequence(t)) for t in trees], dtype=np.float64)
        return np.abs(n[ia] - n[ib])
    if method == "onehot":
        X = count_matrix([activity_counts(t) for t in trees])
        nn = np.asarray(X.multiply(X).sum(axis=1)).ravel()
        xy = np.asarray(X[ia].multiply(X[ib]).sum(axis=1)).ravel()
        return 1.0 - xy / (nn[ia] + nn[ib] - xy)
    if method == "trigram":
        X = count_matrix([kgrams(tree_to_sequence(t)) for t in trees])
        return np.sqrt(np.asarray(X[ia].multiply(X[ia]).sum(axis=1)).ravel()
                       + np.asarray(X[ib].multiply(X[ib]).sum(axis=1)).ravel()
                       - 2 * np.asarray(X[ia].multiply(X[ib]).sum(axis=1)).ravel()).astype(np.float64)
    if method == "pqgram":
        X = count_matrix([pq_index(sorted_tree(t), p, q) for t in trees])
        S = np.asarray(X.sum(axis=1)).ravel()
        L1 = _rows_l1(X, ia, ib)
        return 2.0 * L1 / (S[ia] + S[ib] + L1)
    if method == "binary_branch":
        X = count_matrix([binary_branches(sorted_tree(t)) for t in trees])
        return _rows_l1(X, ia, ib).astype(np.float64)
    if method == "apted":
        return apted_pair_distances(trees, ia, ib)
    raise KeyError(f"no pair distance for method {method!r}")


__all__ = ["DUMMY", "EPSILON", "activity_counts", "onehot_distances", "song_jaccard", "apted_distances", "binary_branch_distances", "binary_branches",
           "kgrams", "pairwise_euclidean", "pairwise_l1", "pq_distances", "pq_index", "sorted_tree",
           "trigram_distances"]
