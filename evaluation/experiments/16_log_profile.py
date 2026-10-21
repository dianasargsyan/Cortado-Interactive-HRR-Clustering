"""
One row per candidate log: every property that decides whether it belongs in the evaluation.

  raw log     read from the XES by the streaming reader in _xes.py and cached in
              logfacts_<key>.json: cases, events, activities, which lifecycle transitions are
              recorded, how many events share their timestamp with another event of the same
              case (where concurrency comes from when only completions are recorded), how many
              timestamps sit at midnight (day-level granularity), time span, case attributes
  variants    read from the variant cache (03_cache_variants.py), after the Fallthrough filter
              in _corpus.py: how many variants and how concentrated the cases are, variant length
              and depth, how much concurrency, nesting, loops and repetition the variants contain,
              how many orderings each admits, how many variants share an activity multiset with
              another, and the size of an all-pairs comparison

No encoder is involved: these are properties of the logs alone.

    python evaluation/experiments/16_log_profile.py            # every log with a variant cache
    python evaluation/experiments/16_log_profile.py sepsis     # one log
"""

from __future__ import annotations

import csv
import json
import math
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import CACHE, ROOT, require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
from cortado_core.subprocess_discovery.concurrency_trees.cTrees import (  # noqa: E402
    cTreeOperator,
)
from cortado_core.utils.sequentializations import (  # noqa: E402
    get_number_of_sequentializations,
)

from evaluation._corpus import LOG_NAMES, LOG_SOURCES, filter_note, load_corpus  # noqa: E402

PAR, SEQ, LOOP = cTreeOperator.Concurrent, cTreeOperator.Sequential, cTreeOperator.Loop
OUT_CSV = CACHE / "log_profile.csv"

# File for every log key; the same table as 03_cache_variants.py.
DATA = ROOT / "data"
XES = {
    "domestic": "DomesticDeclarations.xes",
    "prepaid": "PrepaidTravelCost.xes",
    "roadtraffic": "Road_Traffic_Fine_Management_Process.xes",
    "sepsis": "Sepsis Cases - Event Log.xes",
    "hospital": "Hospital Billing - Event Log.xes",
    "permit": "PermitLog.xes",
    "bpic15_1": "BPIC15_1.xes",
    "bpi2011": "Hospital_log.xes",
    "bpi2012": "BPI_Challenge_2012.xes",
    "bpi2017": "BPI Challenge 2017.xes",
    "bpi2018": "BPI Challenge 2018.xes",
}


# --- raw-log facts ---------------------------------------------------------

def log_facts(key: str) -> dict:
    """Raw-log facts, from the cache or by streaming the XES once."""
    path = CACHE / f"logfacts_{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    from evaluation._xes import read_xes_light

    print(f"  streaming {XES[key]} for raw-log facts ...", flush=True)
    _, facts = read_xes_light(DATA / XES[key])
    path.write_text(json.dumps(facts, indent=2, default=str))
    return facts


# --- tree walks --------------------------------------------------------------

def leaves(t) -> list[str]:
    if t.label is not None:
        return [t.label]
    return [a for c in t.children for a in leaves(c)]


def depth(t) -> int:
    """Operator nodes on the longest root-to-leaf path (a flat SEQ is 1)."""
    if t.label is not None:
        return 0
    return 1 + max((depth(c) for c in t.children), default=0)


def par_widths(t) -> list[int]:
    """Number of children of every PAR node."""
    if t.label is not None:
        return []
    own = [len(t.children)] if t.op == PAR else []
    return own + [w for c in t.children for w in par_widths(c)]


def nested_par(t, under_par: bool = False) -> bool:
    """A PAR somewhere below another PAR (through at least one SEQ)."""
    if t.label is not None:
        return False
    if t.op == PAR and under_par:
        return True
    return any(nested_par(c, under_par or t.op == PAR) for c in t.children)


def has_op(t, op) -> bool:
    if t.label is not None:
        return False
    return t.op == op or any(has_op(c, op) for c in t.children)


# --- one log -----------------------------------------------------------------

