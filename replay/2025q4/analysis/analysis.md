# 2025q4 – analysis

target first prints 04 Mar 2025 – 30 Sep 2025 utc, 20190 isps, before the round only.

- acf: lag 1 0.76, lag 4 0.43, lag 8 0.24, lag 96 (a day) 0.11.
- pacf: lag 1 0.76, lag 2 0.13, lag 3 -0.02.
- by hour: most negative at 14:00 (-152 mw), most positive at 21:00 (-56 mw); sd 155-269 mw.
- distribution: mean -99, median -84, sd 212, skew -0.60, 1 % / 99 % -700 / 409 mw; 6.0% exactly 0, 27.0% up, 67.0% down.
- stationarity: adf statistic -11.1 (1 % critical -3.4), p 4.46e-20.
- feature correlations: no training rows before this round (the clean window starts 1 oct 2025); the next rounds report them.
