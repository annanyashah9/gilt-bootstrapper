"""Nelson-Siegel-Svensson curve fitting.

A smooth, 6-parameter parametric alternative to the bootstrap. The bootstrap reprices
every gilt exactly but its forwards wiggle on sparse data; NSS fits one smooth curve
to all the prices at once (the Bank of England fits a variant to the gilt market).

The NSS function gives the zero rate directly; we treat its output as the semi-annual
zero rate to stay consistent with the rest of the project.
"""

from __future__ import annotations

from datetime import date

import numpy as np
from scipy.optimize import least_squares

from .bond import Bond, t1_settlement
from .curve import yearfrac
from .data import Gilt


def nss_zero(t, beta0, beta1, beta2, beta3, tau1, tau2):
    """Nelson-Siegel-Svensson zero rate (decimal) at time t (years)."""
    t = np.maximum(t, 1e-8)
    x1, x2 = t / tau1, t / tau2
    slope = (1 - np.exp(-x1)) / x1
    hump1 = slope - np.exp(-x1)
    hump2 = (1 - np.exp(-x2)) / x2 - np.exp(-x2)
    return beta0 + beta1 * slope + beta2 * hump1 + beta3 * hump2


class NSS:
    """A fitted NSS curve, exposing the same interface as Curve."""

    def __init__(self, value_date: date, params, rms: float = 0.0):
        self.value_date = value_date
        self.params = tuple(params)
        self.rms = rms

    def yearfrac(self, d: date) -> float:
        return yearfrac(self.value_date, d)

    def zero_rate(self, t: float) -> float:
        return float(nss_zero(t, *self.params))

    def df(self, t: float) -> float:
        if t <= 0:
            return 1.0
        return (1 + self.zero_rate(t) / 2) ** (-2 * t)

    def forward_rate(self, t1: float, t2: float) -> float:
        return 2 * ((self.df(t1) / self.df(t2)) ** (1 / (2 * (t2 - t1))) - 1)

    @classmethod
    def fit(cls, gilts: list[Gilt], value_date: date | None = None) -> "NSS":
        from .bootstrap import IRREGULAR_FIRST_COUPON

        gilts = [g for g in gilts if g.isin not in IRREGULAR_FIRST_COUPON]
        if value_date is None:
            value_date = t1_settlement(gilts[0].settlement_date)

        # Pre-compute each bond's (time, amount) cashflows and market dirty price.
        bonds = [([(yearfrac(value_date, d), amt) for d, amt in Bond.from_gilt(g).cashflows()],
                  g.dirty_price) for g in gilts]

        def residuals(p):
            return [sum(amt * (1 + nss_zero(t, *p) / 2) ** (-2 * t) for t, amt in cfs) - mkt
                    for cfs, mkt in bonds]

        x0 = [0.02, -0.01, 0.01, 0.01, 2.0, 10.0]
        lower = [-1, -1, -1, -1, 0.05, 0.05]
        upper = [1, 1, 1, 1, 30, 30]
        sol = least_squares(residuals, x0, bounds=(lower, upper))
        rms = float(np.sqrt(np.mean(np.square(sol.fun))))
        return cls(value_date, sol.x, rms)
