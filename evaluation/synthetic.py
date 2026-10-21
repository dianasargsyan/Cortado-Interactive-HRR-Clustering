"""
The synthetic corpora, each compared all-pairs like a log:

  universe_4     every variant with 2, 3 or 4 activities (evaluation/universe.py)
  length_<n>     at n = 6 and 12 to 65 every variant of the dataset (each shape and its repeat
                 versions); at n = 9 the sample with the same number of shapes from every depth
                 (evaluation/dataset.sample_9)

HRR takes each corpus's frequency ranges from it.
"""

from __future__ import annotations

from functools import lru_cache

from evaluation import config, dataset, universe
from evaluation.corpus import Corpus, from_trees, load_log


def names() -> list[str]:
    """Every synthetic corpus: the universe, then one per length."""
    return ["universe_4"] + [f"length_{n}" for n in dataset.LENGTHS]


@lru_cache(maxsize=1)
def _universe_4() -> tuple:
    return tuple(t for n in dataset.UNIVERSE for t in universe.variants(n))


def load(name: str) -> Corpus:
    """A synthetic corpus by name: universe_4, a length_<n>, or one of the five-activity universe
    sets (universe_5_<set>, complete enumerations over one activity set)."""
    if name == "universe_4":
        return from_trees(name, list(_universe_4()))
    if name.startswith("universe_5_") and name in universe.corpora():
        return from_trees(name, list(universe.corpora()[name]))
    if name.startswith("length_"):
        return from_trees(name, dataset.corpus(int(name.split("_", 1)[1])))
    raise KeyError(f"not a synthetic corpus: {name}")


def corpus(name: str, sampled: bool = False) -> Corpus:
    """A log (config.LOGS) or a synthetic corpus, by name.  With *sampled*, a log in
    config.SWEEP_SAMPLE is cut to that many variants, drawn once with the shared seed; HRR keeps
    the whole log's frequency ranges."""
    if name not in config.LOGS:
        return load(name)
    c = load_log(name)
    if not sampled or c.n <= config.SWEEP_SAMPLE.get(name, c.n):
        return c
    from evaluation.methods import hrr_ranges
    pick = sorted(config.rng_for(config.DEFAULT_SEED, "pairs").choice(c.n, config.SWEEP_SAMPLE[name],
                                                                       replace=False))
    return Corpus(name=name, trees=[c.trees[i] for i in pick], counts=c.counts[pick], kind="log",
                  note=f"{len(pick)} of {c.n} variants", info={"ranges": hrr_ranges(c.trees)})


def expand(args: list[str]) -> list[str]:
    """Command-line corpus names: "synthetic" stands for every synthetic corpus, "universe" and
    "lengths" for those parts of it, "logs" for the six logs; anything else is a name."""
    groups = {"synthetic": names(), "logs": list(config.LOGS),
              "universe": ["universe_4"],
              "lengths": [n for n in names() if n.startswith("length_")]}
    out: list[str] = []
    for a in args:
        out += groups.get(a, [a])
    return out
