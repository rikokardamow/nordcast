"""Flags on a first print before it's scored.

An ISP's value more than 3 standard deviations from the week before it is
scored as usual but flagged as an outlier, so the scorecard can show it.
"""

import statistics


def is_outlier(value, past_values, sigmas=3):
    if len(past_values) < 2:
        return False
    mean = statistics.mean(past_values)
    sd = statistics.stdev(past_values)
    return sd > 0 and abs(value - mean) > sigmas * sd
