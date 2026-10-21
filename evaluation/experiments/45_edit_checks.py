"""
Does each edit do what it says and only that, and is its effect visible?  Through evaluation/edited.py
at d = config.D, five seeds.

Corpora and settings: the universe at 2 to 4 activities at every setting of the grid; the six logs
at the four settings with each knob off or on.  Activities, by a fixed rule per corpus: among
those in some but not every variant, by the share of variants containing them, the most frequent
(A), the median (M) and the rarest (R) in at least two variants.

  edits    equivalence of (A, M) and of (M, R); ignoring A, M and R (each dropped); and the two
           edits together: equivalence of (M, R) with A ignored

Rows (test edit_checks; edit = the instance; knob alpha,beta,d; seed):

  locality   1 if every variant without the edited activities keeps its vector (to 1e-9)
  exact      equivalence, drop and the two together: 1 if the variants given the same vector are
             exactly those whose edited trees are the same (where the unedited corpus already has
             that property)
  effect     the mean change in distance of the pairs the edit is about (after minus before);
             visible: the share of those pairs that moved closer by more than the noise band;
             contrary: the share that moved apart by more than the band; effect_ok: 1 unless
             the mean moved apart by more than the band; before, after: their mean distances;
             pairs: how many (at most 20,000, sampled with the shared seed); not for the two
             together, which are checked by exact and locality only
  band       per corpus and setting: the noise band (95th percentile of the gap between
             consecutive seeds, over 20,000 sampled pairs)

The pairs an edit is about: for an equivalence, one variant with the first activity and not the
second, the other the reverse; for ignoring, pairs where exactly one variant contains the
activity.

    python evaluation/experiments/45_edit_checks.py                   # every corpus, rows written
    python evaluation/experiments/45_edit_checks.py --dry domestic    # print only
"""

from __future__ import annotations

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

from rotation_hrr.domain_knowledge import DomainKnowledge as DK  # noqa: E402
from evaluation import config, results, synthetic  # noqa: E402
from evaluation.edited import EditedLog  # noqa: E402
from rotation_hrr.tree_utils import tree_to_sequence  # noqa: E402
from rotation_hrr.tree_rewrites import drop_activities, relabel  # noqa: E402
from rotation_hrr.variant_enumeration import canon  # noqa: E402

CORPORA = ["universe_4", *config.LOGS]
N_PAIRS = 20_000
CHUNK = 2048
_PROJ = np.random.default_rng(0).standard_normal((1 << 15, 8))


class Inst:
    """One edit instance: its name, kind, activities and DomainKnowledge."""

    def __init__(self, name, kind, on, dk):
        self.name, self.kind, self.on, self.dk = name, kind, on, dk


def instances(acts) -> list[Inst]:
    A, M, R = acts
    out = [Inst(f"equivalence {x}|{y}", "equivalence", (x, y), DK(activity_equivalences={x: [y]}))
           for x, y in ((A, M), (M, R))]
    for x in (A, M, R):
        out.append(Inst(f"drop {x}", "drop", (x,), DK(ignored_activities={x})))
    out.append(Inst(f"together: equivalence {M}|{R} + drop {A}", "together", (A, M, R),
                    DK(activity_equivalences={M: [R]}, ignored_activities={A})))
    return out


