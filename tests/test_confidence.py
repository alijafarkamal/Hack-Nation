import pytest

from src.utils.confidence import completeness_penalty, wilson_score_interval, wilson_w_interval


def test_wilson_interval_bounds():
    p, lo, hi = wilson_score_interval(1, 10)
    assert 0.0 <= lo <= p <= hi <= 1.0


def test_wilson_w_interval_has_notes():
    w = wilson_w_interval(2, 4)
    assert w.n == 4 and w.k == 2
    assert 0 <= w.point <= 1


def test_completeness_penalty_in_range():
    p = completeness_penalty(False, False, False, 0)
    assert 0.4 <= p <= 1.0


def test_wilson_n_zero():
    p, lo, hi = wilson_score_interval(0, 0)
    assert p == 0.0 and lo == 0.0 and hi == 0.0
