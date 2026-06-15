"""Tests for the bootstrapper, including the North Star repricing test."""

import os
from datetime import date
from pathlib import Path

import pytest

from gilt_bootstrapper import data
from gilt_bootstrapper.bond import Bond
from gilt_bootstrapper.bootstrap import IRREGULAR_FIRST_COUPON, bootstrap
from gilt_bootstrapper.curve import Curve

FIXTURE = Path(__file__).parent / "fixtures" / "gilts_sample.xls"
FIXTURE_DATE = date(2017, 7, 21)
VALUE_DATE = date(2017, 7, 24)


def make_gilt(coupon, maturity, dirty):
    return data.Gilt(name="synthetic", isin="X", coupon=coupon, maturity=maturity,
                     clean_price=0.0, dirty_price=dirty, accrued_interest=0.0,
                     gross_yield=0.0, settlement_date=FIXTURE_DATE)


def reprice(curve, gilt):
    return sum(amt * curve.df(curve.yearfrac(d))
               for d, amt in Bond.from_gilt(gilt).cashflows())


def test_synthetic_recovery():
    # Price bonds off a known flat 4% curve, then check the bootstrap recovers it.
    y = 0.04 / 2
    known = Curve(VALUE_DATE, [(0.0, 1.0)] + [(t, (1 + y) ** (-2 * t)) for t in range(1, 41)])
    gilts = [make_gilt(4.0, m, None) for m in
             (date(2020, 7, 22), date(2025, 7, 22), date(2030, 7, 22))]
    gilts = [make_gilt(g.coupon, g.maturity, reprice(known, g)) for g in gilts]

    curve = bootstrap(gilts)
    for g in gilts:
        t = curve.yearfrac(g.maturity)
        assert curve.df(t) == pytest.approx(known.df(t), rel=1e-9)


def test_north_star_offline():
    gilts = data.parse(FIXTURE, FIXTURE_DATE)
    curve = bootstrap(gilts)
    for g in gilts:
        assert reprice(curve, g) == pytest.approx(g.dirty_price, abs=1e-6)


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="set RUN_NETWORK_TESTS=1 to bootstrap all 44 gilts",
)
def test_north_star_all_gilts():
    gilts = data.load_gilts()
    curve = bootstrap(gilts)

    for g in gilts:
        if g.isin in IRREGULAR_FIRST_COUPON:
            continue
        assert reprice(curve, g) == pytest.approx(g.dirty_price, abs=1e-6)

    # Sanity on the curve: positive zero rates, rising at the short end.
    short = curve.zero_rate(curve.yearfrac(date(2020, 7, 22)))
    medium = curve.zero_rate(curve.yearfrac(date(2030, 12, 7)))
    assert 0 < short < medium < 0.05
