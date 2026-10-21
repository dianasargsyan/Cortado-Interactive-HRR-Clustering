"""
The probes of the synthetic dataset (evaluation/dataset.py, evaluation/probe_sets.py), counted.  On every
base (the universe at 2, 3, 4; every shape at 6 and 9 and the rule's shapes at 12 to 65, each with
its repeat versions; the rule's shapes at 6 and 9 for the check):

  paths       an edit grown step by step at one place, everything else held fixed
              (evaluation.probes.paths_on); eight edits
  one-step    every edit at its smallest size at every place it can go (evaluation.probes.single_edits)

From 12 on both are thinned as the scripts that score them thin them (evaluation.probe_sets.thinned).
  loops       the loop paths (evaluation/dataset.loop_paths), on the bases without repeats

Every path is checked as it is built (tests/test_probes.py).  Nothing here scores a method; the
scripts that score probes rebuild them from evaluation/probe_sets.py.

Output in cache/variants/: paths_counts.csv, per layer (length and repeat
version) and edit: bases, paths, path steps, one-step edits, and the loop-path steps per length;
rule_shapes.txt, every shape the rule chooses at 6, 9 and 12 to 65, each activity written as •
and a run of k single steps as •×k.

    python evaluation/experiments/30_paths.py
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import CACHE, require_cortado_env  # noqa: E402

require_cortado_env()

import pandas as pd  # noqa: E402

from evaluation import dataset, probe_sets, probes  # noqa: E402
from rotation_hrr.variant_enumeration import OP_SYM, is_leaf  # noqa: E402

OUT = CACHE / "paths_counts.csv"
SHAPES = CACHE / "rule_shapes.txt"
SMALLEST = {"move": 1, "seq_to_par": 2, "nesting": 2, "alongside": 2}


def layer_rows(layer, bases, thin=False):
    rows, per_edit = [], {}
    for _, t in bases:
        for (edit, _, _), steps in probes.paths_on(t, thin).items():
            c = per_edit.setdefault(edit, {"paths": 0, "steps": 0, "one_step": 0})
            c["paths"] += 1
            c["steps"] += len(steps)
        for e in probes.single_edits(t, smallest=True, thin=thin):
            if e.size == SMALLEST.get(e.edit, e.size):
                per_edit.setdefault(e.edit, {"paths": 0, "steps": 0, "one_step": 0})["one_step"] += 1
    for edit, c in sorted(per_edit.items()):
        rows.append({"layer": layer, "bases": len(bases), "edit": edit, **c})
    return rows


def compact(t) -> str:
    """A shape with every activity as • and a run of k single steps as •×k."""
    if is_leaf(t):
        return "•"
    parts, run = [], 0
    for c in t.children + [None]:
        if c is not None and is_leaf(c):
            run += 1
            continue
        if run:
            parts.append("•" if run == 1 else f"•×{run}")
            run = 0
        if c is not None:
            parts.append(compact(c))
    return f"{OP_SYM[t.op]}({', '.join(parts)})"


def write_shapes() -> None:
    lines = []
    for n in dataset.CHECK_LENGTHS + dataset.RULE:
        shapes = dataset.rule_shapes(n)
        lines.append(f"Length {n}: {len(shapes)} shapes" + (" (the check)" if n in dataset.CHECK_LENGTHS else ""))
        lines += [f"  {fam:32s} {compact(t)}" for fam, t in shapes] + [""]
    SHAPES.write_text("\n".join(lines))


def main() -> None:
    t0 = time.time()
    write_shapes()
    rows = []
    for n in dataset.UNIVERSE:
        rows += layer_rows(f"universe {n}", probe_sets.universe(n))
        print(f"universe {n} ({time.time() - t0:.0f}s)", flush=True)
    for n in probe_sets.LENGTHS:
        by_version: dict = {}
        for g, t in probe_sets.with_groups(n):
            by_version.setdefault(g.rsplit(", ", 1)[1], []).append((g, t))
        for v, bases in by_version.items():
            rows += layer_rows(f"length {n}, {v}", bases, probe_sets.thinned(n))
        loops = sum(len(st) for _, t in dataset.base_shapes(n) for st in dataset.loop_paths(t).values())
        rows.append({"layer": f"length {n}", "bases": len(dataset.base_shapes(n)), "edit": "loops",
                     "paths": "", "steps": loops, "one_step": ""})
        print(f"length {n} ({time.time() - t0:.0f}s)", flush=True)
    for n in dataset.CHECK_LENGTHS:
        rows += layer_rows(f"check {n}", probe_sets.check(n))
    P = pd.DataFrame(rows)
    P.to_csv(OUT, index=False)
    tot = P[P["edit"] != "loops"].groupby("layer")[["paths", "steps", "one_step"]].sum()
    print(f"\nwrote {OUT.name} ({time.time() - t0:.0f}s)\n{tot.to_string()}")


if __name__ == "__main__":
    main()
