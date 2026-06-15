"""Spot/zero curve: discount factors, zero rates and forwards from solved nodes.

Interpolation is log-linear on discount factors (equivalent to piecewise-constant
forward rates). Compounding is semi-annual, matching the gilt conventions:
    DF(t) = (1 + z/2) ** (-2t)
Year fractions use actual/365 -- a convention choice, easily swapped here.
"""

from __future__ import annotations

import math
from bisect import insort
from datetime import date


def yearfrac(value_date: date, d: date) -> float:
    """Actual/365 year fraction -- the single day-count source for the curve."""
    return (d - value_date).days / 365.0


class Curve:
    def __init__(self, value_date: date, nodes: list[tuple[float, float]] | None = None):
        self.value_date = value_date
        self.nodes = sorted(nodes) if nodes else [(0.0, 1.0)]

    def yearfrac(self, d: date) -> float:
        return yearfrac(self.value_date, d)

    def add_node(self, t: float, df: float) -> None:
        insort(self.nodes, (t, df))

    def with_node(self, t: float, df: float) -> "Curve":
        """A copy with one extra node -- used to price against a trial DF."""
        return Curve(self.value_date, self.nodes + [(t, df)])

    def df(self, t: float) -> float:
        if t <= 0:
            return 1.0
        ts = [n[0] for n in self.nodes]
        ln = [math.log(n[1]) for n in self.nodes]
        if t >= ts[-1]:
            i = len(ts) - 1  # flat-forward extrapolation off the last segment
        else:
            i = next(j for j in range(1, len(ts)) if ts[j] >= t)
        t0, t1 = ts[i - 1], ts[i]
        frac = (t - t0) / (t1 - t0)
        return math.exp(ln[i - 1] + frac * (ln[i] - ln[i - 1]))

    def zero_rate(self, t: float) -> float:
        """Semi-annually compounded zero rate at t, as a decimal."""
        return 2 * (self.df(t) ** (-1 / (2 * t)) - 1)

    def forward_rate(self, t1: float, t2: float) -> float:
        """Semi-annually compounded forward rate between t1 and t2, as a decimal."""
        return 2 * ((self.df(t1) / self.df(t2)) ** (1 / (2 * (t2 - t1))) - 1)
