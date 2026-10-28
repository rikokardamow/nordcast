# replay log

28 oct 2026. the walk-forward rehearsal per notes/replay.md: quarterly rounds on the clean window from 1 oct 2025 (15-min day-ahead on every layer), four rounds, q4 2025 to q3 2026. the imbalance replay is short because the data is: `ImbalancePrice` starts 4 mar 2025. every input is an estimated vintage, which flatters every method a little; said once here.

the ladder order and promotion rule are as committed in notes/replay.md before round 1.

## 2025q4 – persistence

config: replay/2025q4/plan.md. scorecard (replay/2025q4/scorecard.csv), 8,825 isps per horizon:

| h | mae | rmse | pinball | coverage | direction | brier | sign | pnl (10 mw, eur) |
|---|---|---|---|---|---|---|---|---|
| 15 | 128.7 | 174.4 | 42.2 | 0.794 | 0.501 | 0.998 | 0.555 | 141,940 |
| 30 | 134.8 | 181.8 | 44.2 | 0.797 | 0.482 | 1.036 | 0.535 | 82,785 |
| 60 | 138.3 | 186.1 | 45.3 | 0.796 | 0.478 | 1.045 | 0.529 | 46,635 |

review (draft, replay/2025q4/review.md): the evening reversals and the onshore shortfalls cost the most; the residual acf (0.62 at lag 1) says mean reversion is the next rung. change for round 2: add ar(1) as a challenger.