def profile(key: str) -> dict | None:
    corpus = load_corpus(CACHE, key)
    if corpus is None:
        print(f"[{key}] no variant cache -- run 03_cache_variants.py first")
        return None
    print(f"[{key}] " + filter_note(corpus), flush=True)
    facts = log_facts(key)

    trees = corpus["trees"]
    counts = np.asarray(corpus["counts"], dtype=np.float64)
    w = counts / counts.sum()
    n = len(trees)

    lens = np.array([len(leaves(t)) for t in trees])
    deps = np.array([depth(t) for t in trees])
    widths = [par_widths(t) for t in trees]
    has_par = np.array([len(x) > 0 for x in widths])
    all_w = [x for ws in widths for x in ws]
    nest = np.array([nested_par(t) for t in trees])
    loop = np.array([has_op(t, LOOP) for t in trees])
    rep = np.array([max(Counter(leaves(t)).values()) > 1 for t in trees])
    lin = [get_number_of_sequentializations(t) for t in trees]
    multi = np.array([x > 1 for x in lin])
    log10_lin = np.array([math.log10(x) for x in lin])

    ms_key = [tuple(sorted(leaves(t))) for t in trees]
    ms_size = Counter(ms_key)
    shares_ms = np.array([ms_size[k] > 1 for k in ms_key])

    order = np.argsort(-counts)
    author, year, title, doi = LOG_SOURCES.get(key, ("", "", "", ""))

    return {
        "log": key,
        "log_name": LOG_NAMES.get(key, key),
        "source": f"{author} ({year}). {title}. 4TU.ResearchData. doi:{doi}",
        # raw log
        "raw_cases": facts["n_cases"],
        "raw_events": facts["n_events"],
        "raw_activities": facts["n_activities"],
        "events_per_case_mean": facts["events_per_case_mean"],
        "events_per_case_max": facts["events_per_case_max"],
        "lifecycle_values": facts["lifecycle_values"],
        "has_start_events": facts["has_start_events"],
        "same_timestamp_event_share": facts["same_timestamp_event_share"],
        "midnight_timestamp_share": facts["midnight_timestamp_share"],
        "first_timestamp": facts["first_timestamp"],
        "last_timestamp": facts["last_timestamp"],
        "n_case_attributes": facts["n_case_attributes"],
        # variants
        "cases": int(counts.sum()),
        "variants": n,
        "variants_per_100_cases": 100 * n / counts.sum(),
        "singleton_variant_share": float((counts == 1).mean()),
        "top10_variant_case_share": float(w[order[:10]].sum()),
        "fallthrough_dropped_variant_share": corpus["dropped_variant_share"],
        "fallthrough_dropped_case_share": corpus["dropped_case_share"],
        "length_mean": float(lens.mean()),
        "length_median": float(np.median(lens)),
        "length_p95": float(np.percentile(lens, 95)),
        "length_max": int(lens.max()),
        "depth_mean": float(deps.mean()),
        "depth_max": int(deps.max()),
        "par_variant_share": float(has_par.mean()),
        "par_case_share": float(w[has_par].sum()),
        "par_nodes_per_par_variant": float(np.mean([len(x) for x in widths if x])) if has_par.any() else 0.0,
        "par_width_mean": float(np.mean(all_w)) if all_w else 0.0,
        "par_width_max": int(max(all_w)) if all_w else 0,
        "nested_par_variant_share": float(nest.mean()),
        "loop_variant_share": float(loop.mean()),
        "repeat_variant_share": float(rep.mean()),
        "multi_order_variant_share": float(multi.mean()),
        "log10_orderings_median_par": float(np.median(log10_lin[has_par])) if has_par.any() else 0.0,
        "log10_orderings_max": float(log10_lin.max()),
        "shared_multiset_variant_share": float(shares_ms.mean()),
        "shared_multiset_case_share": float(w[shares_ms].sum()),
        "all_pairs": n * (n - 1) // 2,
    }


def main() -> None:
    keys = [a for a in sys.argv[1:] if not a.startswith("-")] or list(XES)
    rows = [r for r in (profile(k) for k in keys) if r is not None]
    if not rows:
        return
    existing = {}
    if OUT_CSV.exists() and len(keys) < len(XES):
        with open(OUT_CSV) as fh:
            existing = {r["log"]: r for r in csv.DictReader(fh)}
    for r in rows:
        existing[r["log"]] = r
    out = [existing[k] for k in XES if k in existing]
    with open(OUT_CSV, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(out)
    print(f"\n{len(out)} logs -> {OUT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
