"""
A corpus: variants with a case count each, from a cached event log or built by hand.  Every
method takes a Corpus, so a constructed set runs through the pipeline exactly like a log.

A variant has two identities.  ``repr(tree)`` is the tree as given, the method's input.  The
canonical form, ``repr(sort_parallel(tree))``, is equal for the same variant written two ways
(∧(A, B) and ∧(B, A)): such pairs are invariance cases, never collisions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import cached_property

import numpy as np

from evaluation import config
from evaluation._corpus import filter_note, load_corpus
from rotation_hrr.tree_utils import tree_to_sequence
from rotation_hrr.tree_rewrites import sort_parallel


@dataclass(eq=False)
class Corpus:
    name: str                 # log key ("sepsis") or a name for a constructed set
    trees: list               # Cortado ConcurrencyTrees, one per variant
    counts: np.ndarray        # cases per variant (1 each for constructed sets)
    kind: str                 # "log" | "constructed"
    note: str = ""            # what the Fallthrough filter removed (logs only)
    info: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.trees)

    @cached_property
    def max_leaves(self) -> int:
        """Activities in the longest variant."""
        return max(len(tree_to_sequence(t)) for t in self.trees)

    @cached_property
    def canonical_ids(self) -> np.ndarray:
        """One integer per variant, equal for equal canonical forms."""
        index: dict[str, int] = {}
        return np.array([index.setdefault(repr(sort_parallel(t)), len(index)) for t in self.trees],
                        dtype=np.int64)

    @cached_property
    def fingerprint(self) -> str:
        """Changes whenever the trees, their order or their counts change."""
        h = hashlib.blake2b(digest_size=8)
        for t in self.trees:
            h.update(repr(t).encode())
            h.update(b"\x00")
        h.update(np.asarray(self.counts, dtype=np.float64).tobytes())
        return h.hexdigest()


def load_log(key: str) -> Corpus:
    """One log from the variant cache, without the variants that contain a Fallthrough."""
    blob = load_corpus(config.VARIANT_CACHE, key)
    if blob is None:
        raise FileNotFoundError(f"no variant cache for {key!r} in {config.VARIANT_CACHE}")
    return Corpus(name=key, trees=blob["trees"], counts=blob["counts"], kind="log",
                  note=filter_note(blob), info=blob)


def from_trees(name: str, trees: list, counts=None) -> Corpus:
    """A constructed corpus, one case per tree by default."""
    if not trees:
        raise ValueError("a corpus needs at least one tree")
    counts = np.ones(len(trees)) if counts is None else np.asarray(counts, dtype=np.float64)
    if len(counts) != len(trees):
        raise ValueError(f"{len(trees)} trees but {len(counts)} counts")
    return Corpus(name=name, trees=list(trees), counts=counts, kind="constructed")
