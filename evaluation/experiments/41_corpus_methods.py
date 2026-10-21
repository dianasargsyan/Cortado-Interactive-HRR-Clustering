"""
Collisions, agreement with HRR and the cost of every pair, per corpus (the six logs and the
universe): every method's distances between every pair of variants, computed once and saved, then
read by every part.

  methods    one-hot, 3-grams, APTED, pq-grams, binary branches (as published,
             evaluation/baselines.py), and HRR at each knob off or on, five seeds, d = config.D;
             for collisions pq-grams also at each of its paper's settings (config.PQ_SWEEP),
             in rows of their own (test collisions_pq_sweep, not saved)
  saved      cache/phase2/<corpus>/<method>.npy: the upper triangle, float32, row by
             row as numpy.triu_indices orders it (HRR is recomputed, a few seconds per seed).  A
             saved file is not recomputed, and its cost rows are not written again: the final
             run starts from an empty folder.

  cost           test cost_methods: seconds for every pair of the corpus (representation
                 included) and the matrix's size; for HRR also one encoding and one knob change
  collisions     test collisions_methods: the share of variants, and of the cases they carry,
                 with a different variant (different sorted tree) at distance 0: at most
                 config.TOLD_APART_TOL for the methods without randomness, below the noise band
                 on every seed for HRR (95th percentile of the gap between consecutive seeds).
                 On the universe also per kind of pair: pairs that differ in one property only
                 (evaluation/universe.py's flags), and pairs that differ in several
  agreement      test agreement_methods: every method against HRR at each setting and seed,
                 Kendall's tau-b over all pairs and the share of each variant's 10 nearest under
                 HRR that are among its 10 nearest under the method, ties counted two ways: every
                 variant tied with the 10th nearest counts, or each tied variant counts as its
                 share of the remaining places (what random tie-breaking gives on average); HRR
                 against its next seed as the reference
  neighbourhood  test agreement_methods, edit "neighbourhood": per method (HRR per setting and
                 seed) the mean and median number of variants at or closer than each variant's
                 10th nearest, ties included (10 when the method ranks them all apart); for HRR
                 also within its noise band (what its seed noise cannot order)

    python evaluation/experiments/41_corpus_methods.py                     # every corpus, every method but APTED
    python evaluation/experiments/41_corpus_methods.py universe_4 --methods apted,onehot,...
    python evaluation/experiments/41_corpus_methods.py bpi2017 --methods apted --parts distances
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
from scipy.stats import kendalltau  # noqa: E402

from evaluation import config, results, synthetic, universe  # noqa: E402
from evaluation.batch_hrr import Batch  # noqa: E402
from evaluation.methods import hrr_ranges, represent  # noqa: E402
from rotation_hrr.encoder import RotationHRREncoder  # noqa: E402

CORPORA = list(config.LOGS) + ["universe_4"]
BASELINES = ["onehot", "trigram", "pqgram", "binary_branch", "apted"]
CACHE = config.ROOT / "cache" / "phase2"
K_NEAREST = 10


def path_of(corpus: str, method: str) -> Path:
    return CACHE / corpus / f"{method}.npy"


def save_distances(corpus, method, C, commit) -> list[dict]:
    """Compute and save one method's distances on one corpus; its cost rows."""
    p = path_of(corpus, method)
    if p.exists():
        return []
    t0 = time.perf_counter()
    D = represent(method, C, use_cache=False).distances
    seconds = time.perf_counter() - t0
    iu = np.triu_indices(C.n, 1)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp.npy")
    np.save(tmp, D[iu].astype(np.float32))
    tmp.replace(p)                                             # written in one step
    base = {"method": method, "log": corpus, "test": "cost_methods", "commit": commit}
    return [{**base, "metric": "seconds_all_pairs", "result": seconds},
            {**base, "metric": "matrix_mb", "result": D.nbytes / 1e6}]


def hrr_triangles(C, a, b, d):
    """HRR's upper-triangle distances at one setting, one array per seed, float32."""
    batch = Batch(C.trees)
    rg = hrr_ranges(C.trees)
    iu = np.triu_indices(C.n, 1)
    out = []
    for s in config.SEEDS:
        enc = RotationHRREncoder(d=d, n_max=rg[0], n_max_depth=rg[1], seed=s)
        X = batch.vectors(enc, a, b)
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        out.append((np.arccos(np.clip(X @ X.T, -1, 1)) / np.pi)[iu].astype(np.float32))
        del X
    return out


