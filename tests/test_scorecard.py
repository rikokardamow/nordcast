from datetime import UTC, datetime, timedelta

import pytest

from nordcast import scorecard

T0 = datetime(2026, 11, 2, 0, tzinfo=UTC)
ISP = timedelta(minutes=15)


def test_bootstrap_is_seeded_and_brackets_the_mean():
    daily = [1.0, 2.0, 3.0, 4.0, 5.0]
    mean, lo, hi = scorecard.bootstrap(daily)
    assert mean == 3.0 and lo < mean < hi
    assert scorecard.bootstrap(daily) == (mean, lo, hi)
    assert scorecard.bootstrap([]) is None


def test_a_missed_challenger_call_is_scored_as_persistence():
    bar = {T0: 10.0, T0 + ISP: 10.0}
    assert scorecard.skill(bar, {T0: 4.0})[0] == pytest.approx(3.0)  # (6 + 0) / 2


def test_lines_compare_each_method_with_the_bar():
    rows = []
    for k in range(8):
        isp = T0 + k * ISP
        rows += [
            (isp, 15, "model", "model", 10.0, 0.5, True, True),
            (isp, 15, "baseline", "persistence", 10.0, 0.5, True, True),
            (isp, 15, "challenger", "lightgbm_v1", 8.0, 0.4, k % 2 == 0, False),
        ]
    table = scorecard.lines(rows, {15: 10})
    by = {r["method"]: r for r in table}
    assert set(by) == {"headline", "lightgbm_v1 (challenger)"}
    assert by["headline"]["skill"][0] == 0
    assert by["lightgbm_v1 (challenger)"]["skill"][0] == pytest.approx(2.0)
    assert by["lightgbm_v1 (challenger)"]["direction_hit"] == 0.5
    assert by["headline"]["on_time"] == 0.8


def test_replace_swaps_only_the_marked_block():
    readme = f"top\n{scorecard.START}\nold\n{scorecard.END}\nbottom\n"
    out = scorecard.replace(readme, scorecard.markdown([]))
    assert out.startswith("top\n") and out.endswith("bottom\n")
    assert "no scored calls yet" in out and "old" not in out
    with pytest.raises(ValueError):
        scorecard.replace("no markers", "x")
