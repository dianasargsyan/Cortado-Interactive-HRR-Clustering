"""
Does HRR score a pair differently for pointing one way in time or the other?  One protocol on the
final encoder (paired banks, ranges from the corpus, d = config.D).

  U  the universe           every pair of the universe (2 to 4 activities) against the same pair
                            read backwards (the universe holds every variant read backwards)
  A  pairs read backwards   d(base, edited) against d(both read backwards), per seed, on the
                            synthetic dataset (evaluation/probe_sets.py): every edit that keeps the
                            length, at its smallest size and at every place, and the first and
                            last step of every same-length path; one layer per length and repeat
                            version (6, 9, 12 to 65), and the real bases of each log; from 12 on
                            at the kept places and sizes (evaluation/probes.py)
  F  fresh seeds            on the real bases of BPI 2012, BPI 2017 and Sepsis (part A's pairs),
                            per pair a t-test of the mean gap over 20 seeds against 0, on three
                            independent sets of 20 seeds (42-61, 62-81, 82-101); the share of
                            pairs with p < 0.05 (about 0.05 if the gaps are chance), each setting
                            next to beta = 0
  C  real logs              per log: rank agreement (Spearman and Kendall's tau-b) of all
                            distances at beta against -beta (same seed), and PAM clusterings at
                            k in config.K (adjusted Rand index), each next to the same between
                            two seeds

A pair counts as scored by direction only if all five seeds agree on the sign of its gap.
beta = 0 is the control on the same pairs and seeds.  Settings: alpha in {0.5, 1} at beta = 1,
and beta = 0.5 at alpha = 1, each with its control.  Rows: test direction_final.

    python evaluation/experiments/35_direction_final.py            # U, A and C
    python evaluation/experiments/35_direction_final.py A:6,12,real    # part A on some lengths, or the real bases
    python evaluation/experiments/35_direction_final.py F          # the fresh-seed check on real variants
    python evaluation/experiments/35_direction_final.py C:domestic F:sepsis   # parts C and F on some logs
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

import numpy as np  # noqa: E402
from scipy.stats import rankdata  # noqa: E402
from sklearn.metrics import adjusted_rand_score  # noqa: E402

from evaluation.clustering import kmedoids_cluster  # noqa: E402
from evaluation import config, probe_sets, probes, results, synthetic  # noqa: E402
from evaluation.agreement import tau_b  # noqa: E402
from evaluation.batch_hrr import Batch, pair_distances  # noqa: E402
from evaluation.corpus import load_log  # noqa: E402
from evaluation.methods import hrr_ranges, represent  # noqa: E402
from evaluation.orders import backwards  # noqa: E402
from rotation_hrr.encoder import RotationHRREncoder  # noqa: E402
from rotation_hrr.tree_utils import tree_to_sequence  # noqa: E402
from rotation_hrr.variant_enumeration import canon, n_leaves  # noqa: E402

D = config.D
SETTINGS = [(0.5, 1.0), (1.0, 1.0), (1.0, 0.5)]
SAME_LENGTH = ("move", "relabel", "seq_to_par", "joins", "nesting", "alongside")


SMALLEST = {"move": 1, "seq_to_par": 2, "nesting": 2, "alongside": 2}   # others: every size is one step


def _probes_of(t, out, thin=False):
    """Every edit that keeps the length at its smallest size and at every place (the kept places
    with *thin*, evaluation/probes.py), and the first and last step of every same-length path (every
    probe is then seen under every encoder seed): added to *out*, edit -> [(base, edited), ...]."""
    for e in probes.single_edits(t, smallest=True, thin=thin):
        if e.edit in SAME_LENGTH and e.size == SMALLEST.get(e.edit, e.size):
            out.setdefault(e.edit, []).append((e.base, e.edited))
    for (edit, _, _), steps in probes.paths_on(t, thin).items():
        if edit in SAME_LENGTH and steps:
            for e in {steps[0].size: steps[0], steps[-1].size: steps[-1]}.values():
                out.setdefault(edit, []).append((e.base, e.edited))


def layer_pairs(only=None, logs=config.LOGS):
    """Part A's pairs one layer at a time, so only one layer is held in memory: (layer,
    edit -> [(base, edited), ...], extra trees for the ranges).  One layer per dataset length
    and repeat version (only the lengths in *only*, if given), then one per log (real bases)."""
    for n in probe_sets.LENGTHS:
        if only is not None and n not in only:
            continue
        by_version: dict = {}
        for g, t in probe_sets.with_groups(n):
            by_version.setdefault(g.rsplit(", ", 1)[1], []).append(t)
        for v, bases in by_version.items():
            out: dict = {}
            for t in bases:
                _probes_of(t, out, probe_sets.thinned(n))
            yield f"length {n}, {v}", out, []
    for key in logs:
        c = load_log(key)
        lengths = np.array([len(tree_to_sequence(t)) for t in c.trees])
        out = {}
        for n, idx in probe_sets.real(lengths).items():
            for i in idx:
                _probes_of(c.trees[i], out, probe_sets.thinned(n))
        yield f"real {key}", out, c.trees          # real bases use their log's ranges


def pair_sets(lengths=True, logs=config.LOGS):
    """(layer, edit) -> list of (base, edited) pairs, and layer -> extra trees for the ranges
    (every layer of layer_pairs at once)."""
    out, extra = {}, {}
    for layer, sets, ex in layer_pairs(None if lengths else set(), logs):
        out.update({(layer, e): v for e, v in sets.items()})
        if len(ex):
            extra[layer] = ex
    return out, extra


def part_u(commit):
    """Every pair of the universe against the same pair read backwards, per seed; the share of
    pairs all five seeds score by direction, overall and for pairs of the same and of different
    lengths."""
    trees = synthetic.load("universe_4").trees
    index = {canon(t): i for i, t in enumerate(trees)}
    rev = np.array([index[canon(backwards(t))] for t in trees])
    iu, ju = np.triu_indices(len(trees), 1)
    same = np.array([n_leaves(t) for t in trees])
    same = same[iu] == same[ju]
    rg = hrr_ranges(trees)
    batch = Batch(trees)
    rows = []
    for a, b in SETTINGS:
        for beta in (b, 0.0):
            G = []
            for s_ in config.SEEDS:
                enc = RotationHRREncoder(d=D, n_max=rg[0], n_max_depth=rg[1], seed=s_)
                X = batch.vectors(enc, a, beta)
                X /= np.linalg.norm(X, axis=1, keepdims=True)
                Dm = np.arccos(np.clip(X @ X.T, -1, 1)) / np.pi
                G.append(Dm[iu, ju] - Dm[rev[iu], rev[ju]])
                del X, Dm
            G = np.stack(G)                                                   # (seeds, pairs)
            agree = np.all(G > 1e-9, axis=0) | np.all(G < -1e-9, axis=0)
            base = {"method": "hrr", "log": "universe_4", "knob": "alpha,beta,d",
                    "value": f"{a:g},{beta:g},{D}", "test": "direction_final", "commit": commit}
            for lab, sel in (("all pairs", slice(None)), ("same length", same), ("different length", ~same)):
                rows += [{**base, "edit": lab, "metric": "all_seeds_agree_share", "result": float(agree[sel].mean())},
                         {**base, "edit": lab, "metric": "mean_abs_gap", "result": float(np.abs(G[:, sel].mean(0)).mean())},
                         {**base, "edit": lab, "metric": "pairs", "result": int(np.asarray(agree[sel]).size)}]
            del G
    print("U done", flush=True)
    return rows


def part_a(commit, only=None, logs=config.LOGS):
    """Each layer is its own corpus with its own frequency ranges; real bases add their
    log's variants to the ranges.  Distances from evaluation.batch_hrr (equal to encode_tree).  Rows
    are written layer by layer, so a stopped run keeps the layers it finished; *only* keeps those
    dataset lengths, *logs* those logs' real bases."""
    settings = list(dict.fromkeys(s for a, b in SETTINGS for s in ((a, b), (a, 0.0))))
    for layer, sets, extra in layer_pairs(only, logs):
        t0 = time.time()
        pairs, spans = [], {}
        for e, v in sets.items():
            lo = len(pairs)
            for a, b in v:
                pairs += [(a, b), (backwards(a), backwards(b))]
            spans[e] = (lo, len(pairs))
        trees = [t for p in pairs for t in p] + list(extra)
        dist = pair_distances(pairs, hrr_ranges(trees), settings, config.SEEDS, D)
        rows = []
        for a, b in SETTINGS:
            for beta in (b, 0.0):
                ki = settings.index((a, beta))
                for e, (lo, hi) in spans.items():
                    g = (dist[lo:hi:2, :, ki] - dist[lo + 1:hi:2, :, ki]).T      # (seeds, pairs)
                    agree = np.all(g > 1e-12, axis=0) | np.all(g < -1e-12, axis=0)
                    base = {"method": "hrr", "log": layer, "knob": "alpha,beta,d",
                            "value": f"{a:g},{beta:g},{D}", "test": "direction_final", "edit": e,
                            "commit": commit}
                    rows += [{**base, "metric": "all_seeds_agree_share", "result": float(agree.mean())},
                             {**base, "metric": "mean_abs_gap", "result": float(np.abs(g.mean(0)).mean())},
                             {**base, "metric": "pairs", "result": int(g.shape[1])}]
        results.write(rows)
        print(f"A: {layer} ({len(pairs):,} pairs, {time.time() - t0:.0f}s) done", flush=True)
        del dist, pairs, trees
    return []


