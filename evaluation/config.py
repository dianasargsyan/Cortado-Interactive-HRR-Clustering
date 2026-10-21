"""
The evaluation's fixed settings: where files live, the logs, HRR's settings and the seeds.

Every stochastic number is reported over ``SEEDS``; a single run uses ``DEFAULT_SEED``.  Each
random component draws from its own stream, derived from (seed, component name) by ``rng_for``,
so changing how many pairs one step samples never changes which probes another draws.  The
encoder's activity vectors come from the encoder's own seed.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent

VARIANT_CACHE = ROOT / "cache" / "variants"   # variants_<log>.pkl
RESULTS = Path(os.environ.get("RESULTS_TABLE", ROOT / "results" / "results.csv"))  # the one results table
REPR_CACHE = ROOT / "cache" / "representations"        # regenerable

LOGS: tuple[str, ...] = ("domestic", "permit", "sepsis", "bpic15_1", "bpi2012", "bpi2017")

# The knob sweeps (response, admissibility) compare a knob step with a reseed on the same pairs, so
# on the two largest logs they run on a sample of this many variants (evaluation.synthetic.corpus).
SWEEP_SAMPLE: dict[str, int] = {"bpi2012": 1000, "bpi2017": 1000}

# Every corpus d has to serve: the logs, the universe and the synthetic lengths.
CORPORA: tuple[str, ...] = LOGS + ("universe_4", "length_6", "length_9", "length_12", "length_15",
                                   "length_20", "length_30", "length_45", "length_65")

K: tuple[int, ...] = (5, 10, 20)

# One d for every corpus and the tool: the smallest d at which, on every corpus and every setting
# of GRID, two seeds rank all pairs alike, keep each variant's 10 nearest and agree with
# d = 32768 (evaluation/d_rule.py).  BPIC15_1 is the corpus that needs 8192.
D: int = 8192

# HRR's knobs, from 0 (off) to 1 (one place, or one level deeper, is one step of the slowest
# rotation), and the tool's starting point.
HRR_DEFAULTS: dict = {"d": D, "alpha": 1.0, "beta": 1.0}
# represent("hrr") refuses a setting outside HRR_RANGES unless the caller passes
# outside_range=True, as the scans that measure the ranges do.
HRR_RANGES: dict[str, tuple[float, float]] = {"alpha": (0.0, 1.0), "beta": (0.0, 1.0)}
GRID: dict[str, tuple] = {"alpha": (0.0, 0.5, 1.0), "beta": (0.0, 0.5, 1.0), "d": (D,)}

# Frequency ranges from the corpus: n_max = FREQ_RANGE_FACTOR x the longest variant, the depth
# range FREQ_RANGE_FACTOR x the deepest nesting (each at least the factor).  4 is the smallest
# round factor for which, at alpha = beta = 1, the similarity of a moved activity falls with the
# size of the move and never turns negative, in every log.
FREQ_RANGE_FACTOR: int = 4

# Each knob off or on, for the steps that compare HRR's settings with the other methods.
PHASE2_SETTINGS: tuple[tuple[float, float], ...] = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0))

# pq-grams' own knobs, (p, q) as its paper varies them (Augsten, Boehlen & Gamper 2010, Sect.
# 9.2): q from 1 to 4 at p = 2, p from 1 to 4 at q = 3.  The comparison's pq-grams stays at
# (2, 3); these settings go in rows of their own (capability_pq_sweep, collisions_pq_sweep).
PQ_SWEEP: tuple[tuple[int, int], ...] = ((2, 1), (2, 2), (2, 3), (2, 4), (1, 3), (3, 3), (4, 3))

# A method without randomness tells two variants apart if their distance exceeds this (above 0,
# against rounding); HRR must exceed its noise band on every seed.
TOLD_APART_TOL: float = 1e-9

SEEDS: tuple[int, ...] = tuple(range(42, 47))
DEFAULT_SEED: int = SEEDS[0]

COMPONENTS = ("pairs", "probe")


def rng_for(seed: int, component: str) -> np.random.Generator:
    """An independent generator for one random component under one seed: "pairs" for sampled
    pairs and subsets of variants, "probe" for drawn probe bases."""
    if component not in COMPONENTS:
        raise ValueError(f"unknown component {component!r}; expected one of {COMPONENTS}")
    h = hashlib.blake2b(f"{seed}\x00{component}".encode(), digest_size=8).digest()
    return np.random.default_rng(int.from_bytes(h, "big"))
