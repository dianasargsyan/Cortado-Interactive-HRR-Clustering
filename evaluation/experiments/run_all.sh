#!/usr/bin/env bash
# Every experiment of the evaluation, one at a time, in the order below. Each one appends its
# rows to results/results.csv (set RESULTS_TABLE to write elsewhere).
#
#   bash evaluation/experiments/run_all.sh            the full run; the tree edit distance on the
#                                                      two largest logs takes the longest
#   QUICK=1 bash evaluation/experiments/run_all.sh    every experiment on a small input, as a check
#
# The variant caches in cache/variants/ are part of the repository; 03_cache_variants.py rebuilds
# them from the event logs in data/. The timed experiments (46, 43, 41 with --parts cost) should
# run while nothing else heavy runs on the machine.
#
# Log: results/run_<date>.log, with the time of every step and "FAILED" when a step fails; the run
# goes on with the next step.
set -u
PY=${PYTHON:-python}
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
mkdir -p results
STAMP=$(date +%Y%m%d_%H%M)
LOG="results/run_$STAMP.log"

step() {
  echo "=== $(date '+%F %T') $*" >> "$LOG"
  local start=$SECONDS
  "$@" >> "$LOG" 2>&1
  local code=$? took=$((SECONDS - start))
  if (( code != 0 )); then
    echo "FAILED (exit $code, ${took} s): $*" >> "$LOG"
  else
    echo "--- done in ${took} s" >> "$LOG"
  fi
  return 0
}
run() { step "$PY" "evaluation/experiments/$@"; }

METHODS=onehot,trigram,pqgram,binary_branch,apted,hrr

if [[ -n ${QUICK:-} ]]; then
  export RESULTS_TABLE="$ROOT/results/quick_$STAMP.csv"
  echo "=== results go to $RESULTS_TABLE" >> "$LOG"
  run 16_log_profile.py sepsis
  run 22_universe.py
  run 30_paths.py
  run 21_positions.py
  run 28_floors.py universe_4 length_12
  run 46_edit_latency.py domestic
  run 43_scaling.py --sizes 100
  run 43_scaling.py --sizes 100 --methods apted
  run 41_corpus_methods.py domestic --parts distances,cost
  run 41_corpus_methods.py domestic --methods apted --parts distances
  run 31_real_bases.py 1
  run 41_corpus_methods.py sepsis --methods apted --parts distances
  run 41_corpus_methods.py domestic --methods $METHODS --parts collisions,agreement
  run 41_corpus_methods.py domestic --methods $METHODS --parts neighbourhood
  run 42_capability_methods.py --kinds check
  run 42_capability_methods.py --kinds check --methods apted
  run 42_capability_methods.py --kinds lengths --only 12
  run 45_edit_checks.py domestic
  run 26_dimension_noise.py domestic
  run 27_kernels.py 8192 domestic
  run 27_kernels.py curves
  run 34_response.py domestic
  run 29_admissibility.py 8192 universe_5_AAAAB
  run 29_admissibility.py 8192 domestic
  run 25_paired_layout.py A C E B:domestic
  run 35_direction_final.py U A:6 C:domestic
  run 17_chaining_check.py domestic
else
  echo "=== results go to ${RESULTS_TABLE:-results/results.csv}" >> "$LOG"
  # the data and the exact checks
  run 16_log_profile.py
  run 22_universe.py
  run 30_paths.py
  run 21_positions.py
  run 28_floors.py
  # the timed experiments
  run 46_edit_latency.py
  run 43_scaling.py
  run 43_scaling.py --methods apted
  run 41_corpus_methods.py --parts distances,cost
  run 41_corpus_methods.py domestic sepsis permit bpic15_1 universe_4 --methods apted --parts distances
  run 31_real_bases.py
  run 41_corpus_methods.py bpi2012 bpi2017 --methods apted --parts distances
  # all pairs of a corpus and the modifications
  run 41_corpus_methods.py --methods $METHODS --parts collisions,agreement
  run 41_corpus_methods.py --methods $METHODS --parts neighbourhood
  run 42_capability_methods.py
  run 42_capability_methods.py --methods apted
  # the adjustments, the dimension and the weights
  run 45_edit_checks.py
  run 26_dimension_noise.py synthetic logs
  run 27_kernels.py
  run 27_kernels.py 8192 synthetic
  run 27_kernels.py curves
  run 34_response.py
  run 34_response.py synthetic
  run 29_admissibility.py
  run 29_admissibility.py 8192 synthetic logs
  run 25_paired_layout.py
  run 35_direction_final.py U A:6,9,12,15,20,30,45,65 C
  run 17_chaining_check.py
fi
echo "=== $(date '+%F %T') done; failed steps: $(grep -c '^FAILED' "$LOG")" >> "$LOG"