F_LOGS = ("bpi2012", "bpi2017", "sepsis")
F_SEED_SETS = (42, 62, 82)


def part_f(commit, logs=F_LOGS):
    """Fresh seeds on the real variants where part A saw shares above the control: per
    pair, a t-test of the mean forward-minus-backward gap over 20 seeds against 0, on three
    independent seed sets.  If the excess is chance, about 5% of pairs have p < 0.05, at beta > 0
    as at beta = 0."""
    from scipy import stats
    sets, extra = pair_sets(lengths=False, logs=logs)
    settings = list(dict.fromkeys(s for a, b in SETTINGS for s in ((a, b), (a, 0.0))))
    rows = []
    for key in logs:
        layer = f"real {key}"
        keys = [k for k in sets if k[0] == layer]
        pairs, spans = [], {}
        for k in keys:
            lo = len(pairs)
            for a, b in sets[k]:
                pairs += [(a, b), (backwards(a), backwards(b))]
            spans[k] = (lo, len(pairs))
        trees = [t for p_ in pairs for t in p_] + list(extra[layer])
        rg = hrr_ranges(trees)
        for first in F_SEED_SETS:
            t0 = time.time()
            seeds = list(range(first, first + 20))
            dist = pair_distances(pairs, rg, settings, seeds, D)          # (pairs, seeds, settings)
            for (a, beta) in settings:
                ki = settings.index((a, beta))
                for k in keys:
                    lo, hi = spans[k]
                    g = dist[lo:hi:2, :, ki] - dist[lo + 1:hi:2, :, ki]      # (pairs, seeds)
                    live = np.abs(g).max(axis=1) > 1e-12                    # pairs that read the same both ways drop out
                    pv = stats.ttest_1samp(g[live], 0.0, axis=1).pvalue if live.any() else np.array([])
                    base = {"method": "hrr", "log": layer, "knob": "alpha,beta,d",
                            "value": f"{a:g},{beta:g},{D}", "test": "direction_final", "edit": k[1],
                            "seed": f"{first}-{first + 19}", "commit": commit}
                    rows += [{**base, "metric": "share_p_below_0.05",
                              "result": float(np.mean(pv < 0.05)) if pv.size else float("nan")},
                             {**base, "metric": "pairs", "result": int(live.sum())}]
            del dist
            print(f"F: {layer}, seeds {first}-{first + 19} ({time.time() - t0:.0f}s)", flush=True)
    return rows


