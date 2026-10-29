# Interconnector flows layer (#33, DK1): risk analysis (written before any code)

29 Oct 2026. From the energy-forecasting catalogue (`docs/PROJECTS.md` #33, "Interconnector Flows", grade 6, framed there for Ireland/GB); built for DK1 in `~/nordcast`, claimed by message. Layer #32 (residual load) is its neighbour: residual load = thermal production + net import, and this layer splits the net import by border.

## Facts checked today

- **Six DK1 borders in `ElectricityProdex5MinRealtime`, 5-min:** Germany, Netherlands (COBRA), Great Britain (Viking Link), Norway (Skagerrak), Sweden (Konti-Skan), and the Great Belt to DK2.
- **Sign, tested per border:** hourly means against `ProductionConsumptionSettlement` (+ = import, stated there), 1–7 Aug and 1–7 Oct 2026: correlation 1.000 for DE, NL, GB, NO, SE and 0.999 for the Great Belt, bias within ±12 MW. So every real-time column is **+ = import**, the energy-analyst skill's rule for GB (`gas-power-metals.md` §C6: "normalise to 'import to GB = +'") applied to DK1.
- **No open capacity.** Energi Data Service carries no DK1 cross-border capacity (NTC or flow-based) and no scheduled commercial flows; only aFRR transfer limits (`AfrrBorderAvailableTransferCapacity`), which are a different product. Capacities and schedules sit with ENTSO-E (token) and JAO. So a utilisation measure like the skill's gas one (flow ÷ capacity, its #25 chart) can't be built here from open, keyless data.
- **Observed limits:** in those two weeks NL ran exactly ±700 MW, GB ±1,456, SE −699 to +715, the Great Belt about ±600, DE −3,491 to +3,321; NO capped at 1,387 in August and 1,139 in October, so its limit moves.

## Risks, ranked

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Calling an observed maximum "capacity".** Limits move (Norway, above), and a link that never reached its rating looks smaller than it is. | Certain | High | The layer never says capacity or utilisation. "At its limit" means within 2 % of the largest absolute flow in the same direction over the trailing 28 days, known at the time; the README says it is an observed limit. No rating is typed in from memory. |
| 2 | **Sign or column changes at Energinet.** | Low | High | A fixed-week test pins each border against settlement (correlation > 0.99, bias under 50 MW). |
| 3 | **Touching the live record.** | Medium | High | Six new series and their rows; no change to `features.SERIES`, the frozen calls, the challenger or the pre-registration. |
| 4 | **Leakage in the alpha test.** | Medium | High | As layer #32: values as of isp − h − 5 min with the 5-min feed's nominal lag; the 28-day limit uses only days before; weekly refits out of sample on the replay's 2026 rounds; day-block bootstrap and a daily t statistic. |
| 5 | **A redundant layer.** Net import is already inside residual load. | High | Medium | The test asks what the split adds: binding borders and per-border ramps, on top of rung 4 + residual load, not instead of it. |
| 6 | **Clashing with other sessions.** | Low | Medium | `sources/energinet.py` (six `SERIES` entries), one migration, new tests and `docs/layers/interconnectors/`. |

## Stop conditions

- Any border's correlation with settlement under 0.99.
- The binding measure needs data from after the freeze.