def hrr_cost(C, d, commit) -> list[dict]:
    """HRR at both knobs on: one encoding, every pair, one knob change; median of three runs."""
    batch = Batch(C.trees)
    rg = hrr_ranges(C.trees)
    enc = RotationHRREncoder(d=d, n_max=rg[0], n_max_depth=rg[1], seed=config.DEFAULT_SEED)

    def med(f):
        ts = []
        for _ in range(3):
            t0 = time.perf_counter()
            f()
            ts.append(time.perf_counter() - t0)
        return float(np.median(ts))

    X = batch.vectors(enc, 1.0, 1.0)

    def pairs():
        Y = X / np.linalg.norm(X, axis=1, keepdims=True)
        np.arccos(np.clip(Y @ Y.T, -1, 1))

    def knob_change():
        Z = batch.vectors(enc, 0.0, 1.0)
        Z /= np.linalg.norm(Z, axis=1, keepdims=True)
        np.arccos(np.clip(Z @ Z.T, -1, 1))

    base = {"method": "hrr", "log": C.name, "test": "cost_methods", "knob": "d", "value": d,
            "commit": commit}
    return [{**base, "metric": "seconds_encode", "result": med(lambda: batch.vectors(enc, 1.0, 1.0))},
            {**base, "metric": "seconds_all_pairs", "result": med(pairs)},
            {**base, "metric": "seconds_knob_change", "result": med(knob_change)},
            {**base, "metric": "matrix_mb", "result": C.n * C.n * 8 / 1e6}]


# ---------------------------------------------------------------------------
# Collisions
# ---------------------------------------------------------------------------


def colliding(C, mask_pairs):
    """Shares of variants, and of the cases they carry, in at least one colliding pair."""
    iu = np.triu_indices(C.n, 1)
    hit = np.zeros(C.n, dtype=bool)
    hit[iu[0][mask_pairs]] = True
    hit[iu[1][mask_pairs]] = True
    counts = np.asarray(C.counts, dtype=np.float64)
    return float(hit.mean()), float(counts[hit].sum() / counts.sum())


def kinds_of_pair(C):
    """On the universe: the kind of each pair, the one property it differs in (evaluation/universe.py's
    flags), or "several"."""
    F = universe.features(C.trees)
    fl = universe.pair_flags(F)
    iu = np.triu_indices(C.n, 1)
    names = list(fl)
    M = np.stack([fl[f][iu] for f in names])                  # (flags, pairs)
    count = M.sum(axis=0)
    kind = np.full(len(iu[0]), "several", dtype=object)
    for k, f in enumerate(names):
        kind[(count == 1) & M[k]] = f"{f} only"
    return kind


def part_collisions(corpus, C, methods, commit) -> list[dict]:
    iu = np.triu_indices(C.n, 1)
    different = C.canonical_ids[iu[0]] != C.canonical_ids[iu[1]]
    kind = kinds_of_pair(C) if corpus.startswith("universe") else None
    rows = []

    def add(method, mask, value=None, knob=None, test="collisions_methods"):
        v, c = colliding(C, mask)
        base = {"method": method, "log": corpus, "test": test, "knob": knob,
                "value": value, "commit": commit}
        rows.extend([{**base, "metric": "colliding_variant_share", "result": v},
                     {**base, "metric": "colliding_case_share", "result": c}])
        if kind is not None:
            for k in np.unique(kind):
                sel = kind == k
                rows.extend([{**base, "edit": k, "metric": "pairs", "result": int(sel.sum())},
                             {**base, "edit": k, "metric": "colliding_pair_share",
                              "result": float(mask[sel].mean())}])

    for m in methods:
        if m == "hrr":
            continue
        if not path_of(corpus, m).exists():
            print(f"  collisions: {m} has no saved distances on {corpus}, skipped", flush=True)
            continue
        add(m, (np.load(path_of(corpus, m)) <= config.TOLD_APART_TOL) & different)
    if "pqgram" in methods:
        for p, q in config.PQ_SWEEP:
            D = represent("pqgram", C, use_cache=False, p=p, q=q).distances
            add("pqgram", (D[iu] <= config.TOLD_APART_TOL) & different, f"{p},{q}", "p,q",
                test="collisions_pq_sweep")
            del D
    if "hrr" in methods:
        d = config.D
        for a, b in config.PHASE2_SETTINGS:
            T = hrr_triangles(C, a, b, d)
            band = float(np.percentile(np.abs(np.diff(np.stack(T), axis=0)), 95))
            add("hrr", np.all(np.stack(T) < band, axis=0) & different, f"{a:g},{b:g},{d}", "alpha,beta,d")
            rows.append({"method": "hrr", "log": corpus, "test": "collisions_methods",
                         "knob": "alpha,beta,d", "value": f"{a:g},{b:g},{d}", "metric": "noise_band",
                         "result": band, "commit": commit})
            del T
    return rows


