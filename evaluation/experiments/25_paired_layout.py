"""
Does pairing the frequency banks remove the direction effect, and what else does it change?  HRR
against itself only; nothing is scored against an expected distance.

Two layouts of the encoder's frequency banks, with the same random vectors (same seed):

  shared   block k turns by a*p*theta_k + b*d*theta'_k
  paired   blocks in pairs with equal frequencies; the first of each pair turns by
           a*p*theta + b*d*theta', the second by a*p*theta - b*d*theta'.  Each bank then has
           half as many distinct frequencies, over the same range.

Decision rule, fixed before the run: adopt the paired layout if (a) at every beta > 0 the
direction gaps fall to the beta = 0 control level, for every edit and mirror family, at every
setting and seed, and (b) the should-be-the-same checks still hold.  Everything else is reported,
not scored.

  A  direction, synthetic   every shape with 2 to N_EXHAUSTIVE activities and every single edit
                            that keeps the length: d(base, edited) against the same pair read
                            backwards; and three mirror families at LENGTHS
  B  real logs              each log: rank agreement (Spearman and Kendall's tau-b) of all
                            distances at beta against -beta (the sign only picks the
                            direction), next to two seeds at the same beta; and shared against
                            paired
  C  what else changes      seed-free kernels: the similarity of an activity to itself moved by
                            (dp, dd), for position-only, depth-only and combined moves; flipping
                            beta alone; moves in both that look less moved than one of their
                            parts
  D  how much moves         rank agreement of shared against paired on the universe
  E  follow-up              for joins, nesting and sequence to parallel: 20 seeds per pair and a
                            t-test on the mean gap, on three independent sets of 20 seeds; and
                            the paired layout's identity (a pair read backwards under v = the
                            pair under the mirrored, pair-swapped v) checked exactly

Grid: config.GRID (beta = 0 is the control), five seeds.

    python evaluation/experiments/25_paired_layout.py            # all parts
    python evaluation/experiments/25_paired_layout.py A C        # some parts
    python evaluation/experiments/25_paired_layout.py B:domestic # part B on some logs
    python evaluation/experiments/25_paired_layout.py E          # the follow-up
"""

from __future__ import annotations

import itertools
import sys
import time
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402
from scipy.stats import rankdata  # noqa: E402

from evaluation import config, probes, results  # noqa: E402
from evaluation import universe as U  # noqa: E402
from evaluation.agreement import tau_b  # noqa: E402
from evaluation.batch_hrr import Batch  # noqa: E402
from evaluation.corpus import load_log  # noqa: E402
from evaluation.methods import angular, hrr_ranges  # noqa: E402
from evaluation.orders import backwards  # noqa: E402
from rotation_hrr.encoder import RotationHRREncoder  # noqa: E402
from rotation_hrr.tree_utils import tree_to_positioned_sequence  # noqa: E402
from rotation_hrr.variant_enumeration import canon, leaf, par, seq  # noqa: E402

LAYOUTS = ("shared", "paired")
G = config.GRID
N_EXHAUSTIVE = 7
LENGTHS = (4, 5, 6, 8, 10, 16, 24, 32, 48, 64)
SAME_LENGTH_EDITS = ("move", "relabel", "seq_to_par", "joins", "nesting")
FAMILIES = ("alongside", "seq_to_par", "joins")


# ---------------------------------------------------------------------------
# Encoders
# ---------------------------------------------------------------------------

def _spread(top: float, n_max: int, m: int) -> np.ndarray:
    low = np.pi / (n_max * 1.5)
    return top * (low / top) ** (np.arange(m) / (m - 1))