def activities(trees):
    n = len(trees)
    share = Counter(a for t in trees for a in set(tree_to_sequence(t)))
    cand = sorted((c, a) for a, c in share.items() if 2 <= c < n)
    return None if len(cand) < 3 else (cand[-1][1], cand[len(cand) // 2][1], cand[0][1])


def target_pairs(trees, acts, rng):
    """The sampled pairs each kind of edit is about, and a sample for the noise band."""
    n = len(trees)
    labs = [set(tree_to_sequence(t)) for t in trees]

    def sample(I, J):
        I, J = np.asarray(I, dtype=int), np.asarray(J, dtype=int)
        if not len(I) or not len(J):
            return np.empty((0, 2), dtype=int)
        k = min(N_PAIRS, len(I) * len(J))
        p = np.stack([rng.choice(I, k), rng.choice(J, k)], axis=1)
        return np.unique(p[p[:, 0] != p[:, 1]], axis=0)

    out = {"band": sample(np.arange(n), np.arange(n))}
    for x in acts:
        out[("one", x)] = sample([i for i in range(n) if x in labs[i]], [i for i in range(n) if x not in labs[i]])
    for x, y in ((acts[0], acts[1]), (acts[1], acts[2])):
        out[("pair", x, y)] = sample([i for i in range(n) if x in labs[i] and y not in labs[i]],
                                     [i for i in range(n) if y in labs[i] and x not in labs[i]])
    return out


def unit(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.where(n < 1e-12, 1.0, n)


def pair_dist(Xn, P):
    """Angular distance of each pair, in blocks."""
    out = np.empty(len(P))
    for a in range(0, len(P), CHUNK):
        i, j = P[a:a + CHUNK, 0], P[a:a + CHUNK, 1]
        c = np.einsum("ij,ij->i", Xn[i], Xn[j])
        out[a:a + CHUNK] = np.arccos(np.clip(c, -1, 1)) / np.pi
    return out


def keys(Xn):
    """Which variants share a vector: 8 fixed projections to 9 decimals."""
    return [r.tobytes() for r in np.round(Xn @ _PROJ[:Xn.shape[1]], 9)]


def same_split(k1, k2) -> bool:
    return len(set(zip(k1, k2))) == len(set(k1)) == len(set(k2))


def target_key(kind, on):
    return ("pair", *on) if kind == "equivalence" else ("one", on[0])


def check_corpus(name, commit) -> list[dict]:
    t_start = time.time()
    C = synthetic.corpus(name)
    trees, n = C.trees, C.n
    acts = activities(trees)
    d = config.D
    settings = ([(a, b) for a in config.GRID["alpha"] for b in config.GRID["beta"]]
                if name.startswith("universe") else list(config.PHASE2_SETTINGS))
    print(f"{name}: {n} variants, d = {d}, activities {acts}", flush=True)
    if acts is None:
        return []
    P = target_pairs(trees, acts, config.rng_for(config.DEFAULT_SEED, "pairs"))
    labs = [set(tree_to_sequence(t)) for t in trees]
    base = EditedLog(trees, d=d)
    insts = instances(acts)
    E = {x.name: EditedLog(trees, x.dk, d=d, ranges=base.ranges) for x in insts}
    split_tree = {}                                   # the edited trees' split, for "exact"
    for x in insts:
        if x.kind == "drop":
            split_tree[x.name] = [(lambda u: "" if u is None else canon(u))(drop_activities(t, {x.on[0]}))
                                  for t in trees]
        elif x.kind == "equivalence":
            split_tree[x.name] = [canon(relabel(t, {x.on[1]: x.on[0]})) for t in trees]
        elif x.kind == "together":
            a, m, r = x.on
            split_tree[x.name] = [(lambda u: "" if u is None else canon(u))(drop_activities(relabel(t, {r: m}), {a}))
                                  for t in trees]
    split_base = [canon(t) for t in trees]
    print(f"  built {len(insts)} edits ({time.time() - t_start:.0f} s)", flush=True)

    rows = []
    for a, b in settings:
        value = f"{a:g},{b:g},{d}"
        # the noise band at this setting, from the unedited distances over the five seeds
        bd = [pair_dist(unit(base.vectors(a, b, s)), P["band"]) for s in config.SEEDS]
        band = float(np.percentile(np.abs(np.diff(np.stack(bd), axis=0)), 95))
        rows.append({"method": "hrr", "log": name, "test": "edit_checks", "edit": "noise band",
                     "knob": "alpha,beta,d", "value": value, "metric": "band", "result": band,
                     "commit": commit})
        for s in config.SEEDS:
            X0 = unit(base.vectors(a, b, s))
            k0 = keys(X0)
            for x in insts:
                X1 = unit(E[x.name].vectors(a, b, s))
                r = {"method": "hrr", "log": name, "test": "edit_checks", "edit": x.name,
                     "knob": "alpha,beta,d", "value": value, "seed": s, "commit": commit}
                u = np.array([not (set(x.on) & labs[i]) for i in range(n)])
                loc = bool(np.all(np.abs(X1[u] - X0[u]) <= 1e-9))
                rows.append({**r, "metric": "locality", "result": int(loc)})
                if x.name in split_tree and same_split(k0, split_base):
                    rows.append({**r, "metric": "exact",
                                 "result": int(same_split(keys(X1), split_tree[x.name]))})
                if x.kind == "together":
                    continue
                T = P[target_key(x.kind, x.on)]
                if not len(T):
                    continue
                d0, d1 = pair_dist(X0, T), pair_dist(X1, T)
                ch = d1 - d0
                m = float(ch.mean())
                rows += [{**r, "metric": k_, "result": v} for k_, v in (
                    ("effect", m), ("effect_ok", int(-m >= -band)), ("visible", float(np.mean(-ch > band))),
                    ("contrary", float(np.mean(ch > band))), ("before", float(d0.mean())),
                    ("after", float(d1.mean())), ("pairs", int(len(T))))]
        print(f"  {value}: done ({time.time() - t_start:.0f} s)", flush=True)
    return rows


def main() -> None:
    args = sys.argv[1:]
    dry = "--dry" in args
    names = [a for a in args if a != "--dry"] or CORPORA
    commit = results.commit()
    for name in names:
        rows = check_corpus(name, commit)
        v: dict = {}
        for row in rows:
            if row["metric"] in ("locality", "exact", "effect_ok"):
                v.setdefault((row["metric"]), []).append(row["result"])
        print("  " + "; ".join(f"{m} {sum(x)}/{len(x)}" for m, x in sorted(v.items())), flush=True)
        if not dry and rows:
            results.write(rows)


if __name__ == "__main__":
    main()
