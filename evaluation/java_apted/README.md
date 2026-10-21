# APTED, the authors' Java implementation

`src/` is the APTED source of Mateusz Pawlik and Nikolaus Augsten, copied unchanged from
https://github.com/DatabaseGroup/apted (commit `193666b`, 14 February 2018; MIT licence, `LICENSE`).

`AllPairs.java` computes the unit-cost tree edit distance between many trees in parallel: every
pair i < j, or a given list of pairs. `eval/baselines.py` writes the trees in bracket notation
(every label replaced by an id), compiles the classes into `build/` on first use (`javac`, JDK 11
or later) and runs it. Its distances equal the Python port's (the `apted` package) on every pair
compared (`tests/test_baselines.py`).
