"""Tests for the gilt data layer.

These run offline against a small committed fixture (a handful of real rows from
the DMO 2017 file). The one test that actually hits the network is opt-in via the
RUN_NETWORK_TESTS env var.
"""

import os
import shutil
from datetime import date
from pathlib import Path

import pytest

from gilt_bootstrapper import data

FIXTURE = Path(__file__).parent / "fixtures" / "gilts_sample.xls"
FIXTURE_DATE = date(2017, 7, 21)


@pytest.fixture
def gilts():
    return data.parse(FIXTURE, FIXTURE_DATE)


def test_keeps_only_conventional(gilts):
    # Fixture has 5 conventional gilts plus one index-linked and one STRIP.
    assert len(gilts) == 5
    for g in gilts:
        assert "index-linked" not in g.name.lower()
        assert "strip" not in g.name.lower()


def test_known_row_parsed_correctly(gilts):
    g = next(g for g in gilts if g.isin == "GB00BDRHNP05")
    assert g.name == "1¼% Treasury Gilt 2027"
    assert g.coupon == 1.25
    assert g.maturity == date(2027, 7, 22)


def test_dirty_equals_clean_plus_accrued(gilts):
    # Real-data invariant for conventional gilts; catches column-mapping mistakes.
    for g in gilts:
        assert g.dirty_price == pytest.approx(g.clean_price + g.accrued_interest, abs=1e-4)


def test_settlement_date_applied(gilts):
    assert all(g.settlement_date == FIXTURE_DATE for g in gilts)


def test_sorted_by_maturity(gilts):
    maturities = [g.maturity for g in gilts]
    assert maturities == sorted(maturities)


@pytest.mark.parametrize("name, expected", [
    ("8¾% Treasury Stock 2017", 8.75),
    ("1% Treasury Gilt 2017", 1.0),
    ("0½% Treasury Gilt 2022", 0.5),
    ("4¼% Treasury Gilt 2027", 4.25),
    ("0 1/8% Index-linked Treasury Gilt 2019", 0.125),
])
def test_parse_coupon(name, expected):
    assert data.parse_coupon(name) == expected


def test_cache_avoids_redownload(monkeypatch, tmp_path):
    cached = tmp_path / "2017.xls"
    monkeypatch.setattr(data, "cache_path", lambda: cached)

    calls = []

    def fake_download(url, dest):
        calls.append(url)
        shutil.copy(FIXTURE, dest)

    monkeypatch.setattr(data, "download", fake_download)

    data.load_gilts(FIXTURE_DATE)   # cache miss -> downloads
    data.load_gilts(FIXTURE_DATE)   # cache hit  -> no download
    assert len(calls) == 1


@pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="set RUN_NETWORK_TESTS=1 to run the live DMO download",
)
def test_live_download():
    gilts = data.load_gilts(force_refresh=True)
    assert len(gilts) > 30
    assert any(g.isin == "GB00BDRHNP05" for g in gilts)
