"""
Every representation the evaluation compares, behind one interface.

A method is a function ``fn(corpus, seed, **knobs) -> array`` registered with ``@method``.  It
returns either vectors, shape (n, width), with the distance its paper uses, or a distance matrix,
shape (n, n), for methods without vectors.  ``represent`` does the rest for every method:

  knobs   a method accepts only the knobs it registers, with their defaults
  seeds   a method without randomness runs once (seed None)
  cache   the array is saved under config.REPR_CACHE, keyed by method, corpus, seed, knob
          settings and the source files the method depends on
  checks  every distance matrix is square, symmetric, finite and non-negative with a zero
          diagonal before anything uses it
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field
from functools import cached_property
from typing import Callable

import numpy as np

from evaluation import config
from evaluation.batch_hrr import Batch
from evaluation.corpus import Corpus
from rotation_hrr.encoder import RotationHRREncoder
from rotation_hrr.tree_utils import tree_to_positioned_sequence, tree_to_sequence


def angular(X: np.ndarray) -> np.ndarray:
    """arccos(cosine) / pi, in [0, 1]; a metric, unlike 1 - cosine."""
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    Xn = X / np.where(norms < 1e-12, 1.0, norms)
    S = Xn @ Xn.T
    D = np.arccos(np.clip((S + S.T) / 2, -1.0, 1.0)) / np.pi
    np.fill_diagonal(D, 0.0)
    return D


def absdiff(X: np.ndarray) -> np.ndarray:
    """|x_i - x_j| for one-column vectors."""
    return np.abs(X[:, 0][:, None] - X[:, 0][None, :])


@dataclass(frozen=True)
class Method:
    name: str
    fn: Callable
    returns: str                        # "vectors" | "distances"
    distance: Callable | None           # vectors -> distances; None if returns distances
    stochastic: bool
    knobs: dict                         # accepted knobs and their defaults
    depends_on: tuple[str, ...]         # source files (from the repo root) the output depends on
    cite: str


METHODS: dict[str, Method] = {}


def method(name: str, *, returns: str = "vectors", distance: Callable | None = None,
           stochastic: bool = False, knobs: dict | None = None,
           depends_on: tuple[str, ...] = (), cite: str = ""):
    """Register ``fn(corpus, seed, **knobs)`` under *name*."""
    if returns not in ("vectors", "distances"):
        raise ValueError(f"returns must be 'vectors' or 'distances', got {returns!r}")
    if (returns == "vectors") != (distance is not None):
        raise ValueError("a method returning vectors names its distance; one returning "
                         "distances does not")

    def register(fn: Callable) -> Callable:
        if name in METHODS:
            raise ValueError(f"method {name!r} is already registered")
        METHODS[name] = Method(name, fn, returns, distance, stochastic,
                               dict(knobs or {}), tuple(depends_on), cite)
        return fn
    return register


@dataclass(eq=False)
class Representation:
    method: str
    corpus: str
    seed: int | None                    # None for methods without randomness
    settings: dict                      # every knob, defaults filled in
    vectors: np.ndarray | None          # None for distance-only methods
    _distances: np.ndarray | None = field(default=None, repr=False)
    _distance_fn: Callable | None = field(default=None, repr=False)

    @cached_property
    def distances(self) -> np.ndarray:
        D = self._distances if self._distances is not None else self._distance_fn(self.vectors)
        check_distances(D, self.method)
        return D


def check_distances(D: np.ndarray, name: str = "") -> None:
    """Fail loudly on a matrix no metric should be given."""
    where = f" ({name})" if name else ""
    if D.ndim != 2 or D.shape[0] != D.shape[1]:
        raise ValueError(f"distance matrix is not square{where}: {D.shape}")
    if not np.all(np.isfinite(D)):
        raise ValueError(f"distance matrix has non-finite values{where}")
    if not np.allclose(D, D.T, atol=1e-12):
        raise ValueError(f"distance matrix is not symmetric{where}")
    if np.any(np.diag(D) != 0):
        raise ValueError(f"distance matrix has a nonzero diagonal{where}")
    if np.any(D < 0):
        raise ValueError(f"distance matrix has negative values{where}")


def check_range(name: str, settings: dict) -> None:
    """Refuse an HRR setting outside config.HRR_RANGES."""
    if name != "hrr":
        return
    for knob, (lo, hi) in config.HRR_RANGES.items():
        x = settings.get(knob)
        if x is not None and not lo - 1e-12 <= float(x) <= hi + 1e-12:
            raise ValueError(f"hrr: {knob} = {x} is outside the measured range [{lo:g}, {hi:g}]; "
                             "pass outside_range=True only in a scan that measures the range")


def represent(name: str, corpus: Corpus, seed: int | None = config.DEFAULT_SEED,
              use_cache: bool = True, outside_range: bool = False, **knobs) -> Representation:
    """Method *name* applied to *corpus*: vectors (if any) and distances.  HRR settings must lie
    in config.HRR_RANGES unless *outside_range* is True."""
    if name not in METHODS:
        raise KeyError(f"unknown method {name!r}; registered: {sorted(METHODS)}")
    m = METHODS[name]
    unknown = set(knobs) - set(m.knobs)
    if unknown:
        raise ValueError(f"{name} has no knob(s) {sorted(unknown)}; it accepts {sorted(m.knobs)}")
    settings = {**m.knobs, **knobs}
    if not outside_range:
        check_range(name, settings)
    seed = seed if m.stochastic else None

    path = config.REPR_CACHE / f"{name}__{corpus.name}__{_cache_key(m, corpus, seed, settings)}.npz"
    if use_cache and path.exists():
        arr = np.load(path)["array"]
    else:
        arr = np.asarray(m.fn(corpus, seed, **settings), dtype=np.float64)
        if len(arr) != corpus.n:
            raise ValueError(f"{name} returned {len(arr)} rows for {corpus.n} variants")
        if use_cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(path, array=arr)

    if m.returns == "vectors":
        return Representation(name, corpus.name, seed, settings, vectors=arr,
                              _distance_fn=m.distance)
    return Representation(name, corpus.name, seed, settings, vectors=None, _distances=arr)


def _cache_key(m: Method, corpus: Corpus, seed: int | None, settings: dict) -> str:
    h = hashlib.blake2b(digest_size=8)
    h.update(json.dumps([m.name, corpus.fingerprint, seed, settings], sort_keys=True).encode())
    h.update(inspect.getsource(m.fn).encode())
    for rel in m.depends_on:
        h.update((config.ROOT / rel).read_bytes())
    return h.hexdigest()


def hrr_ranges(trees) -> tuple[int, int]:
    """The encoder's frequency ranges for a set of variants: (n_max, n_max_depth) =
    FREQ_RANGE_FACTOR x the longest variant and x the deepest nesting, each at least the factor.
    Only the variants' length and depth are used, never their activities."""
    f = config.FREQ_RANGE_FACTOR
    longest = max(len(tree_to_sequence(t)) for t in trees)
    deepest = max(max(dp for _, _, dp in tree_to_positioned_sequence(t)[0]) for t in trees)
    return max(f, f * longest), max(f, f * deepest)


