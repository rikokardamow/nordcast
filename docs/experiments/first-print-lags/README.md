# Check: are the nominal lags late enough? (29 Oct 2026)

**In plain English.** Past data is stamped with an assumed time of publication, and that assumption must err late. This check finds it does for every measured feed but one: the forecast target sometimes appeared later than assumed. The sample is small, so it needs re-measuring.

**Question.** Backfilled history is stamped `published_at = NOMINAL_LAG(isp)`, and the challenger reads live data through the same lags (`challenger.nominal`). A lag must err late (notes/backfill.md: check it against the live pulls "and correct the constant"). Are they late enough?

**Answer: every measured lag is, except the target's.** `SatisfiedDemand` (and `DominatingDirection`, the same row) usually prints ~7 min after its ISP ends, but in 3 of 16 watched ISPs it printed ~22 min after, past the nominal 15. Small sample, one day; re-measure after a week before acting.

**Method** ([run.py](run.py), results in [results.csv](results.csv)). From `~/nordcast-archive`: an ISP's first print is the first pull in which its value is complete (every 5-minute piece non-null). Pull times come from the archive's log, one line per source per run. An ISP counts only if its dataset was pulled at least every 6 min from the ISP's start to 30 min past its nominal lag. The archive ran 28 Oct 18:16–21:32 and from 29 Oct 18:58 (with a gap 19:00–19:22), hence the small sample. Forecast series and day-ahead prices can't be checked this way.

| series | ISPs | nominal (min after ISP end) | first print: median | p95 | max | after nominal |
|---|---|---|---|---|---|---|
| satisfied_demand, dominating_direction | 16 | 15 | 6.8 | 21.9 | 22.2 | **19 %** |
| imbalance_price_eur | 12 | 45 | 21.8 | 22.9 | 23.9 | 0 % |
| afrr_up_mw, afrr_down_mw | 12 | 45 | 6.8 | 21.9 | 22.2 | 0 % |
| mfrr_up_mw, mfrr_down_mw | 6 | 60 | −19.4 | −19.1 | −19.1 | 0 % |
| 5-min feed (wind, solar, residual load, six flows) | 17 | 5 | −2.3 | 2.4 | 2.9 | 0 % |

**The late prints are Energinet's, not the archive's.** For the 19:45 UTC ISP on 29 Oct the archive pulled `ImbalancePrice` successfully every minute; the row first appeared at 20:22:10, all fields at once. The 20:00 ISP had appeared at its usual ~7 min, before it: publication can be out of order. The other two late ISPs (20:30, 20:45) look the same.

**What it means.**
- **Live calls are fine.** The frozen calls read exact pulls, and the challenger's nominal view can only hide data, never show data that hasn't arrived. In the late ISPs the challenger simply sees a staler target than training would have.
- **Training is a little optimistic.** The backfilled target counts as visible at end + 15 min; in about one ISP in five it really came at ~end + 22 min, so v1's training rows sometimes carry a one-ISP-fresher target lag than live will have.
- **Don't change the constant under v1.** lightgbm_v1 was trained with 15 min and its live view applies 15 min; changing `NOMINAL_LAG` now would break that match. The fix belongs with the next re-backfill and model: 25 min (above the 22.2 seen), after a week of measurements.
- **mFRR activation is published ~4.5 min before its ISP starts** (scheduled ahead), so its 60-min lag is very conservative; it's still after every freeze (the latest is 20 min before the ISP), so it can't be a same-ISP input.
- The 5-minute feed posts each 5 minutes' value before that 5 minutes ends, as `sources/energinet.py` says.

**Next.** Re-run after 5 Nov (the 7-day soak) on a full week; if the target's late share holds, raise its lag to 25 min with the next re-backfill and v2, and update `tests/test_sources.py`'s measured first prints.