# ---------------------------------------------------------------------------
# Agreement with HRR
# ---------------------------------------------------------------------------


def square(tri: np.ndarray, n: int) -> np.ndarray:
    D = np.zeros((n, n), dtype=np.float32)
    iu = np.triu_indices(n, 1)
    D[iu] = tri
    return D + D.T


def nearest(D: np.ndarray, k: int = K_NEAREST, chunk: int = 512):
    """Per row (self excluded), as sparse matrices: the k nearest (ties broken by index), and two
    tie-aware weights: every variant tied with the k-th nearest counts fully ("all"), or the
    tied ones share the remaining places equally ("share", the average of random tie-breaking)."""
    from scipy import sparse
    n = len(D)
    kk = min(k, n - 1)
    near_r, near_c, all_r, all_c, share_v = [], [], [], [], []
    for s in range(0, n, chunk):
        R = D[s:s + chunk].astype(np.float64)
        rows = np.arange(len(R))
        R[rows, s + rows] = np.inf
        order = np.argsort(R, axis=1, kind="stable")[:, :kk]
        near_r.append(np.repeat(s + rows, kk))
        near_c.append(order.ravel())
        kth = np.take_along_axis(R, order[:, -1:], axis=1)
        closer = R < kth - 1e-12
        tied = np.abs(R - kth) <= 1e-12
        n_closer = closer.sum(axis=1, keepdims=True)
        n_tied = np.maximum(tied.sum(axis=1, keepdims=True), 1)
        w = closer + tied * ((kk - n_closer) / n_tied)
        r, c = np.nonzero(closer | tied)
        all_r.append(s + r)
        all_c.append(c)
        share_v.append(w[r, c])
    near = sparse.csr_matrix((np.ones(sum(map(len, near_r))), (np.concatenate(near_r),
                              np.concatenate(near_c))), shape=(n, n))
    r, c = np.concatenate(all_r), np.concatenate(all_c)
    w_all = sparse.csr_matrix((np.ones(len(r)), (r, c)), shape=(n, n))
    w_share = sparse.csr_matrix((np.concatenate(share_v), (r, c)), shape=(n, n))
    return near, w_all, w_share


def overlap(W, near_h) -> float:
    """Mean over variants of the share of HRR's k nearest that the method's weights cover."""
    return float(np.asarray(W.multiply(near_h).sum(axis=1)).mean() / K_NEAREST)


def part_agreement(corpus, C, methods, commit) -> list[dict]:
    rows = []
    d = config.D
    others = {}
    for m in methods:
        if m == "hrr":
            continue
        if not path_of(corpus, m).exists():
            print(f"  agreement: {m} has no saved distances on {corpus}, skipped", flush=True)
            continue
        tri = np.load(path_of(corpus, m))
        _, w_all, w_share = nearest(square(tri, C.n))
        others[m] = (tri, w_all, w_share)
    for a, b in config.PHASE2_SETTINGS:
        T = hrr_triangles(C, a, b, d)
        value = f"{a:g},{b:g},{d}"
        for si, (s, tri_h) in enumerate(zip(config.SEEDS, T)):
            near_h, _, _ = nearest(square(tri_h, C.n))
            base = {"method": "hrr", "log": corpus, "seed": s, "knob": "alpha,beta,d", "value": value,
                    "test": "agreement_methods", "commit": commit}
            for m, (tri, w_all, w_share) in others.items():
                tau = kendalltau(tri_h, tri, variant="b").statistic
                rows.extend([
                    {**base, "edit": f"vs {m}", "metric": "rank_agreement_tau_b", "result": float(tau)},
                    {**base, "edit": f"vs {m}", "metric": "neighbours_kept_ties_all",
                     "result": overlap(w_all, near_h)},
                    {**base, "edit": f"vs {m}", "metric": "neighbours_kept_ties_share",
                     "result": overlap(w_share, near_h)}])
            if si + 1 < len(T):                                   # the reference: the next seed
                near_n, _, _ = nearest(square(T[si + 1], C.n))
                tau = kendalltau(tri_h, T[si + 1], variant="b").statistic
                rows.extend([
                    {**base, "edit": "vs next seed", "metric": "rank_agreement_tau_b", "result": float(tau)},
                    {**base, "edit": "vs next seed", "metric": "neighbours_kept_ties_share",
                     "result": overlap(near_n, near_h)}])
        print(f"  agreement: {corpus} at {value} done", flush=True)
        del T
    return rows