_TREES = ("rotation_hrr/tree_utils.py",)


@method("hrr", distance=angular, stochastic=True, knobs=config.HRR_DEFAULTS,
        depends_on=("rotation_hrr/encoder.py", "rotation_hrr/tree_utils.py", "evaluation/batch_hrr.py",
                    "evaluation/methods.py", "evaluation/config.py"),
        cite="this thesis")
def hrr(corpus, seed, *, d, alpha, beta):
    """Rotation-HRR, one vector per variant, frequency ranges from the corpus (a sample keeps
    its log's, evaluation.synthetic.corpus)."""
    n_max, n_max_depth = corpus.info.get("ranges") or hrr_ranges(corpus.trees)
    enc = RotationHRREncoder(d=d, n_max=n_max, seed=seed, n_max_depth=n_max_depth)
    return Batch(corpus.trees).vectors(enc, alpha, beta)


def song_jaccard(X: np.ndarray) -> np.ndarray:
    """Song et al.'s Jaccard distance on count vectors (evaluation.baselines.song_jaccard)."""
    from scipy import sparse
    from evaluation.baselines import song_jaccard as on_counts
    D = on_counts(sparse.csr_matrix(X.astype(np.int64)))
    np.fill_diagonal(D, 0.0)
    return D


@method("onehot", distance=song_jaccard, depends_on=_TREES + ("evaluation/baselines.py",),
        cite="Song, Günther & van der Aalst 2009 (activity profile: counts; their Jaccard distance)")
def onehot(corpus, seed):
    """The activity profile: x[a] = how often activity a occurs in the variant, the sum of the
    one-hot vectors of its activities."""
    from evaluation.baselines import activity_counts
    bags = [activity_counts(t) for t in corpus.trees]
    vocab = {a: i for i, a in enumerate(sorted({a for b in bags for a in b}))}
    X = np.zeros((len(bags), len(vocab)))
    for row, b in enumerate(bags):
        for a, n in b.items():
            X[row, vocab[a]] = n
    return X


# The other methods, each as its paper defines it (evaluation/baselines.py): the sequence baselines of
# trace clustering (one-hot, 3-grams) and ordered tree edit distance with its published fast
# approximations (APTED, pq-grams, binary branches).  The sequence methods read a variant left to
# right with every block's activities sorted; the tree methods get the tree with every block sorted.
_BASE = ("evaluation/baselines.py", "rotation_hrr/tree_utils.py", "rotation_hrr/tree_rewrites.py")


@method("trigram", returns="distances", depends_on=_BASE,
        cite="Bose & van der Aalst 2009 (3-grams, Euclidean)")
def trigram(corpus, seed):
    from evaluation.baselines import trigram_distances
    return trigram_distances(corpus.trees)


@method("apted", returns="distances",
        depends_on=_BASE + ("evaluation/java_apted/AllPairs.java", "evaluation/java_apted/src/at/unisalzburg/dbresearch/apted/distance/APTED.java"),
        cite="Pawlik & Augsten 2015, 2016 (tree edit distance, unit costs)")
def apted(corpus, seed):
    from evaluation.baselines import apted_distances
    return apted_distances(corpus.trees)


@method("pqgram", returns="distances", depends_on=_BASE, knobs={"p": 2, "q": 3},
        cite="Augsten, Böhlen & Gamper 2010 (normalised pq-gram distance, p = 2, q = 3; "
             "config.PQ_SWEEP for the paper's other settings)")
def pqgram(corpus, seed, *, p, q):
    from evaluation.baselines import pq_distances
    return pq_distances(corpus.trees, p=p, q=q)


@method("binary_branch", returns="distances", depends_on=_BASE,
        cite="Yang, Kalnis & Tung 2005 (binary branch distance)")
def binary_branch(corpus, seed):
    from evaluation.baselines import binary_branch_distances
    return binary_branch_distances(corpus.trees)


@method("length", distance=absdiff, depends_on=_TREES,
        cite="Conneau et al. 2018 (a length-only probe as a control)")
def length(corpus, seed):
    """The number of activities; the distance is the difference in that number.  A method that
    tracks only length passes the missing and repetition tests; this control shows how much of
    a pass that explains."""
    return np.array([[len(tree_to_sequence(t))] for t in corpus.trees], dtype=np.float64)
