"""Bootstrap a spot curve from gilt dirty prices.

Working in maturity order, each gilt fixes one new node: the discount factor at its
maturity such that the bond's cashflows discount to its market dirty price. Coupon
dates before that interpolate off already-solved nodes; the residual is monotonic in
the unknown DF, so a bracketed root-find (brentq) is robust.
"""

from __future__ import annotations

from scipy.optimize import brentq

from .bond import Bond, t1_settlement
from .curve import Curve
from .data import Gilt

# 0¾% Treasury Gilt 2023: first issued mid-2017, still in its irregular first coupon
# period on our snapshot, which the regular-schedule bond model can't price.
IRREGULAR_FIRST_COUPON = {"GB00BF0HZ991"}


def bootstrap(gilts: list[Gilt]) -> Curve:
    gilts = sorted((g for g in gilts if g.isin not in IRREGULAR_FIRST_COUPON),
                   key=lambda g: g.maturity)
    curve = Curve(t1_settlement(gilts[0].settlement_date))

    for gilt in gilts:
        flows = Bond.from_gilt(gilt).cashflows()
        t_m = curve.yearfrac(gilt.maturity)

        def residual(df_m, flows=flows, t_m=t_m, market=gilt.dirty_price):
            trial = curve.with_node(t_m, df_m)
            pv = sum(amount * trial.df(curve.yearfrac(d)) for d, amount in flows)
            return pv - market

        df_m = brentq(residual, 1e-9, 1.5, xtol=1e-14)
        curve.add_node(t_m, df_m)

    return curve
