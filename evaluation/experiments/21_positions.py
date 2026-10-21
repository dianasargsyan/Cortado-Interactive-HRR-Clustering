"""
Does every activity sit at its average place over every order the variant allows?

Every shape with 1 to N_MAX activities (evaluation/probes.shapes: every tree the grammar allows, one
naming each; positions do not depend on names), checked against evaluation/orders.py, which works only
from which activity must come before which:

  max_error          largest |position - exact average place| over the shapes
  not_exact          shapes with an activity off by more than 1e-12
  order              pairs (a before b in every order) placed with a not before b
  bounds             activities placed before their earliest or after their latest place
  reversal_error     largest |position read backwards - (n - 1 - position)|
  forms / forms_differ   ways of writing the shapes (every order of every block's children),
                     and how many of them get other positions
  depth_mismatch     shapes whose depths differ from the operators above each activity

Positions use no random numbers and no knob, so each check runs once.  Rows: method hrr, log
shapes_<n>, knob defaults.

    python evaluation/experiments/21_positions.py
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

from evaluation import probes, results  # noqa: E402
from evaluation.orders import backwards, leaf_depths, violations, written_forms  # noqa: E402
from rotation_hrr.tree_utils import tree_to_positioned_sequence  # noqa: E402

N_MAX = 9
TOL = 1e-12


def check(n: int) -> dict:
    out = dict(shapes=0, max_error=0.0, not_exact=0, order=0, bounds=0, reversal_error=0.0,
               forms=0, forms_differ=0, depth_mismatch=0)
    for t in probes.shapes(n):
        items = tree_to_positioned_sequence(t)[0]
        v = violations(t, items)
        out["shapes"] += 1
        out["max_error"] = max(out["max_error"], v["max_error"])
        out["not_exact"] += v["max_error"] > TOL
        out["order"] += v["order"]
        out["bounds"] += v["bounds"]
        fwd = {a: p for a, p, _ in items}
        rev = {a: p for a, p, _ in tree_to_positioned_sequence(backwards(t))[0]}
        out["reversal_error"] = max(out["reversal_error"],
                                    max(abs(rev[a] - (n - 1 - fwd[a])) for a in fwd))
        ref = {a: (p, d) for a, p, d in items}
        for form in written_forms(t):
            out["forms"] += 1
            out["forms_differ"] += {a: (p, d) for a, p, d
                                    in tree_to_positioned_sequence(form)[0]} != ref
        out["depth_mismatch"] += [d for *_, d in items] != leaf_depths(t)
    return out


def main() -> None:
    commit = results.commit()
    print(f"Every shape with 1-{N_MAX} activities, commit {commit}\n")
    cols = ("shapes", "max_error", "not_exact", "order", "bounds", "reversal_error",
            "forms", "forms_differ", "depth_mismatch")
    print(f"{'n':>2} " + " ".join(f"{c:>15}" for c in cols) + f" {'time':>6}")
    rows = []
    for n in range(1, N_MAX + 1):
        t0 = time.time()
        r = check(n)
        print(f"{n:>2} " + " ".join(f"{r[c]:>15.2e}" if isinstance(r[c], float) else f"{r[c]:>15,}"
                                   for c in cols) + f" {time.time() - t0:>5.0f}s")
        rows += [{"method": "hrr", "log": f"shapes_{n}", "knob": "defaults", "metric": c,
                  "result": r[c], "commit": commit} for c in cols]
    path = results.write(rows)
    print(f"\nWrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main()
