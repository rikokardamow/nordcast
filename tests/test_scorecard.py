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


def test_readme_block_keeps_the_full_table_behind_the_short_one():
    block = scorecard.readme_block([])
    assert block.index("no scored calls yet") < block.index("<details>")
    assert "Brier vs climatology" in block
    readme = f"a\n{scorecard.START}\nold\n{scorecard.END}\nb\n"
    assert "</details>" in scorecard.replace(readme, block)


def test_brier_against_persistence_and_climatology():
    rows = []
    for k in range(8):
        isp = T0 + k * ISP
        rows += [
            (isp, 15, "model", "model", 10.0, 1.0, True, True),
            (isp, 15, "baseline", "persistence", 10.0, 1.0, True, True),
            (isp, 15, "baseline", "direction_climatology", None, 0.6, False, None),
            (isp, 15, "challenger", "lightgbm_v1", 9.0, 0.55, True, True),
        ]
    table = scorecard.lines(rows, {15: 8})
    assert {r["method"] for r in table} == {"headline", "lightgbm_v1 (challenger)"}
    (c,) = [r for r in table if r["method"] == "lightgbm_v1 (challenger)"]
    assert c["brier_vs_persistence"][0] == pytest.approx(0.45)
    assert c["brier_vs_climatology"][0] == pytest.approx(0.05)
    assert "+0.050" in scorecard.markdown(table)


def test_a_missed_call_takes_persistence_against_climatology_too():
    pers = {T0: 1.0, T0 + ISP: 1.0}
    clim = {T0: 0.6, T0 + ISP: 0.6}
    # one call made (0.5), one missed: filled with persistence's 1.0, not clim's
    got = scorecard.skill(clim, {T0: 0.5}, fill=pers)
    assert got[0] == pytest.approx((0.1 - 0.4) / 2)
