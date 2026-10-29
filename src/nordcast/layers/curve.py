"""Futures curve structure: roll-adjusted nearby ranks, time spreads, convexity, and a
six-state curve-regime classifier. Never touches DuckDB (root NOTES.md rule) -- callers
(pipelines/derived/curve.py) read the lake, call these pure functions, and write the
results back. Every input is a wide DataFrame (index=date, columns=contract code or rank
label) -- see nearby_panel's own docstring for how contract_panel/expiries are built.

Business-day arithmetic is plain Mon-Fri (numpy.busday_offset), not a real CME/ICE holiday
calendar -- confirmed with the user before this session: core/calendars.py has no
business-day helper at all today, and there is no real settlement data yet to need
holiday-exact roll dates against. Revisit once real data demands more precision.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from nordcast.layers.calendars import roll_calendar

# CME/ICE's own fixed, standardised delivery-month letter codes -- a contract code like
# "z26" IS the December 2026 contract by construction, not something to look up or guess.
CME_MONTH_CODES: dict[str, int] = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}

# Regime state -> small int, for the lake (`derived.curve.<root>.regime`). A fixed, static
# enum -- not per-contract data, so it lives here as a plain constant rather than in
# pipelines/futures/series_meta.py's per-contract schema (see this session's own NOTES.md
# note for why that table doesn't fit). Import this dict to decode a stored code; don't
# guess the mapping. "flat" (6) is a real seventh value this module adds for the s12==0
# knife-edge the spec's own six named states don't cover.
REGIME_CODES: dict[str, int] = {
    "super_contango": 0,
    "super_backwardation": 1,
    "convex_contango": 2,
    "concave_contango": 3,
    "convex_backwardation": 4,
    "concave_backwardation": 5,
    "flat": 6,
}

_RANK_COLUMN = "f{:02d}"


def _rank_col(i: int) -> str:
    return _RANK_COLUMN.format(i)


def _business_days_before(expiry: pd.Timestamp, n: int) -> pd.Timestamp:
    """expiry minus n Mon-Fri business days. A non-business-day expiry is first rolled
    back to the preceding business day (roll="backward"), then n days are subtracted."""
    return pd.Timestamp(np.busday_offset(expiry.date(), -n, roll="backward"))


def nearby_panel(
    contract_panel: pd.DataFrame,
    expiries: pd.Series,
    roll_days_before_expiry: int = 5,
    adjust: str = "ratio",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """`contract_panel`: wide, index=date, one column per contract code, values=settle
    price. `expiries`: index=contract code, value=expiry date (pipelines/futures/
    series_meta.py's own `expiry` column, one row per contract).

    Ranking rule: for date d, a contract "retires" from the curve entirely (not just
    demoted a rank) the business day its own roll_date = expiry - roll_days_before_expiry
    arrives -- valid_contracts(d) = every contract with d < roll_date(c), sorted by expiry
    ascending; f0i on date d is the i-th (1-indexed) element of valid_contracts(d). This
    means a contract's own rank naturally decreases (f03->f02->f01) as earlier contracts
    roll off, and it disappears from every rank once its own roll date passes.

    Returns (adjusted, unadjusted, roll_dates): `unadjusted` columns f01..fn hold raw
    prices (genuinely discontinuous at each roll -- this is what spreads/convexity/regime
    must use, per specs/00_TRADING_CONVENTIONS.md's "spreads never from a back-adjusted
    series" rule). `adjusted` has only an f01 column, ratio/Panama-style back-adjusted so
    the return crossing a roll boundary equals the *new* front contract's own real return,
    never an artificial cross-contract jump. `roll_dates` is indexed by date, value = the
    contract code occupying f01 that day (None where fewer contracts remain than ranks
    needed)."""
    if adjust != "ratio":
        raise NotImplementedError(f"adjust={adjust!r} not implemented -- only 'ratio' exists")

    contracts_sorted = expiries.sort_values().index.tolist()
    n = len(contracts_sorted)
    roll_dates_by_contract = {
        c: _business_days_before(pd.Timestamp(expiries[c]), roll_days_before_expiry)
        for c in contracts_sorted
    }
    roll_dates_arr = np.array(
        [roll_dates_by_contract[c].to_datetime64() for c in contracts_sorted],
        dtype="datetime64[D]",
    )

    dates = contract_panel.index
    dates64 = dates.values.astype("datetime64[D]")
    # k(d) = number of contracts already retired (roll_date <= d) on date d -- vectorised
    # across every date at once, not a per-date Python loop.
    k = np.searchsorted(roll_dates_arr, dates64, side="right")

    values = contract_panel[contracts_sorted].to_numpy(dtype=float)
    row_idx = np.arange(len(dates))
    contracts_arr = np.array(contracts_sorted, dtype=object)

    unadjusted = pd.DataFrame(index=dates)
    front_contract = np.full(len(dates), None, dtype=object)
    for i in range(1, n + 1):
        idx = k + (i - 1)
        valid = idx < n
        col_idx = np.clip(idx, 0, n - 1)
        col_values = np.where(valid, values[row_idx, col_idx], np.nan)
        unadjusted[_rank_col(i)] = col_values
        if i == 1:
            front_contract = np.full(len(dates), None, dtype=object)
            front_contract[valid] = contracts_arr[col_idx[valid]]

    roll_dates = pd.Series(front_contract, index=dates, name="f01_contract")

    # Ratio back-adjustment for f01 only, built backward from the most recent (ratio=1)
    # segment -- a bounded loop over roll TRANSITIONS (proportional to contract count, not
    # date count), which is the "roll handling" the project's own vectorisation rule
    # explicitly allows a loop for.
    f01_raw = unadjusted[_rank_col(1)].to_numpy(dtype=float)
    cumulative_factor = np.ones(len(dates))
    transition_positions = [
        p for p in range(1, len(dates)) if front_contract[p] != front_contract[p - 1]
    ]
    for p in reversed(transition_positions):
        old_c, new_c = front_contract[p - 1], front_contract[p]
        if old_c is None or new_c is None:
            continue
        old_price = contract_panel[old_c].iloc[p - 1]
        new_price = contract_panel[new_c].iloc[p - 1]
        if pd.isna(old_price) or pd.isna(new_price) or old_price == 0:
            continue
        cumulative_factor[:p] *= new_price / old_price

    adjusted = pd.DataFrame({_rank_col(1): f01_raw * cumulative_factor}, index=dates)
    return adjusted, unadjusted, roll_dates


def time_spreads(unadj: pd.DataFrame) -> pd.DataFrame:
    """s12=f01-f02, s13=f01-f03, s16=f01-f06, s1_12=f01-f12, s23=f02-f03. A column needing
    a rank `unadj` doesn't have (e.g. s1_12 needs f12, impossible with fewer than 12
    contracts) is NaN, never a crash or a fabricated value. dec_dec is deliberately NOT
    here -- see the module-level `dec_dec()` function; it needs real contract codes, which
    rank-labelled `unadj` columns (f01..fn) no longer carry."""

    def _diff(a: int, b: int) -> pd.Series:
        ca, cb = _rank_col(a), _rank_col(b)
        if ca not in unadj.columns or cb not in unadj.columns:
            return pd.Series(np.nan, index=unadj.index)
        return unadj[ca] - unadj[cb]

    return pd.DataFrame(
        {
            "s12": _diff(1, 2),
            "s13": _diff(1, 3),
            "s16": _diff(1, 6),
            "s1_12": _diff(1, 12),
            "s23": _diff(2, 3),
        },
        index=unadj.index,
    )


def dec_dec(contract_panel: pd.DataFrame) -> pd.DataFrame:
    """Dec(y) - Dec(y+1), read directly off contract codes -- "z" is CME/ICE's own fixed
    December month code, so a "z26" column IS the Dec 2026 contract by construction, no
    roll-calendar lookup needed (corrected from an earlier draft of this plan, which
    wrongly deferred this to Session C). One column per consecutive December pair actually
    present in `contract_panel`; empty DataFrame if fewer than two December contracts
    exist."""
    dec_years = {}
    for code in contract_panel.columns:
        if not code or code[0].upper() != "Z":
            continue
        try:
            year = 2000 + int(code[1:])
        except ValueError:
            continue
        dec_years[year] = code

    result = pd.DataFrame(index=contract_panel.index)
    for year in sorted(dec_years):
        if year + 1 not in dec_years:
            continue
        result[f"dec_dec_{year}_{year + 1}"] = (
            contract_panel[dec_years[year]] - contract_panel[dec_years[year + 1]]
        )
    return result


def annualised_slope(unadj: pd.DataFrame) -> pd.Series:
    """(f01-f12)/f01 -- NaN if unadj has fewer than 12 ranks."""
    if _rank_col(12) not in unadj.columns:
        return pd.Series(np.nan, index=unadj.index)
    f01, f12 = unadj[_rank_col(1)], unadj[_rank_col(12)]
    return (f01 - f12) / f01


def roll_yield(unadj: pd.DataFrame) -> pd.Series:
    """(f01-f02)/f02*12, annualised monthly roll yield."""
    f01, f02 = unadj[_rank_col(1)], unadj[_rank_col(2)]
    return (f01 - f02) / f02 * 12


def convexity(unadj: pd.DataFrame, k: tuple[int, int, int] = (1, 2, 3)) -> pd.Series:
    """cv = F_k1 - 2*F_k2 + F_k3. NaN if any of the three ranks isn't in `unadj`."""
    cols = [_rank_col(i) for i in k]
    if not all(c in unadj.columns for c in cols):
        return pd.Series(np.nan, index=unadj.index)
    return unadj[cols[0]] - 2 * unadj[cols[1]] + unadj[cols[2]]


def curve_regime(
    unadj: pd.DataFrame, storage_cost_m1m2: float = 0.60, lookback: int = 252
) -> pd.DataFrame:
    """Six states plus a seventh, undocumented-by-the-spec "flat" value for the s12==0
    knife edge. Evaluated in the spec's own stated order, first match wins (np.select's
    own semantics match this exactly, so evaluation order is structural, not incidental).
    `slope_pct` (the spec's own p95(lookback)) is today's s12 percentile rank within its
    own trailing lookback-day window, inclusive of today -- NaN for the first
    lookback-1 rows (not enough history), which safely fails every slope_pct>0.95
    comparison via pandas' own NaN semantics, never raising and never false-triggering
    super_backwardation early."""
    f01, f02 = unadj[_rank_col(1)], unadj[_rank_col(2)]
    s12 = f01 - f02
    cv = convexity(unadj)  # default k=(1,2,3) -- the triple this regime classifier uses
    s1_12 = time_spreads(unadj)["s1_12"]

    slope_pct = s12.rolling(lookback).apply(lambda w: (w <= w.iloc[-1]).mean(), raw=False)

    conditions = [
        (s12 < -1.5 * storage_cost_m1m2) & (s1_12 < 0),
        (slope_pct > 0.95) & (s12 > 2.0),
        (s12 < 0) & (cv > 0),
        (s12 < 0) & (cv <= 0),
        (s12 > 0) & (cv > 0),
        (s12 > 0) & (cv <= 0),
    ]
    choices = [
        "super_contango",
        "super_backwardation",
        "convex_contango",
        "concave_contango",
        "convex_backwardation",
        "concave_backwardation",
    ]
    state = np.select(conditions, choices, default="flat")

    return pd.DataFrame(
        {
            "slope_sign": np.sign(s12),
            "cv_sign": np.sign(cv),
            "slope_pct": slope_pct,
            "state": state,
        },
        index=unadj.index,
    )


def transition_matrix(states: pd.Series) -> pd.DataFrame:
    """Row-normalised state[t] -> state[t+1] transition counts. Rows sum to 1 by
    construction; a state observed with zero outgoing transitions in the sample gets an
    all-NaN row (not silently zeroed -- a zero would imply a transition probability that
    was never actually observed)."""
    current = states.iloc[:-1].reset_index(drop=True)
    following = states.iloc[1:].reset_index(drop=True)
    all_states = sorted(states.dropna().unique())

    counts = pd.crosstab(current, following).reindex(
        index=all_states, columns=all_states, fill_value=0
    )
    row_sums = counts.sum(axis=1)
    return counts.div(row_sums, axis=0)


# --- Session C additions: roll-pressure seasonality, Cushing coupling, physical bands ---
# Business-day helpers above (_business_days_before) and core/calendars.py's own
# roll_calendar()/roll_window_flag() (index-roll-window arithmetic) are reused here, not
# reimplemented.


def _ttest_1samp_vs_zero(x: pd.Series) -> tuple[float, float]:
    """One-sample t-test of x against 0 -- mean, t-stat. Hand-rolled (mean / (sample std /
    sqrt(n))) rather than scipy.stats.ttest_1samp: this project's own root NOTES.md rule
    ("ask before adding a dependency") applies, and a one-sample-vs-zero t-stat needs no
    library at all -- the smallest change that satisfies the spec's own acceptance
    criteria. NaN t-stat if fewer than 2 non-NaN observations, or zero variance."""
    x = x.dropna()
    n = len(x)
    if n == 0:
        return (np.nan, np.nan)
    mean = float(x.mean())
    if n < 2:
        return (mean, np.nan)
    se = x.std(ddof=1) / np.sqrt(n)
    if se == 0:
        return (mean, np.nan)
    return (mean, float(mean / se))


def roll_pressure_seasonal(s12: pd.Series, flag: pd.Series) -> pd.DataFrame:
    """Mean & t-stat of day-over-day s12 moves, inside vs outside an index's own roll
    window (`flag`, e.g. core.calendars.roll_window_flag's output), grouped by year.
    Columns: year, mean_in, t_in, mean_out, t_out."""
    delta = s12.diff()
    flag = flag.reindex(delta.index, fill_value=False)
    years = pd.DatetimeIndex(delta.index).year

    rows = []
    for year in sorted(set(years)):
        year_mask = years == year
        mean_in, t_in = _ttest_1samp_vs_zero(delta[year_mask & flag])
        mean_out, t_out = _ttest_1samp_vs_zero(delta[year_mask & ~flag])
        rows.append(
            {"year": year, "mean_in": mean_in, "t_in": t_in, "mean_out": mean_out, "t_out": t_out}
        )
    return pd.DataFrame(rows)


def cushing_utilisation(stocks_kbbl: pd.Series, working_cap_kbbl: pd.Series) -> pd.Series:
    """stocks_kbbl / working_cap_kbbl, elementwise -- `working_cap_kbbl` (sparse,
    semi-annual per this project's real eia.cushing_working_capacity series) is
    forward-filled onto `stocks_kbbl`'s own (weekly) index first, per the spec's own
    "forward-fill the semi-annual capacity" instruction. Never the other way round."""
    combined_index = stocks_kbbl.index.union(working_cap_kbbl.index)
    filled_cap = working_cap_kbbl.reindex(combined_index).sort_index().ffill()
    return stocks_kbbl / filled_cap.reindex(stocks_kbbl.index)


def utilisation_decile(util: pd.Series, years: int = 5) -> pd.Series:
    """Rolling decile rank (1..10) of `util` within its own trailing `years`*365-day
    window, inclusive of today -- requires a sorted DatetimeIndex (pandas' own time-based
    rolling window)."""

    def _decile(window: pd.Series) -> float:
        rank = (window <= window.iloc[-1]).mean()
        return float(min(10, int(np.ceil(rank * 10))))

    return util.rolling(f"{years * 365}D").apply(_decile, raw=False)


def rolling_quantile_bands(
    series: pd.Series, window: int, min_periods: int = 1
) -> pd.DataFrame:
    """Rolling p05/p50/p95 of `series` over a trailing `window` trading days. Columns:
    value, p05, p50, p95.

    The shared mechanism behind every percentile band on the curve page -- physical
    differentials via `physical_bands` below, and convexity, which previously computed
    its own `.rolling(...).quantile(...)` pair inline in the page. Analytics belong in
    `core/`, and a band the page builds for itself is one no test ever sees."""
    rolling = series.rolling(window, min_periods=min_periods)
    return pd.DataFrame(
        {
            "value": series,
            "p05": rolling.quantile(0.05),
            "p50": rolling.quantile(0.50),
            "p95": rolling.quantile(0.95),
        },
        index=series.index,
    )


def physical_bands(diff: pd.Series, window: int = 1260) -> pd.DataFrame:
    """Rolling p05/p50/p95 of a physical differential series over a trailing `window`
    trading days (default 1260 ~= 5 years). Columns: value, p05, p50, p95."""
    return rolling_quantile_bands(diff, window=window, min_periods=1)


def roll_window_offset_grid(delta: pd.Series, index: str, window: int = 5) -> pd.DataFrame:
    """Mean `delta` value (e.g. day-over-day Δs12) by (year, business-day offset from
    `index`'s own roll-window start), offsets `-window..window` -- feeds
    core.theme.bday_heatmap. Window-start dates come from core.calendars.roll_calendar
    (the first date of each month's own window, every year present in `delta`'s index);
    each date in `delta` is assigned the offset to its nearest window start."""
    dates = pd.DatetimeIndex(delta.index)
    years_present = sorted(dates.year.unique())

    window_starts: list[np.datetime64] = []
    for year in years_present:
        cal = roll_calendar(year, index)
        starts = cal.groupby(cal["date"].dt.month)["date"].min()
        window_starts.extend(pd.Timestamp(s).to_datetime64() for s in starts)
    window_starts_arr = np.array(sorted(window_starts), dtype="datetime64[D]")

    offsets = np.empty(len(dates), dtype=int)
    dates64 = dates.values.astype("datetime64[D]")
    for i, d in enumerate(dates64):
        idx = np.searchsorted(window_starts_arr, d)
        candidates = window_starts_arr[max(idx - 1, 0) : idx + 1]
        best = min(
            candidates,
            key=lambda c: abs(np.busday_count(min(c, d), max(c, d))),
            default=d,
        )
        sign = 1 if d >= best else -1
        offsets[i] = sign * np.busday_count(min(best, d), max(best, d))

    grid_df = pd.DataFrame({"year": dates.year, "offset": offsets, "value": delta.to_numpy()})
    grid_df = grid_df[grid_df["offset"].abs() <= window]
    grid = grid_df.pivot_table(index="year", columns="offset", values="value", aggfunc="mean")
    return grid.reindex(columns=range(-window, window + 1))


def tas_window_flag(dates: pd.DatetimeIndex, cl_expiry: pd.Series) -> pd.Series:
    """True on the last two business days before any CL contract's own expiry (reuses
    `_business_days_before`, n=1 and n=2) -- `cl_expiry` is a Series of expiry dates (one
    per CL contract, e.g. pipelines/futures/series_meta.py's own `expiry` column). CL
    contracts expire roughly a month apart, so each contract's own 2-day window never
    overlaps another's -- looping over the (small, contract-count-bounded) set of expiries
    is the same "loop over roll transitions, not dates" convention nearby_panel already
    uses, not a per-date lookup of the nearest expiry."""
    dates = pd.DatetimeIndex(dates)
    flags = pd.Series(False, index=dates)
    for e in pd.Series(cl_expiry).dropna().unique():
        expiry = pd.Timestamp(e)
        day1 = _business_days_before(expiry, 1)
        day2 = _business_days_before(expiry, 2)
        flags |= dates.isin([day1, day2])
    return flags


# --- rank-sourced curves (EIA publishes ranks, not contracts) ----------------------
#
# `nearby_panel` above derives ranks FROM contract codes plus expiries. EIA's futures
# route publishes "Contract 1..4" directly, with no contract code, expiry, open interest
# or volume, so that path cannot be used for it at all. These two functions recover what
# is still recoverable from a rank panel alone.


_LAST_BUSINESS_DAY_ROOTS = {"rb", "ho", "hu"}
_TWENTY_FIFTH_ROOTS = {"cl"}


def nymex_expiry(root: str, year: int, month: int) -> date:
    """Published last-trading day for a NYMEX contract month, from the exchange's rule.

    - `cl`: three business days before the 25th calendar day of the month preceding
      delivery; if the 25th is not a business day, the count starts from the business day
      before it.
    - `rb`/`ho`/`hu`: the last business day of the month preceding delivery.

    Business days are Monday-Friday only. `core/curve.py` already makes this
    approximation for its roll arithmetic (documented in `pipelines/derived/NOTES.md`):
    an exchange holiday falling in the counting window shifts the real date by a day.
    """
    prior_year, prior_month = (year, month - 1) if month > 1 else (year - 1, 12)

    if root in _LAST_BUSINESS_DAY_ROOTS:
        last = pd.Timestamp(year=prior_year, month=prior_month, day=1) + pd.offsets.MonthEnd(1)
        stamp = np.busday_offset(last.date(), 0, roll="backward")
        return pd.Timestamp(stamp).date()

    if root not in _TWENTY_FIFTH_ROOTS:
        raise ValueError(f"no expiry rule for root {root!r}")

    twenty_fifth = date(prior_year, prior_month, 25)
    anchor = np.busday_offset(twenty_fifth, 0, roll="backward")
    return pd.Timestamp(np.busday_offset(anchor, -3, roll="backward")).date()


def roll_dates_from_calendar(root: str, index: pd.DatetimeIndex) -> pd.Series:
    """True on each day a rank series moves to the next contract.

    EIA's "Contract 1" still quotes the expiring contract on its last trading day, so the
    rank rolls on the **following** business day. Derived from the published expiry rule
    rather than inferred from prices: an earlier price-based heuristic here fired 88 times
    a year against a true ~12, because WTI's f01-f02 spread is routinely narrower than a
    single day's move, and "correcting" a non-roll day injects the spread as a spurious
    return -- it raised realised volatility instead of lowering it, which is how it was
    caught.
    """
    index = pd.DatetimeIndex(index)
    if len(index) == 0:
        return pd.Series(dtype=bool)

    # A contract month M expires during month M-1, so the roll landing inside this index
    # can belong to a contract month AFTER index.max(). Stopping the range at index.max()
    # silently drops the final roll -- caught by the no-look-ahead test, where truncating
    # a panel just past a roll made that roll disappear and the raw jump reappear.
    months = pd.period_range(
        index.min() - pd.DateOffset(months=1),
        index.max() + pd.DateOffset(months=2),
        freq="M",
    )
    rolls = set()
    for period in months:
        expiry = nymex_expiry(root, period.year, period.month)
        rolls.add(pd.Timestamp(np.busday_offset(expiry, 1, roll="forward")))

    return pd.Series(index.isin(sorted(rolls)), index=index, name="rolled")


def roll_flags_from_ranks(unadj: pd.DataFrame, root: str) -> pd.Series:
    """Roll days for a rank panel, from `root`'s published expiry rule."""
    return roll_dates_from_calendar(root, pd.DatetimeIndex(unadj.index))


def back_adjust_from_ranks(unadj: pd.DataFrame, root: str) -> pd.Series:
    """Ratio back-adjusted f01 built from a rank panel.

    Same Panama-style construction as `nearby_panel`'s own adjustment and the same
    anchoring: factors accumulate backwards from the most recent segment, whose factor is
    1, so the latest adjusted price equals the latest real price. At each roll the factor
    is `f02_{t-1} / f01_{t-1}` -- the incoming front contract's price over the outgoing
    one's, both measured on the last day they traded side by side, which is exactly
    `nearby_panel`'s `new_price / old_price`.

    Returns are therefore each contract's own returns; the cross-contract spread jump at
    the roll is removed. Never use this for spreads (see the conventions' own rule).
    """
    f01 = unadj[_rank_col(1)].astype(float)
    f02 = unadj[_rank_col(2)].astype(float)
    flags = roll_flags_from_ranks(unadj, root)

    factor = np.ones(len(f01))
    for position in reversed(np.flatnonzero(flags.to_numpy())):
        old_price = f01.iloc[position - 1]
        new_price = f02.iloc[position - 1]
        if pd.isna(old_price) or pd.isna(new_price) or old_price == 0:
            continue
        factor[:position] *= new_price / old_price

    return pd.Series(f01.to_numpy() * factor, index=f01.index, name=_rank_col(1))
