"""Tests for the bond/cashflow model.

Offline tests reprice the 5 conventional gilts in the fixture and check our accrued
interest against the DMO's published figures. The all-45 check is opt-in via
RUN_NETWORK_TESTS=1.
"""

import os
from datetime import date
from pathlib import Path

import pytest

from gilt_bootstrapper import data
from gilt_bootstrapper.bond import Bond, add_months, coupon_schedule, t1_settlement

FIXTURE = Path(__file__).parent / "fixtures" / "gilts_sample.xls"
FIXTURE_DATE = date(2017, 7, 21)


@pytest.fixture
def gilts():
    return data.parse(FIXTURE, FIXTURE_DATE)


# --- pure arithmetic, exact ---

def test_par_when_yield_equals_coupon():
    # Valued on a coupon date: no accrued, first coupon a full period away.
    bond = Bond(coupon=4.0, maturity=date(2030, 6, 7), value_date=date(2017, 6, 7))
    assert bond.accrued_interest() == 0.0
    assert bond.dirty_price(4.0) == pytest.approx(100.0)
    assert bond.clean_price(4.0) == pytest.approx(100.0)


def test_single_coupon_hand_value():
    bond = Bond(coupon=5.0, maturity=date(2018, 1, 7), value_date=date(2017, 7, 7))
    _, future, w = bond._period()
    assert future == [date(2018, 1, 7)]
    expected = (5.0 / 2 + 100.0) / (1 + 0.03 / 2) ** w
    assert bond.dirty_price(3.0) == pytest.approx(expected)


# --- schedule / dates ---

def test_t1_settlement_skips_weekend():
    assert t1_settlement(date(2017, 7, 21)) == date(2017, 7, 24)  # Fri -> Mon


def test_add_months_clamps_month_end():
    assert add_months(date(2017, 1, 31), 1) == date(2017, 2, 28)
    assert add_months(date(2017, 7, 22), -6) == date(2017, 1, 22)


def test_schedule_spacing_and_bounds():
    value_date = date(2017, 7, 24)
    prev, future = coupon_schedule(date(2027, 7, 22), value_date)
    assert prev <= value_date < future[0]
    assert future[-1] == date(2027, 7, 22)
    assert all(b > a for a, b in zip(future, future[1:]))
    for earlier, later in zip([prev] + future, future):
        assert add_months(earlier, 6) == later


# --- real-data validation ---

def test_accrued_matches_dmo(gilts):
    for g in gilts:
        bond = Bond.from_gilt(g)
        assert bond.accrued_interest() == pytest.approx(g.accrued_interest, abs=1e-4)


def test_reprice_at_dmo_yield(gilts):
    # Looser tolerance: the DMO yield is rounded to 4 dp, which moves long-bond
    # prices by ~a penny.
    for g in gilts:
        bond = Bond.from_gilt(g)
        assert bond.dirty_price(g.gross_yield) == pytest.approx(g.dirty_price, abs=0.02)
        assert bond.clean_price(g.gross_yield) == pytest.approx(g.clean_price, abs=0.02)


# 0¾% Treasury Gilt 2023, first issued 2017-07-11 -- it's still inside its irregular
# first coupon period on our snapshot, which the regular-schedule model can't price.
NEW_ISSUE_2017 = "GB00BF0HZ991"


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="set RUN_NETWORK_TESTS=1 to validate against all 45 gilts",
)
def test_accrued_matches_dmo_all_gilts():
    for g in data.load_gilts():
        if g.isin == NEW_ISSUE_2017:
            continue
        assert Bond.from_gilt(g).accrued_interest() == pytest.approx(g.accrued_interest, abs=1e-4)
