"""
The rule for the vector length d: the smallest d at which every corpus's distances are stable
across seeds at every setting of config.GRID.  Stable means, at the worst setting (mean over
consecutive seed pairs): two seeds rank all pairs alike (Spearman at least 0.99), keep each
variant's 10 nearest (at least 0.9), and agree with d = 32768 (at least 0.99).  Two cells are
left out: the rank checks at alpha = beta = 0 on the synthetic corpora (most distances are 0
there) and the neighbour check at alpha = 0.  Read from the results table's dimension_grid rows.
``d_by_rule`` gives what each corpus needs, ``fixed_d`` the largest over the corpora, which is
config.D.
"""

from __future__ import annotations

import pandas as pd

from evaluation import config

RULE = {"seeds": 0.99, "neighbours": 0.9, "reference": 0.99}


def newest(df: pd.DataFrame, order: list[str] | None = None) -> pd.DataFrame:
    """Per corpus, only the rows of its newest commit (*order*, newest first; by default the
    order the commits appear in the table, last written last)."""
    keep = []
    for _, g in df.groupby("log"):
        commits = order or list(dict.fromkeys(g["commit"].astype(str)[::-1]))
        for c in commits:
            if (g["commit"].astype(str) == c).any():
                keep.append(g[g["commit"].astype(str) == c])
                break
    return pd.concat(keep) if keep else df.iloc[:0]


def d_summary(Dg: pd.DataFrame) -> pd.DataFrame:
    """Per corpus and d: the worst setting's seed agreement, agreement with d = 32768 and
    neighbours kept, and the largest noise band."""
    x = Dg.copy()
    v = x["value"].astype(str).str.split(",", expand=True)
    x["a"], x["b"], x["d"] = v[0].astype(float), v[1].astype(float), v[2].astype(int)
    x["result"] = pd.to_numeric(x["result"], errors="coerce")
    x = x[x["d"] < 32768]
    syn = x["log"].astype(str).str.startswith(("length_", "universe"))
    rank_ok = ~(syn & (x["a"] == 0) & (x["b"] == 0))
    out = {}
    for name, sel in (("seeds", (x["edit"] == "vs next seed") & (x["metric"] == "rank_agreement") & rank_ok),
                      ("reference", (x["edit"] == "vs reference") & (x["metric"] == "rank_agreement") & rank_ok),
                      ("neighbours", (x["edit"] == "vs next seed") & (x["metric"] == "neighbour_overlap") & (x["a"] > 0)),
                      ("band", (x["edit"] == "vs next seed") & (x["metric"] == "noise_band_p95") & rank_ok)):
        per = x[sel].groupby(["log", "d", "a", "b"])["result"].mean()
        out[name] = per.groupby(["log", "d"]).max() if name == "band" else per.groupby(["log", "d"]).min()
    return pd.DataFrame(out)


def smallest_d(S: pd.DataFrame, floor: int = 0) -> pd.Series:
    """Per corpus, the smallest d meeting the rule, at least *floor*.  A check not run on a
    corpus (neighbours on the universe, where ties decide the 10 nearest) is not applied."""
    ok = (S["seeds"] >= RULE["seeds"]) & (S["neighbours"].isna() | (S["neighbours"] >= RULE["neighbours"])) & \
         (S["reference"] >= RULE["reference"])
    ok = ok[ok].reset_index()
    ok = ok[ok["d"] >= floor]
    return ok.groupby("log")["d"].min()


def on_grid(rows: pd.DataFrame) -> pd.DataFrame:
    """Only the rows at a setting of config.GRID."""
    v = rows["value"].astype(str).str.split(",", expand=True)
    a, b = v[0].astype(float), v[1].astype(float)
    return rows[a.isin(config.GRID["alpha"]) & b.isin(config.GRID["beta"])]


def d_by_rule(R: pd.DataFrame) -> dict[str, int]:
    """Per corpus, the smallest d meeting the rule on config.GRID.  A corpus with no such d is
    left out."""
    rows = on_grid(newest(R[R["test"] == "dimension_grid"]))
    return {k: int(v) for k, v in smallest_d(d_summary(rows)).items()}


def fixed_d(R: pd.DataFrame, corpora=None) -> int:
    """The one d for every corpus: the largest of what the corpora need (config.CORPORA by
    default).  Fails if a corpus meets the rule at no d tested."""
    corpora = list(corpora or config.CORPORA)
    need = d_by_rule(R)
    missing = [c for c in corpora if c not in need]
    if missing:
        raise ValueError(f"no d meets the rule on {missing}")
    return max(need[c] for c in corpora)


__all__ = ["RULE", "d_by_rule", "d_summary", "fixed_d", "newest", "on_grid", "smallest_d"]
