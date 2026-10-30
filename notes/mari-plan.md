# mari – the retrain plan

30 oct 2026. mari is the european mfrr platform. when the nordic tsos join, dk1's mfrr is activated through it, which is the largest known break ahead for nordcast's target. no code here: this is what to do, and when.

## the date moved

the plan and the notes said q1 2027. that is out of date.

- 3 jul 2026: "remain focused on connecting ... by Q1 2027" ([nbm](https://nordicbalancingmodel.net/reconfirmation-of-the-target-timeline-for-the-nordic-accession-to-the-mari-platform/)).
- 2 sep 2026, withdrawn: the change request "to mitigate the risk of undesired price spread in MARI is incompatible with the planned Nordic accession in Q1 2027". "New go-live date not yet decided"; after the summer next year, "with September or October 2027 currently considered the most likely timeframe" ([nbm](https://nordicbalancingmodel.net/changes-in-the-target-timeline-for-the-nordic-accession-to-the-mari-platform/)).
- 15 oct 2026: entso-e's accession roadmap v16 gives no date of its own and points to that notice ([entso-e](https://www.entsoe.eu/network_codes/eb/mari/)).

so: no firm date, sep–oct 2027 likely, and it has slipped repeatedly (legal deadline jul 2024, then 2026, then q1 2027). plan on the date moving again. the notices speak for the nordic tsos jointly, with nothing specific to energinet.

## what that does to the record

good news. the challenger's 60-day window can run 31 oct – 29 dec 2026 and the promotion date stays 1 apr 2027. mari no longer cuts across the test, and whichever model holds the headline gets about five months live before the break. nothing about the test changes; the pre-registration's regime-break rule fires on the accession itself, whenever that is.

## what the last break says

the nordic mfrr energy activation market went live on 4 mar 2025. first prints, dk1, by month:

| | imbalance price sd, eur/mwh | satisfiedDemand sd, mw |
|---|---|---|
| oct 2024 – feb 2025, before (esett) | 68–115 | not published |
| mar – sep 2025 | 180–322 | 180–250 |
| oct 2025 – feb 2026 | 108–206 | 125–184 |
| mar – sep 2026 | 88–190 | 144–194 |

volatility nearly tripled and took about seven months to come down. it isn't a clean measure: 1 oct 2025 also brought 15-min day-ahead, and the months carry their own seasons. and the nordic tsos are delaying mari precisely to avoid a repeat of that price spread, so this is a warning and not a forecast.

the replay adds a second lesson: fitting only on the ~5 months after the 4 mar 2026 change was worse at every horizon than pooling with a regime flag (model cards). so don't throw away the old regime; flag it, and wait for enough of the new one.

## what will change, and what's only a guess

confirmed by the notices: the accession date, and that a price-spread change request is being built. not found on any page read: what happens to 15-min settlement, the imbalance price formula, or what energinet publishes. these are hypotheses to check when energinet publishes its implementation details, none of them facts:

- cross-border netting could weaken the link between dk1's own need and `SatisfiedDemand` (activated volume) and `mfrrRequest`.
- `DominatingDirection` and the 25 mw threshold may be redefined.
- column names or meanings may change, as they did on 4 mar 2026.

## the plan

**1. now, until a firm date: watch.** read the nordic balancing model news once a month and record the date in this file. energinet's implementation webinars are the source for the hypotheses above; read them when they appear. no modelling work yet: there's nothing to fit.

**2. when a firm date is set, about 3 months before:**
- list what energinet will change, and turn each item into a line in notes/sources.md.
- add a check on the live data's sign and columns. `tests/test_sign_convention.py` pins a fixed past week, so it can't see a new definition arrive.
- add `regime_mari` beside `regime_activated` in features, off until the date. a v2's inputs only: v1 stays as pre-registered.
- owner's decision, by amendment, before go-live: which call holds the headline through the break. recommended: fall back to ar(1) or persistence. they refit on the last 7 days, so they recover by themselves within a week, where a model trained on the old market won't.

**3. at go-live:** the pre-registration's rule stops any open window and reports what was scored. keep freezing everything, flagged; the model's calls on the new market are the evidence for how badly it degrades. an incident entry and a change log line. check the sign and direction coding by hand on the first days.

**4. eight weeks after go-live, at the earliest: the first refit.** about 5,400 isps, pooled with the old regime under `regime_mari`, as the 2026 evidence favours. it becomes a challenger with its own pre-registration and a 60-day window. if volatility is still far from settled, wait: seven months is what the last break took.

**5. promotion:** quarter boundaries only, after validation, as now. a sep or oct 2027 go-live gives: first refit nov–dec 2027, window closed by feb 2028, **promotion 1 apr 2028**.

## not checked

picasso (aFRR), a separate later break with its own date; a statnett report put it a year after mari, unconfirmed. the eight-week minimum is a judgement from one precedent, not a measured optimum.
