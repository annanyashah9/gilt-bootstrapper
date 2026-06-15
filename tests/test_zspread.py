"""Tests for the Z-spread calculator."""

import os
from datetime import date
from pathlib import Path

import pytest

from gilt_bootstrapper import data
from gilt_bootstrapper.bond import Bond
from gilt_bootstrapper.bootstrap import IRREGULAR_FIRST_COUPON, bootstrap
from gilt_bootstrapper.zspread import price_with_spread, z_spread, z_spread_gilt

FIXTURE = Path(__file__).parent / "fixtures" / "gilts_sample.xls"
FIXTURE_DATE = date(2017, 7, 21)


@pytest.fixture
def curve_and_gilts():
    gilts = data.parse(FIXTURE, FIXTURE_DATE)
    return bootstrap(gilts), gilts


def test_input_gilts_have_zero_spread(curve_and_gilts):
    curve, gilts = curve_and_gilts
    for g in gilts:
        assert z_spread_gilt(curve, g) == pytest.approx(0.0, abs=1e-6)


def test_round_trip_known_spread(curve_and_gilts):
    curve, gilts = curve_and_gilts
    cfs = Bond.from_gilt(gilts[2]).cashflows()
    target = price_with_spread(curve, cfs, 0.0075)  # 75 bp
    assert z_spread(curve, cfs, target) == pytest.approx(0.0075, abs=1e-8)


def test_sign(curve_and_gilts):
    curve, gilts = curve_and_gilts
    cfs = Bond.from_gilt(gilts[2]).cashflows()
    fair = price_with_spread(curve, cfs, 0.0)
    assert z_spread(curve, cfs, fair - 2) > 0   # cheaper -> positive spread
    assert z_spread(curve, cfs, fair + 2) < 0   # richer  -> negative spread


def test_zero_spread_matches_curve_repricing(curve_and_gilts):
    curve, gilts = curve_and_gilts
    cfs = Bond.from_gilt(gilts[2]).cashflows()
    via_df = sum(amt * curve.df(curve.yearfrac(d)) for d, amt in cfs)
    assert price_with_spread(curve, cfs, 0.0) == pytest.approx(via_df)


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="set RUN_NETWORK_TESTS=1 to check all 44 gilts",
)
def test_all_input_gilts_zero_spread():
    gilts = data.load_gilts()
    curve = bootstrap(gilts)
    for g in gilts:
        if g.isin in IRREGULAR_FIRST_COUPON:
            continue
        assert z_spread_gilt(curve, g) == pytest.approx(0.0, abs=1e-6)
