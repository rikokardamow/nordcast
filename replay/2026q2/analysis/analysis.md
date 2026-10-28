# 2026q2 – analysis

target first prints 30 Mar 2025 – 31 Mar 2026 utc, 35125 isps, before the round only.

- acf: lag 1 0.77, lag 4 0.39, lag 8 0.24, lag 96 (a day) 0.14.
- pacf: lag 1 0.77, lag 2 0.09, lag 3 -0.03.
- by hour: most negative at 15:00 (-104 mw), most positive at 21:00 (-33 mw); sd 145-224 mw.
- distribution: mean -69, median -60, sd 189, skew -0.67, 1 % / 99 % -619 / 373 mw; 10.0% exactly 0, 29.0% up, 61.0% down.
- stationarity: adf statistic -13.1 (1 % critical -3.4), p 2.12e-24.
- correlation with the target (training rows, 15 min): mfrr_down_mw_last -0.23, wind_onshore_err_da_last -0.13, wind_offshore_err_da_last -0.12, wind_onshore_err_da_mean4 -0.10, wind_offshore_err_da_mean4 -0.10, wind_onshore_fc_1h_minus_da -0.09, solar_fc_da -0.09, wind_offshore_fc_1h_minus_da -0.09, solar_err_da_last -0.09, solar_err_da_mean4 -0.07, sd_std8 -0.07, imb_minus_da_last +0.06, regime_activated +0.07, da_price +0.08, afrr_down_mw_last +0.10, mfrr_up_mw_last +0.12, sd_lag4 +0.22, dir_last +0.23, sd_lag3 +0.23, sd_lag2 +0.27, sd_mean4 +0.30, sd_lag1 +0.33
