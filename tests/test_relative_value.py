"""Tests for the relative-value (Z-spread on non-gilt instruments) demo."""

from datetime import date
from pathlib import Path

import pytest

from gilt_bootstrapper import data
from gilt_bootstrapper.bond import Bond
from gilt_bootstrapper.bootstrap import bootstrap
from gilt_bootstrapper.zspread import price_with_spread, z_spread

FIXTURE = Path(__file__).parent / "fixtures" / "gilts_sample.xls"
FIXTURE_DATE = date(2017, 7, 21)


def test_strip_zspread_is_sane():
    curve = bootstrap(data.parse(FIXTURE, FIXTURE_DATE))
    strip = data.parse_strips(FIXTURE, FIXTURE_DATE)[0]
    spread = z_spread(curve, [(strip.maturity, 100.0)], strip.price)
    assert abs(spread) < 0.02  # a strip prices close to the curve, within ~200 bp


def test_corporate_spread_round_trip():
    # The "corporate" path: a non-gilt Bond priced at a known spread over the curve.
    curve = bootstrap(data.parse(FIXTURE, FIXTURE_DATE))
    bond = Bond(coupon=5.0, maturity=date(2030, 6, 7), value_date=curve.value_date)
    dirty = price_with_spread(curve, bond.cashflows(), 0.0030)
    assert z_spread(curve, bond.cashflows(), dirty) == pytest.approx(0.0030, abs=1e-8)
