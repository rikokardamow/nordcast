# DK1 price coupling layer (#31, DK1 part): risk analysis (written before any code)

29 Oct 2026. From the energy-forecasting catalogue (`docs/PROJECTS.md` #31, "Power Markets", grade 8, framed there for Ireland/GB first; Ireland is another session's). Built for DK1 in `~/nordcast`, claimed by message. It follows layer #33, which left open whether a border at its limit shows as a price split.

## Facts checked today

- **`DayAheadPrices`** (Energi Data Service, 15-min since 1 Oct 2025, EUR and DKK) carries **DE, DK1, DK2, NO2, SE3 and SE4**. Of DK1's six neighbours that covers Germany, DK2, Norway (NO2) and Sweden (SE3); the Netherlands and Great Britain are missing (GB left EU market coupling in 2021).
- **Timing:** the day-ahead auction clears about 12:45–13:00 Copenhagen time the day before; nordcast already stamps DK1's price at 13:00 the day before (`sources/energinet.py`). So the target ISP's prices, and every spread, are known at every freeze.
- **The record is DK1-only.** `energinet.fetch()` filters `PriceArea = DK1`, the live loader keeps DK1 rows, and the archive doesn't pull `DayAheadPrices`. Adding neighbour areas to the record changes that shared code.

## Risks, ranked

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Changing shared code under a live record** (and with other sessions committing to `main`). | High if done | High | Not done in this pass: the back-test pulls neighbour prices into a gitignored cache (`data/history/DayAheadPricesAll/`), outside the record. Only if the test finds an edge does the record change, and then only with the owner's yes. |
| 2 | **Reading a day-ahead spread as a physical constraint.** The spread is the auction's (scheduled) result; physical flows also move intraday and in balancing. | Certain | Medium | The coupling check compares the day-ahead spread with the physical flow and reports agreement as a rate, not as a rule. |
| 3 | **Two of six borders missing** (NL, GB). | Certain | Medium | Stated wherever the coupling share is shown; no NL/GB price is inferred. |
| 4 | **Leakage.** | Low | High | Spreads for the target ISP are published the day before every freeze. The fit is the replay's weekly out-of-sample refit, as in #32/#33. |
| 5 | **"Coupled" defined too tightly or loosely.** Prices print to 2 decimals. | Medium | Low | Coupled = |spread| < EUR 0.01/MWh; the share at 0.5 and 1 EUR is reported too. |
| 6 | **Load on Energi Data Service.** | Low | Low | About 13 monthly calls, cached; finished months aren't refetched. |

## Stop conditions

- The day-ahead prices for a target ISP turn out to be published after its freeze.
- The test needs NL or GB prices.
