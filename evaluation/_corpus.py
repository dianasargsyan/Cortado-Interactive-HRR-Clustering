"""
The logs as the evaluation uses them: each log's cached variants without the ones that contain a
Fallthrough node.  Cortado makes a Fallthrough when part of a variant fits neither a sequence nor
a parallel block, and lists its activities alphabetically, so their recorded order is lost; the
evaluation leaves such variants out rather than compare an order nobody recorded.  Every script
reports how many variants and cases the filter removed.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
from cortado_core.subprocess_discovery.concurrency_trees.cTrees import cTreeOperator

FALLTHROUGH = cTreeOperator.Fallthrough
LOOP = cTreeOperator.Loop

LOG_NAMES = {
    "domestic": "Domestic Declarations",
    "prepaid": "Prepaid Travel Cost",
    "roadtraffic": "Road Traffic Fine Mgmt.",
    "sepsis": "Sepsis Cases",
    "hospital": "Hospital Billing",
    "permit": "Permit Log",
    "bpic15_1": "BPIC15_1",
    "bpi2012": "BPI Challenge 2012",
    "bpi2017": "BPI Challenge 2017",
    "bpi2011": "BPI Challenge 2011",
    "bpi2018": "BPI Challenge 2018",
}

# (authors, year, title, DOI) as given on 4TU.ResearchData.
LOG_SOURCES = {
    "domestic": ("van Dongen, B.F.", 2020, "BPI Challenge 2020: Domestic Declarations",
                 "10.4121/uuid:3f422315-ed9d-4882-891f-e180b5b4feb5"),
    "prepaid": ("van Dongen, B.F.", 2020, "BPI Challenge 2020: Prepaid Travel Costs",
                "10.4121/datasets/fb84cf2d-166f-4de2-87be-62ee317077e5"),
    "permit": ("van Dongen, B.F.", 2020, "BPI Challenge 2020: Travel Permit Data",
               "10.4121/uuid:ea03d361-a7cd-4f5e-83d8-5fbdf0362550"),
    "roadtraffic": ("de Leoni, M.; Mannhardt, F.", 2015, "Road Traffic Fine Management Process",
                    "10.4121/uuid:270fd440-1057-4fb9-89a9-b699b47990f5"),
    "sepsis": ("Mannhardt, F.", 2016, "Sepsis Cases - Event Log",
               "10.4121/uuid:915d2bfb-7e84-49ad-a286-dc35f063a460"),
    "hospital": ("Mannhardt, F.", 2017, "Hospital Billing - Event Log",
                 "10.4121/uuid:76c46b83-c930-4798-a1c9-4be94dfeb741"),
    "bpic15_1": ("van Dongen, B.F.", 2015, "BPI Challenge 2015 Municipality 1",
                 "10.4121/uuid:a0addfda-2044-4541-a450-fdcc9fe16d17"),
    "bpi2011": ("van Dongen, B.F.", 2011, "Real-life event logs - Hospital log",
                "10.4121/uuid:d9769f3d-0ab0-4fb8-803b-0d1120ffcf54"),
    "bpi2012": ("van Dongen, B.F.", 2012, "BPI Challenge 2012",
                "10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f"),
    "bpi2017": ("van Dongen, B.F.", 2017, "BPI Challenge 2017",
                "10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b"),
    "bpi2018": ("van Dongen, B.F.; Borchert, F.", 2018, "BPI Challenge 2018",
                "10.4121/uuid:3301445f-95e8-4ff0-98a4-901f1f204972"),
}


def has_op(tree, op) -> bool:
    """Whether *op* occurs anywhere in the tree."""
    if tree.label is not None:
        return False
    return tree.op == op or any(has_op(c, op) for c in tree.children)


def load_corpus(cache_dir: Path, key: str) -> dict | None:
    """One log's variants without the Fallthrough ones, with what the filter removed
    (n_dropped, dropped_variant_share, dropped_case_share) and the share of variants with a
    loop.  None if the log is not cached."""
    path = cache_dir / f"variants_{key}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as fh:
        blob = pickle.load(fh)

    trees = list(blob["trees"])
    counts = np.asarray(blob["counts"], dtype=np.float64)
    n_before, cases_before = len(trees), counts.sum()
    keep = np.array([not has_op(t, FALLTHROUGH) for t in trees])
    trees = [t for t, k in zip(trees, keep) if k]
    counts = counts[keep]
    if not trees:
        return None

    return {
        "log": key,
        "log_name": LOG_NAMES.get(key, key),
        "trees": trees,
        "counts": counts,
        "n_variants": len(trees),
        "n_cases": int(counts.sum()),
        "max_leaves": blob["max_leaves"],
        "n_dropped": n_before - len(trees),
        "dropped_variant_share": 1.0 - len(trees) / n_before,
        "dropped_case_share": float(1.0 - counts.sum() / cases_before),
        "loop_variant_share": float(np.mean([has_op(t, LOOP) for t in trees])),
    }


def filter_note(c: dict) -> str:
    """One line on what the filter removed."""
    if c["n_dropped"] == 0:
        return (f"{c['log_name']}: {c['n_variants']:,} variants, "
                f"{c['n_cases']:,} cases (no Fallthrough variants to drop; "
                f"LOOP in {c['loop_variant_share']:.1%})")
    return (f"{c['log_name']}: {c['n_variants']:,} variants, {c['n_cases']:,} cases "
            f"after dropping {c['n_dropped']:,} Fallthrough variants "
            f"({c['dropped_variant_share']:.1%} of variants, "
            f"{c['dropped_case_share']:.1%} of cases); "
            f"LOOP kept, present in {c['loop_variant_share']:.1%}")
