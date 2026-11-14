"""The nordcast figure helpers and the replay chart code path, on synthetic data (no database)."""

import itertools
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("matplotlib")
from nordcast import paper_style as ps
from nordcast.figure_utils import label_offsets

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs"))


def test_label_offsets_separate_labels_that_share_a_line_end():
    fig, axes = ps.figure()
    ax = axes[0][0]
    ax.plot(
        [0, 1], [0, 300]
    )  # no limits set yet: the helper must not read stale limits
    dys = label_offsets(ax, [27.0, 27.2, 26.5, 88.0], gap_pt=9)
    px = [
        ax.transData.transform((0, y))[1] * 72 / fig.dpi + dy
        for y, dy in zip([27.0, 27.2, 26.5, 88.0], dys, strict=True)
    ]
    px.sort()
    assert all(b - a >= 9 - 1e-6 for a, b in itertools.pairwise(px))
    assert label_offsets(ax, []) == []


def test_replay_charts_draw_three_valid_figures(tmp_path):
    replay_charts = pytest.importorskip("replay_charts")
    from nordcast import replay

    rng = np.random.default_rng(3)
    idx = pd.date_range("2025-01-01", periods=96 * 120, freq="15min", tz="UTC")
    y = pd.Series(rng.normal(-50, 150, len(idx)), index=idx)
    start = datetime(2025, 10, 1, tzinfo=replay.CPH)
    replay_charts.draw("2025q4", y, replay_charts.stats(y), start, tmp_path)
    for stem in ("acf", "profiles", "distribution"):
        for ext in ("pdf", "png", "tex"):
            assert (tmp_path / f"{stem}.{ext}").stat().st_size > 0
    assert "as of 2025-10-01" in (tmp_path / "acf.tex").read_text()
