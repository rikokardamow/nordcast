# council – model cards and leakage

29 oct 2026. the plan (phase 2) says each council member gets its pretraining cutoff written down and any backtest window overlapping its pretraining flagged. this is that list, as far as the papers go. not built; the council waits for gate g1.

## the leakage rule, and a correction to the plan

the plan cites arxiv 2609.20554 as showing that leakage distorts tsfm backtests. that paper (chen et al., "does training on future data pay?") is about **equity returns**, using annual chronos / timesfm vintages trained on stock data. its finding is the opposite of "inflates": in the us-trained setting, vintages trained past the forecast date *lowered* accuracy in 18 of 20 model–horizon cases. its conclusion is that temporal exposure is an information-set violation that must be documented, not proof of inflated scores. worth keeping as a citation, but for the rule, not the effect size.

the paper that actually backs the rule for us is **meyer et al., "rethinking evaluation in the era of tsfms: (un)known information leakage challenges" (arxiv 2510.13654, paderborn)**:

- **direct leakage:** a dataset in one model's pretraining is another's test set. of 401 datasets used across 22 tsfms, only 6 % never appear in any pretraining or fine-tuning corpus. "electricity" (uci, 370 portuguese clients) is the standard example – it's in every major model's corpus.
- **indirect (temporal) leakage:** a model trained on series that overlap the test period in time and share a driver (weather, a crisis) learns the test period without seeing the test series. their madrid transport case: ~43 % lower mae from overlap alone; their covid stock experiment: up to ~37 % on single runs with only 7 of 484 series leaking.
- **their requirement 2:** every test observation must come after the latest pretraining timestamp of every model compared.

**how nordcast satisfies it:** the live record does this by construction – a council call is frozen before the isp, and the isp is after every model's release. the problem is only replays and backtests. so:

- council members are scored **live only** on the headline scorecard.
- any replay of a council member is labelled with the model's release date, and rounds before that date get a `pretraining-overlap` flag in replay-log.md, as the plan says.
- dk1 imbalance, `PowerSystemRightNow`, entso-e and eSett series appearing in a corpus would be direct leakage; a european weather or load series covering the same period would be indirect. both go on the card.

## cards

### chronos-2 (amazon, arxiv 2510.15821, technical report 17 oct 2025)

- **released:** oct 2025. treat 2025-10-17 as the cutoff until a corpus end date is found; the report gives none.
- **pretraining data (table 6):** real univariate sets from the chronos and gift-eval corpora – including energy: *electricity* (uci, 15 min–1 w), *solar* (us, 5 min / 1 h), *wind farms* (australia), *london smart meters*, *buildings 900k* – plus weather (weatherbench, ushcn, temperature-rain) and transport, cloud, wiki. **all multivariate and covariate training is synthetic.** no entso-e, energinet, nord pool or nordic grid series listed.
- **in its evaluation, not its training:** fev-bench energy tasks include entso-e load, epf-be/de/fr/np/pjm and gefcom. so it has been *tuned against* european price/load benchmarks even though they're not in the corpus.
- **overlap with nordcast's windows:** the clean replay window starts 1 oct 2025, two weeks before release. the real energy series in the corpus are mostly 2011–2021. direct leakage: none found. indirect: low – weatherbench is reanalysis up to ~2018. flag rounds before 2025-10-17 anyway.
- **interface:** context up to 8192 steps, 21 quantiles (0.01–0.99), past-only and known-future covariates, group attention across series. it can take the q10/q50/q90 we need directly, and wind-forecast error / da price as covariates.
- **evidence on our kind of problem:** best tsfm for belgian imbalance prices with covariates, behind trained models at 15 min, level by 2 h (literature.md). best tsfm on a post-cutoff us price set (gridstatus 2025, pan & ezzat, arxiv 2607.02623), and its average with a domain model beat everything.

### timesfm 2.5 (google, 2025)

- **released:** 2025 (exact date and corpus end not read today).
- **pretraining data:** not checked. timesfm 1.0's corpus (das et al., icml 2024) is google trends, wiki pageviews and synthetic data plus public sets; meyer et al. flag a possible pretraining/test overlap (traffic hourly) in that paper. read the 2.5 model card before scoring.
- **interface:** univariate in the chronos-2 comparison table (no covariates). the gridstatus paper ran a covariate variant ("timesfm 2.5 w.") that didn't help much.
- **evidence:** behind chronos-2 at every horizon on belgian imbalance prices; worst rank change on price spikes in the gridstatus paper (rank +10 in spike periods).
- **note:** timesfm-3 (330m, multivariate with covariates) appeared aug 2026 (alphaxiv 2608.timesfm-3). if the council takes the newest google model, that's a different card and a later cutoff.

### timestral

not found on arxiv under that name today. confirm the model name and source before it gets a card.

## practical defaults from the papers

- context: 2048 steps is the common choice; chronos-2 gains little beyond it. at 1-min data that's ~34 h; at isp resolution ~21 days.
- don't average tsfms with each other (correlated); do average the best tsfm with the trained model and score that as its own row.
- report tails separately (q10 and q90 pinball, extreme-isp subset). that's where tsfms fail.

## sources

arxiv 2510.15821 (chronos-2), 2510.13654 (meyer et al., leakage), 2609.20554 (chen et al., look-ahead in pretrained financial models), 2605.17045 (bui et al., belgian tsfm evaluation), 2607.02623 (pan & ezzat, tsfm contamination in epf).