def encoder(layout: str, d: int, seed: int, ranges, labels) -> RotationHRREncoder:
    """The encoder with its banks laid out as *layout*, frequency ranges (n_max, n_max_depth)
    from the variants it encodes; label vectors drawn in sorted order."""
    e = RotationHRREncoder(d=d, n_max=ranges[0], n_max_depth=ranges[1], seed=seed)
    half = d // 2
    if layout == "shared":          # set explicitly, whatever the encoder's own layout
        e.thetas = _spread(e.theta_max, e.n_max, half)
        e.depth_thetas = _spread(e.theta_max_depth, e.n_max_depth, half)
    else:
        e.thetas = np.repeat(_spread(e.theta_max, e.n_max, half // 2), 2)
        e.depth_thetas = (np.repeat(_spread(e.theta_max_depth, e.n_max_depth, half // 2), 2)
                          * np.tile([1.0, -1.0], half // 2))
    for a in sorted(labels):
        e.get_label_vector(a)
    return e


_BATCHES: dict = {}


def vectors(enc, trees, alpha, beta) -> np.ndarray:
    """Unit vectors of *trees* under *enc* (through the batch encoder, built once per tree list)."""
    if id(trees) not in _BATCHES:
        _BATCHES[id(trees)] = (trees, Batch(trees))
    X = _BATCHES[id(trees)][1].vectors(enc, alpha, beta)
    return X / np.linalg.norm(X, axis=1, keepdims=True)


def pair_dist(X, i, j) -> np.ndarray:
    return np.arccos(np.clip(np.einsum("ij,ij->i", X[i], X[j]), -1, 1)) / np.pi


def labels_of(trees):
    return {a for t in trees for a, _, _ in tree_to_positioned_sequence(t)[0]}


def settings(betas=None):
    return list(itertools.product(G["alpha"], betas if betas is not None else G["beta"], G["d"]))


def row(commit, layout, a, b, d, **kw):
    return {"method": "hrr", "knob": "layout,alpha,beta,d", "value": f"{layout},{a:g},{b:g},{d}",
            "commit": commit, **kw}


# ---------------------------------------------------------------------------
# A  Direction on synthetic trees
# ---------------------------------------------------------------------------

def family(name, n):
    L = lambda i: leaf(f"A{i}")                          # noqa: E731
    r = range(1, n + 1)
    if name == "alongside":
        return (seq(*[L(i) for i in r]), par(L(1), seq(*[L(i) for i in r if i > 1])),
                seq(*[L(i) for i in r]), par(seq(*[L(i) for i in r if i < n]), L(n)))
    if name == "seq_to_par":
        return (seq(*[L(i) for i in r]), seq(par(L(1), L(2)), *[L(i) for i in r if i > 2]),
                seq(*[L(i) for i in r]), seq(*[L(i) for i in r if i < n - 1], par(L(n - 1), L(n))))
    b1 = seq(par(L(1), L(2)), *[L(i) for i in r if i > 2])
    e1 = seq(par(L(1), L(2), L(3)), *[L(i) for i in r if i > 3])
    b2 = seq(*[L(i) for i in r if i < n - 1], par(L(n - 1), L(n)))
    e2 = seq(*[L(i) for i in r if i < n - 2], par(L(n - 2), L(n - 1), L(n)))
    return b1, e1, b2, e2


def part_a(commit) -> list[dict]:
    edits = [e for n in range(2, N_EXHAUSTIVE + 1) for t in probes.shapes(n)
             for e in probes.single_edits(t) if e.edit in SAME_LENGTH_EDITS]
    fam = [(f, n, family(f, n)) for f in FAMILIES for n in LENGTHS]
    trees, index = [], {}

    def add(t):
        k = canon(t)
        if k not in index:
            index[k] = len(trees)
            trees.append(t)
        return index[k]

    P = np.array([(add(e.base), add(e.edited), add(backwards(e.base)), add(backwards(e.edited)))
                  for e in edits])
    Fm = np.array([[add(x) for x in quad] for _, _, quad in fam])
    ed = np.array([e.edit for e in edits])
    labs = labels_of(trees)
    ranges = hrr_ranges(trees)
    print(f"A: {len(edits):,} pairs, {len(fam)} mirror pairs, {len(trees):,} trees", flush=True)
    rows = []
    for layout, (a, b, d) in itertools.product(LAYOUTS, settings()):
        G_pairs, G_fam = [], []
        for s in config.SEEDS:
            X = vectors(encoder(layout, d, s, ranges, labs), trees, a, b)
            G_pairs.append(pair_dist(X, P[:, 0], P[:, 1]) - pair_dist(X, P[:, 2], P[:, 3]))
            d1, d2 = pair_dist(X, Fm[:, 0], Fm[:, 1]), pair_dist(X, Fm[:, 2], Fm[:, 3])
            G_fam.append(np.stack([d1, d2]))
        G_pairs, G_fam = np.array(G_pairs), np.array(G_fam)            # seeds x pairs; seeds x 2 x fam
        for e in SAME_LENGTH_EDITS:
            g = G_pairs[:, ed == e]
            agree = np.mean(np.all(g > 1e-12, axis=0) | np.all(g < -1e-12, axis=0))
            base = row(commit, layout, a, b, d, log=f"shapes_2to{N_EXHAUSTIVE}", test="direction",
                       edit=e)
            rows += [{**base, "metric": "all_seeds_agree_share", "result": float(agree)},
                     {**base, "metric": "mean_abs_gap", "result": float(np.abs(g.mean(0)).mean())},
                     {**base, "metric": "pairs", "result": int(g.shape[1])}]
        for k, (f, n, _) in enumerate(fam):
            d1, d2 = G_fam[:, 0, k], G_fam[:, 1, k]
            base = row(commit, layout, a, b, d, log=f"mirror_{f}", test="direction", edit=f,
                       edit_size=n)
            rows += [{**base, "metric": "gap_mean", "result": float((d1 - d2).mean())},
                     {**base, "metric": "gap_min", "result": float((d1 - d2).min())},
                     {**base, "metric": "gap_max", "result": float((d1 - d2).max())},
                     {**base, "metric": "rel_gap", "result":
                      float((d1 - d2).mean() / ((d1.mean() + d2.mean()) / 2))}]
    return rows


# ---------------------------------------------------------------------------
# B  Real logs;  D  the universe
# ---------------------------------------------------------------------------

def ranks(X) -> np.ndarray:
    D = angular(X)
    return rankdata(D[np.triu_indices(len(D), 1)])


def rho(r1, r2) -> float:
    return float(np.corrcoef(r1, r2)[0, 1])


def both(base, edit, r1, r2) -> list[dict]:
    """Spearman's rank agreement and Kendall's tau-b of two rankings, as two rows."""
    return [{**base, "edit": edit, "result": rho(r1, r2)},
            {**base, "edit": edit, "metric": "rank_agreement_tau_b", "result": tau_b(r1, r2)}]


def agreement(commit, name, trees, betas, with_sign: bool) -> list[dict]:
    """Per seed: beta against -beta (each layout), shared against paired; and each seed
    against the next (the seed band), keeping only one previous ranking in memory."""
    labs = labels_of(trees)
    ranges = hrr_ranges(trees)
    rows = []
    for a, b, d in settings(betas):
        prev = {}
        for s in config.SEEDS:
            cur = {}
            for layout in LAYOUTS:
                enc = encoder(layout, d, s, ranges, labs)
                cur[layout] = ranks(vectors(enc, trees, a, b)).astype(np.float32)
                base = row(commit, layout, a, b, d, log=name, test="rank_agreement", seed=s,
                           metric="rank_agreement")
                if with_sign:
                    neg = ranks(vectors(enc, trees, a, -b)).astype(np.float32)
                    rows += both(base, "beta vs -beta", cur[layout], neg)
                    del neg
                if layout in prev:
                    rows += both(base, "vs next seed", prev[layout], cur[layout])
            rows += both(row(commit, "paired", a, b, d, log=name, test="rank_agreement", seed=s,
                             metric="rank_agreement"), "vs shared", cur["shared"], cur["paired"])
            prev = cur
    return rows


def part_b(commit, logs=config.LOGS) -> list[dict]:
    rows = []
    for key in logs:
        t0 = time.time()
        c = load_log(key)
        rows += agreement(commit, key, c.trees, betas=[x for x in G["beta"] if x > 0],
                          with_sign=True)
        print(f"B: {key} ({c.n:,} variants) {time.time() - t0:.0f}s", flush=True)
    return rows


def part_d(commit) -> list[dict]:
    rows = []
    for name, trees in U.corpora().items():
        rows += agreement(commit, name, list(trees), betas=G["beta"], with_sign=False)
    print("D: universe done", flush=True)
    return rows


# ---------------------------------------------------------------------------
# C  Kernels (seed-free)
# ---------------------------------------------------------------------------

def part_c(commit) -> list[dict]:
    shapes = [t for n in range(2, N_EXHAUSTIVE + 1) for t in probes.shapes(n)]
    moves = Counter()
    for t in shapes:
        for e in probes.single_edits(t):
            b = {a: (p, dd) for a, p, dd in tree_to_positioned_sequence(e.base)[0]}
            x = {a: (p, dd) for a, p, dd in tree_to_positioned_sequence(e.edited)[0]}
            for lab in b.keys() & x.keys():
                dp, dd = round(x[lab][0] - b[lab][0], 9), x[lab][1] - b[lab][1]
                if dp and dd:
                    moves[(dp, dd)] += 1
    shape_ranges = hrr_ranges(shapes)
    logs = {k: load_log(k) for k in config.LOGS}
    rows = []
    for layout, (a, b, d) in itertools.product(LAYOUTS, settings([x for x in G["beta"] if x > 0])):
        def kern(enc):
            return lambda dp, dd: float(np.mean(np.cos(dp * a * enc.thetas + dd * b * enc.depth_thetas)))
        K = kern(encoder(layout, d, config.DEFAULT_SEED, shape_ranges, []))
        base = row(commit, layout, a, b, d, log=f"shapes_2to{N_EXHAUSTIVE}", test="kernel")
        rows.append({**base, "edit": "flip beta (F5)", "metric": "max_gap",
                     "result": max(abs(K(dp, dd) - K(dp, -dd)) for dp, dd in moves)})
        less = [(dp, dd) for dp, dd in moves if K(dp, dd) > min(K(dp, 0), K(0, dd)) + 1e-9]
        rows.append({**base, "edit": "both moves look less moved", "metric": "moves",
                     "result": sum(moves[m] for m in less)})
        rows.append({**base, "edit": "both moves look less moved", "metric": "of_moves",
                     "result": sum(moves.values())})
        for key, c in logs.items():
            rg = hrr_ranges(c.trees)
            Kl = kern(encoder(layout, d, config.DEFAULT_SEED, rg, []))
            Ks = kern(encoder("shared", d, config.DEFAULT_SEED, rg, []))
            lb = row(commit, layout, a, b, d, log=key, test="kernel")
            dps = np.arange(0.25, c.max_leaves - 1 + 0.125, 0.25)
            rows.append({**lb, "edit": "position only", "metric": "max_diff_vs_shared",
                         "result": max(abs(Kl(x, 0) - Ks(x, 0)) for x in dps)})
            rows.append({**lb, "edit": "depth only", "metric": "max_diff_vs_shared",
                         "result": max(abs(Kl(0, x) - Ks(0, x)) for x in range(1, rg[1] // 4 + 1))})
    print(f"C: {len(moves)} distinct moves in both", flush=True)
    return rows


def _sm(v):
    """Mirror each 2-D block, then swap the two blocks of each pair."""
    w = v.copy()
    w[1::2] *= -1
    return w.reshape(-1, 2, 2)[:, ::-1, :].reshape(-1)


def part_e(commit) -> list[dict]:
    from scipy import stats
    rows = []
    for edit in ("joins", "nesting", "seq_to_par"):
        edits = [e for n in range(2, N_EXHAUSTIVE + 1) for t in probes.shapes(n)
                 for e in probes.single_edits(t) if e.edit == edit]
        trees, index = [], {}

        def add(t):
            k = canon(t)
            if k not in index:
                index[k] = len(trees)
                trees.append(t)
            return index[k]

        P = np.array([(add(e.base), add(e.edited), add(backwards(e.base)), add(backwards(e.edited)))
                      for e in edits])
        labs = labels_of(trees)
        worst = 0.0
        for s in config.SEEDS:
            e1 = encoder("paired", 512, s, hrr_ranges(trees), labs)
            e2 = encoder("paired", 512, s, hrr_ranges(trees), [])
            e2._label_table = {a: _sm(v) for a, v in e1._label_table.items()}
            X1, X2 = vectors(e1, trees, 1.0, 1.0), vectors(e2, trees, 1.0, 1.0)
            worst = max(worst, float(np.abs(pair_dist(X1, P[:, 2], P[:, 3])
                                            - pair_dist(X2, P[:, 0], P[:, 1])).max()))
        rows.append(row(commit, "paired", 1.0, 1.0, 512, log=f"shapes_2to{N_EXHAUSTIVE}",
                        test="direction", edit=edit, metric="backwards_identity_max_gap",
                        result=worst))
        for first in (42, 62, 82):
            seeds = range(first, first + 20)
            for layout, (a, d), b in itertools.product(LAYOUTS, ((1.0, 512), (1.0, 1024), (2.0, 512)),
                                                        (0.0, 1.0, 2.0)):
                Gs = np.array([pair_dist(X, P[:, 0], P[:, 1]) - pair_dist(X, P[:, 2], P[:, 3])
                               for X in (vectors(encoder(layout, d, s, hrr_ranges(trees), labs),
                                                 trees, a, b) for s in seeds)])
                p = stats.ttest_1samp(Gs, 0.0, axis=0).pvalue
                rows.append(row(commit, layout, a, b, d, log=f"shapes_2to{N_EXHAUSTIVE}",
                                test="direction", edit=edit, seed=f"{first}-{first + 19}",
                                metric="share_p_below_0.05", result=float(np.mean(p < 0.05))))
        print(f"E: {edit} done", flush=True)
    return rows


def main() -> None:
    parts = sys.argv[1:] or ["A", "B", "C", "D", "E"]
    commit = results.commit()
    for p in parts:
        t0 = time.time()
        if p.startswith("B:"):                      # e.g. B:domestic,sepsis (some logs)
            rows = part_b(commit, p.split(":", 1)[1].split(","))
        else:
            rows = {"A": part_a, "B": part_b, "C": part_c, "D": part_d, "E": part_e}[p](commit)
        results.write(rows)
        print(f"part {p}: {len(rows):,} rows, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
