"""config.D is the rule of evaluation/d_rule.py applied to the dimension_grid rows: the d the hardest corpus
needs."""

import pytest

from evaluation import config


def test_the_fixed_d_is_the_rule():
    from evaluation import results
    from evaluation.d_rule import d_by_rule, fixed_d
    if not config.RESULTS.exists():
        pytest.skip("no results table")
    R = results.read()
    if not (R["test"] == "dimension_grid").any():
        pytest.skip("no dimension_grid rows")
    assert fixed_d(R) == config.D
    need = d_by_rule(R)
    assert all(need[c] <= config.D for c in config.CORPORA)


def test_every_corpus_runs_at_the_one_d():
    assert config.HRR_DEFAULTS["d"] == config.D and config.GRID["d"] == (config.D,)
