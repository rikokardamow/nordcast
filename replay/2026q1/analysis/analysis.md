# 2026q1 – analysis

target first prints 04 Mar 2025 – 31 Dec 2025 utc, 29023 isps, before the round only.

- acf: lag 1 0.77, lag 4 0.42, lag 8 0.25, lag 96 (a day) 0.12.
- pacf: lag 1 0.77, lag 2 0.11, lag 3 -0.02.
- by hour: most negative at 16:00 (-121 mw), most positive at 3:00 (-47 mw); sd 146-242 mw.
- distribution: mean -80, median -68, sd 197, skew -0.68, 1 % / 99 % -655 / 386 mw; 8.7% exactly 0, 27.9% up, 63.4% down.
- stationarity: adf statistic -12.3 (1 % critical -3.4), p 8.36e-23.
- correlation with the target (training rows, 15 min): mfrr_down_mw_last -0.20, solar_fc_da -0.10, wind_onshore_err_da_last -0.10, wind_offshore_err_da_last -0.09, wind_offshore_err_da_mean4 -0.08, wind_onshore_err_da_mean4 -0.07, sd_std8 -0.07, wind_onshore_fc_1h_minus_da -0.07, weekday -0.06, wind_offshore_fc_1h_minus_da -0.06, da_price +0.06, mfrr_up_mw_last +0.11, afrr_down_mw_last +0.14, sd_lag4 +0.20, sd_lag3 +0.21, dir_last +0.21, sd_lag2 +0.23, sd_mean4 +0.27, sd_lag1 +0.30