def part_c(commit, logs=config.LOGS):
    rows = []
    for key in logs:
        t0 = time.time()
        c = load_log(key)
        for a, b in SETTINGS[:2]:
            prev = None
            for s in config.SEEDS:
                Dp = represent("hrr", c, s, use_cache=False, alpha=a, beta=b, d=D).distances
                Dn = represent("hrr", c, s, use_cache=False, outside_range=True, alpha=a, beta=-b,
                               d=D).distances
                iu = np.triu_indices(len(Dp), 1)
                rp, rn = rankdata(Dp[iu]), rankdata(Dn[iu])
                base = {"method": "hrr", "log": key, "seed": s, "knob": "alpha,beta,d",
                        "value": f"{a:g},{b:g},{D}", "test": "direction_final", "commit": commit}
                rows += [{**base, "edit": "beta vs -beta", "metric": "rank_agreement",
                          "result": float(np.corrcoef(rp, rn)[0, 1])},
                         {**base, "edit": "beta vs -beta", "metric": "rank_agreement_tau_b",
                          "result": tau_b(rp, rn)}]
                labs = {}
                for k in config.K:
                    lp, ln_ = kmedoids_cluster(Dp, k)[1], kmedoids_cluster(Dn, k)[1]
                    labs[k] = lp
                    rows.append({**base, "k": k, "algorithm": "pam", "edit": "beta vs -beta",
                                 "metric": "ari", "result": float(adjusted_rand_score(lp, ln_))})
                if prev is not None:
                    rows += [{**base, "edit": "vs next seed", "metric": "rank_agreement",
                              "result": float(np.corrcoef(prev[0], rp)[0, 1])},
                             {**base, "edit": "vs next seed", "metric": "rank_agreement_tau_b",
                              "result": tau_b(prev[0], rp)}]
                    for k in config.K:
                        rows.append({**base, "k": k, "algorithm": "pam", "edit": "vs next seed",
                                     "metric": "ari", "result": float(adjusted_rand_score(prev[1][k], labs[k]))})
                prev = (rp, labs)
                del Dp, Dn, rn
        print(f"C: {key} ({time.time() - t0:.0f}s)", flush=True)
    return rows


def main() -> None:
    parts = sys.argv[1:] or ["U", "A", "C"]
    commit = results.commit()
    for p in parts:
        if p.startswith("A:"):                      # e.g. A:6,12,real (some lengths, or the real bases)
            sel = p.split(":", 1)[1].split(",")
            part_a(commit, {int(x) for x in sel if x != "real"}, config.LOGS if "real" in sel else ())
            print(f"part {p}: done", flush=True)
            continue
        if p.startswith(("C:", "F:")):              # e.g. C:domestic (some logs)
            rows = {"C": part_c, "F": part_f}[p[0]](commit, p.split(":", 1)[1].split(","))
        else:
            rows = {"U": part_u, "A": part_a, "C": part_c, "F": part_f}[p](commit)
        if rows:
            results.write(rows)
        print(f"part {p}: {len(rows):,} rows", flush=True)


if __name__ == "__main__":
    main()
