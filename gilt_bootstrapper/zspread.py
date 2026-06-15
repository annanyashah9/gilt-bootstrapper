"""Z-spread: the constant spread over the bootstrapped spot curve that reprices a bond.

Each cashflow is discounted at the curve's zero rate plus the spread (semi-annual):
    PV(s) = Σ CF_j * (1 + (z(t_j) + s)/2) ** (-2 t_j)
We solve PV(s) = dirty for s. A gilt that was an input to the curve prices at s ≈ 0.
"""

from __future__ import annotations

from datetime import date

from scipy.optimize import brentq

from .bond import Bond
from .curve import Curve
from .data import Gilt


def price_with_spread(curve: Curve, cashflows: list[tuple[date, float]], s: float) -> float:
    pv = 0.0
    for d, amount in cashflows:
        t = curve.yearfrac(d)
        pv += amount * (1 + (curve.zero_rate(t) + s) / 2) ** (-2 * t)
    return pv


def z_spread(curve: Curve, cashflows: list[tuple[date, float]], dirty_price: float) -> float:
    """The spread (decimal) that prices these cashflows to dirty_price."""
    return brentq(lambda s: price_with_spread(curve, cashflows, s) - dirty_price,
                  -0.5, 0.5, xtol=1e-12)


def z_spread_gilt(curve: Curve, gilt: Gilt) -> float:
    return z_spread(curve, Bond.from_gilt(gilt).cashflows(), gilt.dirty_price)
