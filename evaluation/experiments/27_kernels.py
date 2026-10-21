"""
How far can position and depth rotate before a larger move stops looking larger?

The kernel is the similarity of an activity's vector to itself moved by Delta positions (alpha)
or Delta depth levels (beta): per vector, the mean over blocks of cos(knob * Delta * theta_k),
weighted by how much of the vector sits in block k.  The seed-free kernel weights every block
equally; each drawn vector gives its own curve, whose spread is the seed noise.

For each knob value on a fine grid and each corpus, over Delta up to the largest move that occurs
in it (its longest variant for alpha, its deepest nesting for beta):

  stops_decreasing   the first Delta after which the kernel rises by more than the noise band (a
                     larger move looks closer)
  turns_negative     the first Delta at which the kernel is below minus the noise band
  admissible         1 if neither happens within the corpus's range, else 0

The noise band is the 95th percentile of |a drawn vector's kernel - the seed-free kernel| over
N_VECTORS vectors per seed and every seed.  Positions and depths use the encoder's own frequency
banks (ranges from the corpus, as evaluation.methods.hrr does).

With "curves": the seed-free kernel itself at knob = 1 and d = config.D, over every Delta of each
log, under the ranges from the corpus and under the earlier fixed rule (n_max = max(100, longest
variant), depth range 8), with the noise band at each Delta (test kernel_curve; edit = the
ranges, edit_size = Delta).

    python evaluation/experiments/27_kernels.py                 # d = config.D, on the six logs
    python evaluation/experiments/27_kernels.py 8192 synthetic  # on every synthetic corpus
    python evaluation/experiments/27_kernels.py curves
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation._env import require_cortado_env  # noqa: E402

require_cortado_env()

import numpy as np  # noqa: E402

from evaluation import config, results, synthetic  # noqa: E402
from evaluation.corpus import load_log  # noqa: E402
from evaluation.methods import hrr_ranges  # noqa: E402
from rotation_hrr.tree_utils import tree_to_positioned_sequence  # noqa: E402
from rotation_hrr.encoder import RotationHRREncoder  # noqa: E402

KNOB_GRID = np.round(np.arange(0.1, 4.01, 0.1), 2)
N_VECTORS = 200
STEP = 0.25                     # Delta grid for positions (positions are fractional)


def curves(enc, bank: np.ndarray, knob: float, deltas: np.ndarray, weights: np.ndarray):
    """(seed-free kernel, per-vector kernels) over deltas."""
    C = np.cos(np.outer(deltas, knob * bank))                  # deltas x blocks
    return C.mean(axis=1), weights @ C.T                        # (deltas,), (vectors, deltas)


def verdict(k0: np.ndarray, kv: np.ndarray, deltas: np.ndarray, band: float):
    run_min = np.minimum.accumulate(k0)
    rises = np.flatnonzero(k0 > run_min + band)
    neg = np.flatnonzero(k0 < -band)
    stop = float(deltas[rises[0]]) if len(rises) else float("nan")
    turn = float(deltas[neg[0]]) if len(neg) else float("nan")
    return stop, turn


OLD_N_MAX_FLOOR, OLD_DEPTH_RANGE = 100, 8          # the earlier fixed rule, for the curves


def weights(d, n_max, n_max_depth):
    W = []
    for s in config.SEEDS:
        enc = RotationHRREncoder(d=d, n_max=n_max, n_max_depth=n_max_depth, seed=s)
        V = np.stack([enc.get_label_vector(f"v{i}") for i in range(N_VECTORS)])
        w = V[:, 0::2] ** 2 + V[:, 1::2] ** 2
        W.append(w / w.sum(axis=1, keepdims=True))
    return enc, np.concatenate(W)


def curve_rows(commit) -> list[dict]:
    d, rows = config.D, []
    for key in config.LOGS:
        c = load_log(key)
        max_depth = max(max(dp for _, _, dp in tree_to_positioned_sequence(t)[0]) for t in c.trees)
        for label, (n_max, n_max_depth) in (("from the corpus", hrr_ranges(c.trees)),
                                            ("earlier rule", (max(OLD_N_MAX_FLOOR, c.max_leaves),
                                                              OLD_DEPTH_RANGE))):
            enc, W = weights(d, n_max, n_max_depth)
            for knob, bank_name, top in (("alpha", "thetas", c.max_leaves - 1),
                                         ("beta", "depth_thetas", max_depth)):
                deltas = np.arange(STEP, top + STEP / 2, STEP) if knob == "alpha" \
                    else np.arange(1, top + 1, dtype=float)
                k0, kv = curves(enc, getattr(enc, bank_name), 1.0, deltas, W)
                band = np.percentile(np.abs(kv - k0), 95, axis=0)
                base = {"method": "hrr", "log": key, "knob": f"{knob},d", "value": f"1,{d}",
                        "test": "kernel_curve", "edit": label, "commit": commit}
                for x, k, b in zip(deltas, k0, band):
                    rows += [{**base, "edit_size": float(x), "metric": "kernel", "result": float(k)},
                             {**base, "edit_size": float(x), "metric": "noise_band", "result": float(b)}]
        print(f"curves: {key}", flush=True)
    return rows


def main() -> None:
    if sys.argv[1:] == ["curves"]:
        rows = curve_rows(results.commit())
        results.write(rows)
        print(f"{len(rows)} rows")
        return
    args = sys.argv[1:]
    d = int(args.pop(0)) if args and args[0].isdigit() else config.HRR_DEFAULTS["d"]
    commit = results.commit()
    rows = []
    for key in synthetic.expand(args) or config.LOGS:
        c = synthetic.corpus(key)
        n_max, n_max_depth = hrr_ranges(c.trees)
        max_depth = max(max(dp for _, _, dp in tree_to_positioned_sequence(t)[0]) for t in c.trees)
        W = []
        for s in config.SEEDS:
            enc = RotationHRREncoder(d=d, n_max=n_max, n_max_depth=n_max_depth, seed=s)
            V = np.stack([enc.get_label_vector(f"v{i}") for i in range(N_VECTORS)])
            w = V[:, 0::2] ** 2 + V[:, 1::2] ** 2
            W.append(w / w.sum(axis=1, keepdims=True))
        W = np.concatenate(W)
        for knob, bank_name, top in (("alpha", "thetas", c.max_leaves - 1),
                                     ("beta", "depth_thetas", max_depth)):
            if top <= 0:
                continue
            deltas = np.arange(STEP, top + STEP / 2, STEP) if knob == "alpha" \
                else np.arange(1, top + 1, dtype=float)
            bank = getattr(enc, bank_name)
            for x in KNOB_GRID:
                k0, kv = curves(enc, bank, x, deltas, W)
                band = float(np.percentile(np.abs(kv - k0), 95))
                stop, turn = verdict(k0, kv, deltas, band)
                base = {"method": "hrr", "log": key, "knob": f"{knob},d", "value": f"{x:g},{d}",
                        "test": "kernel", "edit": f"{knob} range", "commit": commit}
                rows += [{**base, "metric": "max_delta", "result": float(deltas[-1])},
                         {**base, "metric": "noise_band", "result": band},
                         {**base, "metric": "stops_decreasing_at", "result": stop},
                         {**base, "metric": "turns_negative_at", "result": turn},
                         {**base, "metric": "admissible",
                          "result": int(np.isnan(stop) and np.isnan(turn))},
                         {**base, "metric": "kernel_at_max_delta", "result": float(k0[-1])}]
        print(f"{key}: longest variant {c.max_leaves}, deepest nesting {max_depth}", flush=True)
    results.write(rows)
    print(f"{len(rows)} rows")


if __name__ == "__main__":
    main()
