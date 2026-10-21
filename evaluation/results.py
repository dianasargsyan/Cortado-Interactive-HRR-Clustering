"""
The one results table.  Every script writes to it; every figure and table reads from it.

Columns (fixed; a row with any other column is refused):

  method      registered method name ("hrr", "onehot", ...)
  log         corpus name: a log key, or the name of a constructed set
  seed        encoder seed; empty for methods without randomness
  algorithm   clustering algorithm, if any
  k           number of clusters, if any
  knob        the knob(s) set, comma-separated ("alpha,beta,d"), or "defaults"
  value       their values in the same order ("0.5,0,8192")
  test        which experiment the row belongs to
  edit        the edit a probe applies, or the comparison a row belongs to
  edit_size   how big that edit is
  metric      what was measured
  result      the number
  commit      the git commit the row was computed at; "+dirty" if the code or the variant
              caches had uncommitted changes

The first eleven columns identify a row.  Rows are appended; when the table is read, a row
replaces any earlier row with the same identity, so re-running an experiment updates its rows.

Thesis numbers come from one commit: ``check_final`` refuses a table whose rows come from more
than one commit, from uncommitted code, or from a commit whose code has changed since.
"""

from __future__ import annotations

import csv
import fcntl
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from evaluation import config

COLUMNS: tuple[str, ...] = ("method", "log", "seed", "algorithm", "k", "knob", "value",
                            "test", "edit", "edit_size", "metric", "result", "commit")
KEY: list[str] = list(COLUMNS[:-2])

# What a number can depend on: the code that computes it (Python, and the Java APTED) and the
# variant caches.  The tests and the files the experiments write do not make a row "dirty".
CODE_PATHS: tuple[str, ...] = (":(glob)evaluation/*.py", ":(glob)evaluation/experiments/*.py", ":(glob)rotation_hrr/**/*.py",
                               ":(glob)evaluation/java_apted/**/*.java", ":(glob)cache/variants/variants_*.pkl")


def complete(row: dict) -> dict:
    """The row with every column present (missing ones empty); unknown columns refused."""
    unknown = set(row) - set(COLUMNS)
    if unknown:
        raise ValueError(f"not a results-table column: {sorted(unknown)}")
    return {c: "" if row.get(c) is None else row.get(c, "") for c in COLUMNS}


@contextmanager
def _locked(path: Path):
    """One writer at a time."""
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def write(rows: list[dict], path: Path | None = None) -> Path:
    """Append *rows* to the table (under a lock; the header if the table is new)."""
    path = path or config.RESULTS
    new = [{c: str(v) for c, v in complete(r).items()} for r in rows]
    with _locked(path):
        fresh = not path.exists() or path.stat().st_size == 0
        with open(path, "a", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS)
            if fresh:
                w.writeheader()
            w.writerows(new)
    return path


def read(path: Path | None = None, keep: Callable | None = None, chunksize: int = 200_000):
    """The table as a DataFrame, each row identity once (its last version).  *keep* filters each
    chunk as it is read (a function of a DataFrame of strings, returning the rows to keep), so a
    large table need not fit in memory.  Columns whose values are all numbers are numeric, empty
    cells are NaN; ``result`` is always numeric (NaN where a metric is undefined)."""
    import pandas as pd
    chunks = pd.read_csv(path or config.RESULTS, dtype=str, keep_default_na=False,
                         chunksize=chunksize)
    parts = [keep(c) if keep else c for c in chunks]
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=list(COLUMNS))
    df = df.drop_duplicates(subset=KEY, keep="last").reset_index(drop=True)
    for c in df.columns:
        s = df[c].mask(df[c] == "")
        if c == "result":
            df[c] = pd.to_numeric(s, errors="coerce")
            continue
        num = pd.to_numeric(s, errors="coerce")
        df[c] = num if num.notna().sum() == s.notna().sum() else s
    return df


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def commit() -> str:
    """Short hash of HEAD, with "+dirty" if the code or the variant caches are uncommitted."""
    try:
        head = _git("rev-parse", "--short", "HEAD")
        return head + ("+dirty" if _git("status", "--porcelain", "--", *CODE_PATHS) else "")
    except (OSError, subprocess.CalledProcessError):
        return ""


def check_final(df) -> str:
    """The one commit every row comes from; raises if the rows could be mixed: rows from more
    than one commit, rows computed with uncommitted code, or rows whose commit's code differs
    from the code checked out now.  The fix in every case: commit, re-run everything, draw
    again."""
    commits = sorted(set(df["commit"].astype(str)))
    if len(commits) != 1:
        raise ValueError(f"rows come from {len(commits)} commits {commits}; re-run everything "
                         "at one commit")
    (c,) = commits
    if not c or c.endswith("+dirty"):
        raise ValueError(f"rows were computed with uncommitted code ({c or 'no commit'})")
    try:
        changed = _git("diff", "--name-only", c, "--", *CODE_PATHS)
        changed += _git("status", "--porcelain", "--", *CODE_PATHS)
    except (OSError, subprocess.CalledProcessError) as e:
        raise ValueError(f"cannot compare commit {c} with the checked-out code") from e
    if changed:
        raise ValueError(f"code has changed since {c}, so its rows may be stale:\n{changed}")
    return c
