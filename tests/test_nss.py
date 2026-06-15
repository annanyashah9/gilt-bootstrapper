"""Tests for the Nelson-Siegel-Svensson fit."""

import os
from datetime import date

import pytest

from gilt_bootstrapper import data
from gilt_bootstrapper.bond import Bond
from gilt_bootstrapper.bootstrap import bootstrap
from gilt_bootstrapper.nss import NSS, nss_zero

VALUE_DATE = date(2017, 7, 24)
TRUE_PARAMS = (0.025, -0.015, 0.02, 0.01, 1.5, 8.0)


def synthetic_gilts():
    """Coupon bonds priced off a known NSS curve, for a well-posed fit."""
    truth = NSS(VALUE_DATE, TRUE_PARAMS)
    gilts = []
    for i, year in enumerate(range(2019, 2048)):  # ~29 bonds, > 6 params
        g = data.Gilt(name=f"synthetic {year}", isin=f"S{i}", coupon=2.0 + i * 0.05,
                      maturity=date(year, 7, 22), clean_price=0.0, dirty_price=0.0,
                      accrued_interest=0.0, gross_yield=0.0,
                      settlement_date=date(2017, 7, 21))
        dirty = sum(amt * truth.df(truth.yearfrac(d)) for d, amt in Bond.from_gilt(g).cashflows())
        gilts.append(data.Gilt(g.name, g.isin, g.coupon, g.maturity, 0.0, dirty,
                               0.0, 0.0, g.settlement_date))
    return gilts


def test_recovers_known_curve():
    fit = NSS.fit(synthetic_gilts(), VALUE_DATE)
    assert fit.rms < 1e-3
    for t in (1, 3, 7, 15, 25):
        assert fit.zero_rate(t) == pytest.approx(nss_zero(t, *TRUE_PARAMS), abs=1e-4)


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="set RUN_NETWORK_TESTS=1 to fit the real gilts",
)
def test_fit_real_gilts_tracks_bootstrap():
    gilts = data.load_gilts()
    curve = bootstrap(gilts)
    fit = NSS.fit(gilts)
    assert fit.rms < 1.0  # smooth model -> small (non-zero) pricing residual
    for tenor in (2, 10, 30):
        t = curve.yearfrac(date(2017 + tenor, 7, 22))
        assert fit.zero_rate(t) == pytest.approx(curve.zero_rate(t), abs=0.0015)  # ~15bp
