# 2026q3 – analysis

target first prints 29 Jun 2025 – 30 Jun 2026 utc, 35117 isps, before the round only.

- acf: lag 1 0.77, lag 4 0.35, lag 8 0.21, lag 96 (a day) 0.14.
- pacf: lag 1 0.77, lag 2 0.03, lag 3 -0.01.
- by hour: most negative at 15:00 (-97 mw), most positive at 21:00 (-18 mw); sd 137-214 mw.
- distribution: mean -53, median -49, sd 176, skew -0.45, 1 % / 99 % -552 / 373 mw; 12.3% exactly 0, 30.6% up, 57.1% down.
- stationarity: adf statistic -13.1 (1 % critical -3.4), p 2.14e-24.
- correlation with the target (training rows, 15 min): mfrr_down_mw_last -0.24, solar_fc_da -0.14, wind_onshore_err_da_last -0.13, wind_onshore_err_da_mean4 -0.11, wind_onshore_fc_1h_minus_da -0.10, sd_std8 -0.09, wind_offshore_err_da_last -0.07, weekday -0.05, afrr_up_mw_last +0.05, imb_minus_da_last +0.07, mfrr_up_mw_last +0.11, afrr_down_mw_last +0.12, da_price +0.16, sd_lag4 +0.23, dir_last +0.23, sd_lag3 +0.25, sd_lag2 +0.29, sd_mean4 +0.32, sd_lag1 +0.34
