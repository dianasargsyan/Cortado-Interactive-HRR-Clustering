"""
Extract each log's concurrency-tree variants with Cortado and cache them as
cache/variants/variants_<key>.pkl:

    {'n_cases', 'n_variants', 'counts', 'trees', 'max_leaves', 'load_time_s'}

    python evaluation/experiments/03_cache_variants.py bpi2012 bpi2017
    python evaluation/experiments/03_cache_variants.py --all
    python evaluation/experiments/03_cache_variants.py --list
    python evaluation/experiments/03_cache_variants.py bpi2018 --light

``--light`` reads the XES with the streaming reader in ``_xes.py`` instead of ``pm4py.read_xes``,
keeping only activity, timestamp and lifecycle.  It gives the same variants and case counts
(checked on Sepsis and Domestic) and loads BPI Challenge 2018 in 8 GB of memory.  It also writes
the raw log's facts (lifecycle transitions, shared timestamps, time span, case attributes) to
``logfacts_<key>.json``, which ``16_log_profile.py`` reads.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import ROOT as _root, require_cortado_env  # noqa: E402

require_cortado_env()

import pm4py
from cortado_core.utils.cvariants import get_concurrency_variants

from rotation_hrr.tree_rewrites import groups_to_trees
from rotation_hrr.variant_enumeration import n_leaves

CACHE_DIR = _root / "cache" / "variants"
DATA = _root / "data"

LOGS = {
    "domestic":    ("Domestic Declarations",      DATA / "DomesticDeclarations.xes"),
    "prepaid":     ("Prepaid Travel Cost",        DATA / "PrepaidTravelCost.xes"),
    "roadtraffic": ("Road Traffic Fine Mgmt.",    DATA / "Road_Traffic_Fine_Management_Process.xes"),
    "sepsis":      ("Sepsis Cases",               DATA / "Sepsis Cases - Event Log.xes"),
    "hospital":    ("Hospital Billing",           DATA / "Hospital Billing - Event Log.xes"),
    "permit":      ("Permit Log",                 DATA / "PermitLog.xes"),
    "bpic15_1":    ("BPIC15_1",                   DATA / "BPIC15_1.xes"),
    "bpi2012":     ("BPI Challenge 2012",         DATA / "BPI_Challenge_2012.xes"),
    "bpi2017":     ("BPI Challenge 2017",         DATA / "BPI Challenge 2017.xes"),
    "bpi2011":     ("BPI Challenge 2011",         DATA / "Hospital_log.xes"),
    # BPI Challenge 2013 is not cached: its lifecycle:transition holds
    # sub-statuses ("In Progress", "Closed"), not start/complete, so cortado
    # keeps no events and every variant is empty.  Using it would need its own
    # classifier decision; not worth it for a candidate log.
    # BPI 2018: variant extraction did not finish in over ten minutes and was
    # stopped; not a candidate.
    "bpi2018":     ("BPI Challenge 2018",         DATA / "BPI Challenge 2018.xes"),
}


def cache_path(key: str) -> Path:
    return CACHE_DIR / f"variants_{key}.pkl"


def facts_path(key: str) -> Path:
    return CACHE_DIR / f"logfacts_{key}.json"


def read_log(key: str, light: bool):
    """Parse one log; with *light*, also write its raw-log facts."""
    _, path = LOGS[key]
    if light:
        from evaluation._xes import read_xes_light

        log, facts = read_xes_light(path)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        facts_path(key).write_text(json.dumps(facts, indent=2, default=str))
        return log
    log_df = pm4py.read_xes(str(path))
    return pm4py.convert_to_event_log(log_df)


def cache_variants(key: str, force: bool = False, light: bool = False) -> dict | None:
    """Parse one log, extract concurrency variants, write the cache."""
    name, path = LOGS[key]
    out = cache_path(key)

    if out.exists() and not force:
        with open(out, "rb") as fh:
            data = pickle.load(fh)
        print(f"[{key}] cached already: {data['n_variants']} variants "
              f"from {data['n_cases']} cases")
        return data

    if not path.exists():
        print(f"[{key}] MISSING: {path}")
        return None

    size_mb = path.stat().st_size / 1e6
    print(f"[{key}] parsing {name} ({size_mb:.0f} MB) ...", flush=True)
    t0 = time.perf_counter()

    log = read_log(key, light)
    print(f"[{key}]   parsed in {time.perf_counter() - t0:.0f}s, "
          f"extracting variants ...", flush=True)

    variants = get_concurrency_variants(log)
    variant_items = sorted(variants.items(), key=lambda kv: len(kv[1]), reverse=True)
    groups_all = [v[0] for v in variant_items]
    counts_all = [len(v[1]) for v in variant_items]
    trees_all = groups_to_trees(groups_all)
    max_leaves = max(n_leaves(t) for t in trees_all)

    data = {
        "n_cases": len(log),
        "n_variants": len(groups_all),
        "counts": counts_all,
        "trees": trees_all,
        "max_leaves": max_leaves,
        "load_time_s": time.perf_counter() - t0,
    }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(data, fh)

    print(f"[{key}]   {data['n_cases']} cases, {data['n_variants']} variants, "
          f"max {max_leaves} leaves/variant, {data['load_time_s']:.0f}s total")
    print(f"[{key}]   wrote {out.name} ({out.stat().st_size / 1e6:.1f} MB)",
          flush=True)
    return data


def report_par_structure(key: str, data: dict) -> None:
    """How many of the log's variants contain a parallel block, and how many blocks."""
    from cortado_core.subprocess_discovery.concurrency_trees.cTrees import cTreeOperator

    def count_par(t) -> int:
        if t.label is not None:
            return 0
        own = 1 if t.op == cTreeOperator.Concurrent else 0
        return own + sum(count_par(c) for c in t.children)

    trees = data["trees"]
    par_counts = [count_par(t) for t in trees]
    with_par = sum(1 for c in par_counts if c > 0)
    print(f"[{key}]   PAR structure: {with_par}/{len(trees)} variants contain a "
          f"PAR node ({with_par / len(trees):.1%}), "
          f"{sum(par_counts)} PAR nodes total, max {max(par_counts)} per variant")


def main() -> None:
    args = sys.argv[1:]

    if not args or "--list" in args:
        print("Available log keys:")
        for key, (name, path) in LOGS.items():
            mark = "cached" if cache_path(key).exists() else (
                "     " if path.exists() else "NO XES"
            )
            print(f"  [{mark}] {key:<12} {name}")
        return

    keys = list(LOGS) if "--all" in args else [a for a in args if not a.startswith("-")]
    force = "--force" in args
    light = "--light" in args

    for key in keys:
        if key not in LOGS:
            print(f"unknown log key: {key}")
            continue
        data = cache_variants(key, force=force, light=light)
        if data is not None:
            report_par_structure(key, data)
        print()


if __name__ == "__main__":
    main()
