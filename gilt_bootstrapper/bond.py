"""Bond/cashflow model for conventional gilts: schedule, accrued, price from yield.

Conventions (UK gilts): semi-annual coupons, actual/actual (ICMA) accrual, T+1
settlement, semi-annual compounding. Verified by reproducing DMO reference prices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .data import Gilt


def add_months(d: date, n: int) -> date:
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def t1_settlement(cob: date) -> date:
    """Value date = COB + 1, skipping weekends. Bank holidays out of scope."""
    d = cob + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def coupon_schedule(maturity: date, value_date: date) -> tuple[date, list[date]]:
    """Step back 6 months from maturity to get (prev_coupon, future_coupons).

    Assumes a regular coupon history. Gilts issued within their first coupon period
    have an irregular first coupon, which this doesn't model (out of scope).
    """
    dates = [maturity]
    while dates[0] > value_date:
        dates.insert(0, add_months(dates[0], -6))
    return dates[0], dates[1:]


@dataclass(frozen=True)
class Bond:
    coupon: float       # annual rate in percent, per 100 face
    maturity: date
    value_date: date

    @classmethod
    def from_gilt(cls, gilt: Gilt) -> "Bond":
        return cls(gilt.coupon, gilt.maturity, t1_settlement(gilt.settlement_date))

    def _period(self) -> tuple[date, list[date], float]:
        """(prev_coupon, future_coupons, w) -- w is the remaining period fraction."""
        prev, future = coupon_schedule(self.maturity, self.value_date)
        period = (future[0] - prev).days
        w = (future[0] - self.value_date).days / period
        return prev, future, w

    def accrued_interest(self) -> float:
        prev, future, _ = self._period()
        period = (future[0] - prev).days
        return (self.coupon / 2) * (self.value_date - prev).days / period

    def cashflows(self) -> list[tuple[date, float]]:
        """Future (date, amount) pairs: coupons plus 100 redemption at maturity."""
        _, future, _ = self._period()
        flows = [(d, self.coupon / 2) for d in future]
        flows[-1] = (flows[-1][0], flows[-1][1] + 100.0)
        return flows

    def dirty_price(self, ytm_pct: float) -> float:
        _, future, w = self._period()
        y = ytm_pct / 100 / 2
        n = len(future)
        return sum((self.coupon / 2 + (100.0 if k == n - 1 else 0.0)) / (1 + y) ** (w + k)
                   for k in range(n))

    def clean_price(self, ytm_pct: float) -> float:
        return self.dirty_price(ytm_pct) - self.accrued_interest()