HRR_ROUNDING = 1e-6     # HRR's identical vectors land below 1e-6 (rounding in arccos), and no
                        # distance between different vectors falls below 1e-3 (Domestic, Sepsis)


def tie_sizes(D: np.ndarray, tol: float, k: int = K_NEAREST, chunk: int = 512) -> np.ndarray:
    """Per variant, how many variants sit at or closer than its k-th nearest, plus at most *tol*
    (self excluded): k when the method ranks them all apart, more where it cannot.  *tol*:
    config.TOLD_APART_TOL for the methods without randomness, HRR_ROUNDING for HRR (the same
    representation, the same distance), or HRR's noise band (what its seed noise cannot order)."""
    n = len(D)
    kk = min(k, n - 1)
    out = np.empty(n)
    for s in range(0, n, chunk):
        R = D[s:s + chunk].astype(np.float64)
        rows = np.arange(len(R))
        R[rows, s + rows] = np.inf
        kth = np.partition(R, kk - 1, axis=1)[:, kk - 1:kk]
        out[s:s + len(R)] = (R <= kth + tol).sum(axis=1)
    return out


def part_neighbourhood(corpus, C, methods, commit) -> list[dict]:
    """Each method's neighbourhood size, the mean and median over variants of tie_sizes(); HRR
    per setting and seed, also within its noise band (as for the collisions)."""
    rows = []

    def add(base, sizes, pre="neighbourhood_size"):
        rows.extend([{**base, "metric": f"{pre}_mean", "result": float(sizes.mean())},
                     {**base, "metric": f"{pre}_median", "result": float(np.median(sizes))}])

    for m in methods:
        if m == "hrr":
            continue
        if not path_of(corpus, m).exists():
            print(f"  neighbourhood: {m} has no saved distances on {corpus}, skipped", flush=True)
            continue
        add({"method": m, "log": corpus, "test": "agreement_methods", "edit": "neighbourhood",
             "commit": commit}, tie_sizes(square(np.load(path_of(corpus, m)), C.n), config.TOLD_APART_TOL))
    if "hrr" in methods:
        d = config.D
        for a, b in config.PHASE2_SETTINGS:
            T = hrr_triangles(C, a, b, d)
            band = float(np.percentile(np.abs(np.diff(np.stack(T), axis=0)), 95))
            for s, tri in zip(config.SEEDS, T):
                base = {"method": "hrr", "log": corpus, "seed": s, "knob": "alpha,beta,d",
                        "value": f"{a:g},{b:g},{d}", "test": "agreement_methods",
                        "edit": "neighbourhood", "commit": commit}
                D = square(tri, C.n)
                add(base, tie_sizes(D, HRR_ROUNDING))
                add(base, tie_sizes(D, band), "neighbourhood_size_within_band")
                del D
            del T
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpora", nargs="*", default=CORPORA)
    ap.add_argument("--methods", default=",".join(m for m in BASELINES if m != "apted") + ",hrr")
    ap.add_argument("--parts", default="distances,cost,collisions,agreement")
    args = ap.parse_args()
    methods = args.methods.split(",")
    parts = args.parts.split(",")
    commit = results.commit()
    for corpus in args.corpora:
        t0 = time.time()
        C = synthetic.corpus(corpus)
        print(f"{corpus}: {C.n} variants, d = {config.D}", flush=True)
        rows = []
        if "distances" in parts:
            for m in methods:
                if m != "hrr":
                    r = save_distances(corpus, m, C, commit)
                    if r:
                        rows += r
                        print(f"  {m}: {r[0]['result']:.1f} s", flush=True)
        if "cost" in parts and "hrr" in methods:
            rows += hrr_cost(C, config.D, commit)
        if rows:
            results.write(rows)
        if "collisions" in parts:
            results.write(part_collisions(corpus, C, methods, commit))
            print("  collisions done", flush=True)
        if "agreement" in parts and "hrr" in methods:
            results.write(part_agreement(corpus, C, methods, commit))
        if "neighbourhood" in parts:
            results.write(part_neighbourhood(corpus, C, methods, commit))
            print("  neighbourhood done", flush=True)
        print(f"{corpus} done ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    main()
