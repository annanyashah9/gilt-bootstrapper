"""Tests for the Curve object: interpolation, zero rates and forwards."""

import math
from datetime import date

import pytest

from gilt_bootstrapper.curve import Curve

VALUE_DATE = date(2017, 7, 24)


def flat_forward_curve(rate_pct, max_t=30):
    """Curve with a constant semi-annual forward = rate_pct."""
    y = rate_pct / 100 / 2
    nodes = [(0.0, 1.0)] + [(t, (1 + y) ** (-2 * t)) for t in range(1, max_t + 1)]
    return Curve(VALUE_DATE, nodes)


def test_df_at_nodes():
    curve = Curve(VALUE_DATE, [(0.0, 1.0), (1.0, 0.97), (5.0, 0.85)])
    assert curve.df(1.0) == pytest.approx(0.97)
    assert curve.df(5.0) == pytest.approx(0.85)
    assert curve.df(0.0) == 1.0
    assert curve.df(-1.0) == 1.0


def test_log_linear_midpoint_is_geometric_mean():
    curve = Curve(VALUE_DATE, [(0.0, 1.0), (2.0, 0.9), (4.0, 0.8)])
    assert curve.df(3.0) == pytest.approx(math.sqrt(0.9 * 0.8))


def test_zero_rate_inverts_df():
    curve = flat_forward_curve(3.0)
    # Flat forward => flat zero at the same rate.
    assert curve.zero_rate(5.0) == pytest.approx(0.03)
    # And df(t) reconstructs from the zero rate.
    z = curve.zero_rate(7.0)
    assert curve.df(7.0) == pytest.approx((1 + z / 2) ** (-2 * 7.0))


def test_forward_rate_constant_on_flat_curve():
    curve = flat_forward_curve(2.5)
    assert curve.forward_rate(3.0, 8.0) == pytest.approx(0.025)


def test_flat_forward_extrapolation():
    curve = flat_forward_curve(4.0, max_t=10)
    # Beyond the last node the forward stays constant, so the zero stays at 4%.
    assert curve.zero_rate(20.0) == pytest.approx(0.04)
