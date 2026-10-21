"""
What every method can express, on one probe set (evaluation/phase2_probes.py), layer by layer: the
universe at 2, 3, 4; the synthetic dataset at 6, 9 (the sample), 12, 15, 20, 30, 45, 65, one layer
per repeat version; the real bases of each log and length bin; and the rule's shapes at 6 and 9
("check 6", "check 9"), to compare with every shape at 6 and the sample at 9.

  methods   one-hot, 3-grams, APTED, pq-grams, binary branches and the length check (as
            published, evaluation/baselines.py), and HRR on the full grid, five seeds, d = config.D;
            pq-grams also at each of its paper's settings (config.PQ_SWEEP), in rows of their
            own (test capability_pq_sweep)
  rules     told apart: above config.TOLD_APART_TOL for the methods without randomness, above
            the noise band on every seed for HRR (95th percentile of the gap between consecutive
            seeds over the layer's pairs); the same: at most the tolerance, or within the band on
            every seed

  one_step  told apart (one_step_pairs, one_step_told_apart)
  paths     grows: Kendall's tau between size and distance > 0 (on every seed), distances that
            are not told apart read as 0 (paths, paths_grow)
  count     the same on the count paths (count_paths, count_paths_grow)
  form      the same variant written differently gets the same answer (form_pairs, form_held)
  renamed   renaming every activity leaves the distance unchanged (renamed_pairs, renamed_held)
  sep       separability AUC: the variant written differently against the one-step moves,
            P(move farther) + P(tie) / 2 (separability_auc; HRR: median over seeds)
  combo     one more edit never brings the variant closer (combo_pairs, combo_held)
  named     each named case told apart, or the same where it says so (named_pairs, named_held;
            edit = the case)

Rows: test capability_methods, one per layer, group, edit and method (and HRR setting).  Probes
are built once per layer and saved (cache/phase2/probes/); a method done on a layer
leaves a marker (cache/phase2/capability/) and is skipped on a rerun.

    python evaluation/experiments/42_capability_methods.py                        # every layer, every method but APTED
    python evaluation/experiments/42_capability_methods.py --kinds universe --methods apted
    python evaluation/experiments/42_capability_methods.py --kinds lengths,real --methods apted
    python evaluation/experiments/42_capability_methods.py --build-only           # the probes only
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
import traceback
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from evaluation import config, dataset, phase2_probes, probe_sets, results  # noqa: E402
from evaluation.baselines import pair_distances as base_pairs  # noqa: E402
from evaluation.batch_hrr import pair_distances as hrr_pairs  # noqa: E402
from evaluation.corpus import load_log  # noqa: E402
from evaluation.methods import hrr_ranges  # noqa: E402
from rotation_hrr.tree_utils import tree_to_sequence  # noqa: E402
from rotation_hrr.variant_enumeration import canon  # noqa: E402

BASELINES = ["onehot", "trigram", "pqgram", "binary_branch", "length", "apted"]
GRID = [(a, b) for a in config.GRID["alpha"] for b in config.GRID["beta"]]
CACHE = config.ROOT / "cache" / "phase2"
PROBES = CACHE / "probes"
DONE = CACHE / "capability"
TOL = config.TOLD_APART_TOL


def safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)


# ---------------------------------------------------------------------------
# Layers and their probes
# ---------------------------------------------------------------------------


def layers(kinds, only=None):
    """(layer name, d, extra trees for HRR's ranges, [(group, base)], thinned)."""
    if "universe" in kinds:
        for n in dataset.UNIVERSE:
            yield f"universe {n}", config.D, [], probe_sets.universe(n), False
    if "lengths" in kinds:
        for n in dataset.LENGTHS:
            if only and n not in only:
                continue
            rows = dataset.sample_9() if n == 9 else dataset.variants(n)
            by_version: dict = {}
            for _, fam, version, t in rows:
                by_version.setdefault(version, []).append((fam, t))
            for v, bases in by_version.items():
                yield f"length {n}, {v}", config.D, [], bases, probe_sets.thinned(n)
    if "check" in kinds:
        for n in dataset.CHECK_LENGTHS:
            yield f"check {n}", config.D, [], probe_sets.check(n), False
    if "real" in kinds:
        for key in config.LOGS:
            c = load_log(key)
            lengths = np.array([len(tree_to_sequence(t)) for t in c.trees])
            for n, idx in probe_sets.real(lengths).items():
                if idx:
                    yield f"real {key}, length {n}", config.D, c.trees, \
                        [("all", c.trees[i]) for i in idx], probe_sets.thinned(n)


def build(name, bases, thin=False):
    """The layer's probes, each distinct tree once: (trees, table of pairs).  Saved."""
    p = PROBES / f"{safe(name)}.pkl"
    if p.exists():
        with open(p, "rb") as fh:
            return pickle.load(fh)
    trees, index, rows, pid = [], {}, [], [0]

    def idx(t):
        k = canon(t) + "|" + repr(t)            # a written form stays its own tree
        if k not in index:
            index[k] = len(trees)
            trees.append(t)
        return index[k]

    for group, t in bases:
        rmap = phase2_probes.rename_map(tree_to_sequence(t))
        for q in phase2_probes.probes_of(t, pid, rmap, thin):
            rows.append((q.kind, q.edit, group, q.size, q.position, q.path, q.expect, idx(q.a), idx(q.b)))
    table = pd.DataFrame(rows, columns=["kind", "edit", "group", "size", "position", "path", "expect",
                                        "ia", "ib"])
    PROBES.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}.tmp")      # two runs building one layer never collide
    with open(tmp, "wb") as fh:
        pickle.dump((trees, table), fh, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(p)
    return trees, table


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------


def path_index(table: pd.DataFrame) -> dict:
    """The pairs of every path (paths and count paths) with at least two steps, in order of
    size, grouped by the number of steps: {m: (paths, m) row indices}."""
    out: dict = {}
    sel = table[table["kind"].isin(["paths", "count"])]
    for _, g in sel.groupby(["kind", "path"]):
        if len(g) >= 2:
            out.setdefault(len(g), []).append(g.sort_values("size").index.to_numpy())
    return {m: np.stack(v) for m, v in out.items()}


def verdicts(table: pd.DataFrame, D: np.ndarray, noise, paths: dict) -> dict:
    """Per pair checks.  D: (pairs, seeds); noise: the threshold (TOL, or HRR's band)."""
    told = np.all(D > noise, axis=1)
    same = np.all(D <= noise, axis=1)
    Dz = np.where(D <= noise, 0.0, D)
    out = {"told": told, "same": same}
    grows = np.zeros(len(table), dtype=bool)
    sizes = table["size"].to_numpy(dtype=float)
    for m, IX in paths.items():                    # Kendall's tau-a of size and distance, per seed
        i, j = np.triu_indices(m, 1)
        sx = np.sign(sizes[IX][:, j] - sizes[IX][:, i])[:, :, None]
        sy = np.sign(Dz[IX][:, j] - Dz[IX][:, i])
        tau = (sx * sy).mean(axis=1)               # (paths, seeds)
        grows[IX[:, 0]] = np.all(tau > 0, axis=1)  # one verdict per path, on its first pair
    out["grows"] = grows
    held = np.zeros(len(table), dtype=bool)        # combo: not closer than the pair before it
    for _, g in table[table["kind"] == "combo"].groupby("path"):
        ix = g.sort_values("size").index.to_numpy()
        if len(ix) == 2:
            held[ix[1]] = np.all(D[ix[1]] >= D[ix[0]] - noise)
    renamed = np.zeros(len(table), dtype=bool)     # renamed: the same distance as its one-step twin
    one = table[table["kind"] == "one_step"].reset_index().set_index("path")["index"]
    for i in table.index[table["kind"] == "renamed"]:
        j = one.get(table.at[i, "path"])
        if j is not None:
            renamed[i] = np.all(np.abs(D[i] - D[j]) <= noise)
    out["combo"], out["renamed"] = held, renamed
    return out


def auc(same: np.ndarray, diff: np.ndarray) -> float:
    """P(a move is farther than a written-differently pair) + P(tie) / 2."""
    if not len(same) or not len(diff):
        return np.nan
    s = np.sort(same)
    lo = np.searchsorted(s, diff, side="left")
    hi = np.searchsorted(s, diff, side="right")
    return float((lo + 0.5 * (hi - lo)).sum() / (len(same) * len(diff)))


def rows_for(name, table, D, noise, base, paths) -> list[dict]:
    """Count rows per group and edit for one method (and HRR setting)."""
    v = verdicts(table, D, noise, paths)
    t = table.assign(told=v["told"], same=v["same"], grows=v["grows"], combo=v["combo"],
                     renamed=v["renamed"])
    rows = []

    def add(group, edit, metric, value):
        rows.append({**base, "log": name if group == "all" else f"{name}, {group}", "edit": edit,
                     "metric": metric, "result": value})

    for (group, edit), g in t.groupby(["group", "edit"]):
        k = g["kind"]
        one, pth, cnt = g[k == "one_step"], g[k == "paths"], g[k == "count"]
        if len(one):
            add(group, edit, "one_step_pairs", len(one))
            add(group, edit, "one_step_told_apart", int(one["told"].sum()))
        for sel, pre in ((pth, "paths"), (cnt, "count_paths")):
            firsts = sel.drop_duplicates("path")
            firsts = firsts[sel.groupby("path")["size"].transform("count").loc[firsts.index] >= 2]
            if len(firsts):
                add(group, edit, pre, len(firsts))
                add(group, edit, f"{pre}_grow", int(firsts["grows"].sum()))
        ren = g[k == "renamed"]
        if len(ren):
            add(group, edit, "renamed_pairs", len(ren))
            add(group, edit, "renamed_held", int(ren["renamed"].sum()))
        cmb = g[(k == "combo") & (g["expect"] == "not_closer")]
        if len(cmb):
            add(group, edit, "combo_pairs", len(cmb))
            add(group, edit, "combo_held", int(cmb["combo"].sum()))
        nm = g[k == "named"]
        if len(nm):
            ok = np.where(nm["expect"] == "same", nm["same"], nm["told"])
            add(group, edit, "named_pairs", len(nm))
            add(group, edit, "named_held", int(ok.sum()))
        fm = g[k == "form"]
        if len(fm):
            add(group, edit, "form_pairs", len(fm))
            add(group, edit, "form_held", int(fm["same"].sum()))
    forms = t.index[t["kind"] == "form"]
    moves = t.index[(t["kind"] == "one_step") & (t["edit"] == "move")]
    aucs = [auc(D[forms, s], D[moves, s]) for s in range(D.shape[1])]
    rows.append({**base, "log": name, "edit": "separability", "metric": "separability_auc",
                 "result": float(np.nanmedian(aucs)) if not np.all(np.isnan(aucs)) else np.nan})
    return rows


def run_method(name, d, extra, trees, table, method, commit) -> list[dict]:
    ia, ib = table["ia"].to_numpy(), table["ib"].to_numpy()
    paths = path_index(table)
    if method != "hrr":
        D = base_pairs(method, trees, ia, ib)[:, None]
        rows = rows_for(name, table, D, TOL, {"method": method, "test": "capability_methods",
                                               "commit": commit}, paths)
        if method == "pqgram":
            for p, q in config.PQ_SWEEP:
                Dk = base_pairs(method, trees, ia, ib, p=p, q=q)[:, None]
                rows += rows_for(name, table, Dk, TOL, {"method": method, "test": "capability_pq_sweep",
                                                         "knob": "p,q", "value": f"{p},{q}",
                                                         "commit": commit}, paths)
        return rows
    pairs = [(trees[i], trees[j]) for i, j in zip(ia, ib)]
    rg = hrr_ranges(list(trees) + list(extra))
    dist = hrr_pairs(pairs, rg, GRID, config.SEEDS, d)                    # (pairs, seeds, settings)
    rows = []
    for k, (a, b) in enumerate(GRID):
        Dk = dist[:, :, k]
        band = float(np.percentile(np.abs(np.diff(Dk, axis=1)), 95))
        base = {"method": "hrr", "test": "capability_methods", "knob": "alpha,beta,d",
                "value": f"{a:g},{b:g},{d}", "commit": commit}
        rows.append({**base, "log": name, "edit": "noise band", "metric": "noise_band", "result": band})
        rows += rows_for(name, table, Dk, band, base, paths)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default="universe,lengths,check,real")
    ap.add_argument("--only", default="", help="dataset lengths, e.g. 6,12")
    ap.add_argument("--methods", default=",".join(m for m in BASELINES if m != "apted") + ",hrr")
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()
    kinds = args.kinds.split(",")
    only = {int(x) for x in args.only.split(",") if x}
    methods = args.methods.split(",")
    commit = results.commit()
    DONE.mkdir(parents=True, exist_ok=True)
    failed = []
    for name, d, extra, bases, thin in layers(kinds, only):
        t0 = time.time()
        try:
            trees, table = build(name, bases, thin)
        except Exception:                                       # one layer must not stop the run
            failed.append((name, "build"))
            print(f"{name}: BUILD FAILED\n{traceback.format_exc()}", flush=True)
            continue
        print(f"{name}: {len(table):,} pairs, {len(trees):,} trees ({time.time() - t0:.0f} s)", flush=True)
        if args.build_only:
            continue
        rows, finished = [], []
        for m in methods:
            marker = DONE / f"{safe(name)}__{m}.done"
            if marker.exists():
                continue
            t1 = time.time()
            try:
                r = run_method(name, d, extra, trees, table, m, commit)
            except Exception:
                failed.append((name, m))
                print(f"  {m}: FAILED\n{traceback.format_exc()}", flush=True)
                continue
            rows += r
            finished.append((marker, f"{len(r)} rows, {time.time() - t1:.0f} s\n"))
            print(f"  {m}: {len(r)} rows ({time.time() - t1:.0f} s)", flush=True)
        if rows:
            results.write(rows)              # once per layer: every write rewrites the whole table
        for marker, text in finished:        # a method counts as done only once its rows are saved
            marker.write_text(text)
    print(f"done; failed: {failed or 'none'}", flush=True)


if __name__ == "__main__":
    main()
