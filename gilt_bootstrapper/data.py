"""Load UK gilt reference data from the DMO's historical price files.

Layer 1 of the bootstrapper: turn a real DMO reference-price file into typed
`Gilt` objects. No bond maths here yet.

We use the DMO's 2017 historical file, which has a row per (gilt, business day)
from January to 21 July 2017 (after that FTSE-Tradeweb took over pricing). Each
row already carries clean price, dirty price, accrued interest and yield. The
file is downloaded on first use and cached under data/cache/ (gitignored).
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import xlrd
from xlrd.xldate import xldate_as_datetime

# The DMO serves these files behind opaque media slugs, so we pin the URL.
DMO_2017_URL = "https://www.dmo.gov.uk/media/sn5fj3aw/2017-gilt-reference-prices.xls"

# Last business day in the 2017 file: 45 conventional gilts maturing 2017-2068.
DEFAULT_SETTLEMENT = date(2017, 7, 21)

# Sheet layout: rows 0-3 are a title block, row 4 is the header, data from row 5.
FIRST_DATA_ROW = 5
NAME, ISIN, REDEMPTION, COB, CLEAN, DIRTY, ACCRUED, YIELD = range(8)

# Unicode vulgar fractions the DMO uses in gilt names, e.g. "8¾%".
FRACTIONS = {"⅛": 0.125, "¼": 0.25, "⅜": 0.375, "½": 0.5,
             "⅝": 0.625, "¾": 0.75, "⅞": 0.875}


@dataclass(frozen=True)
class Gilt:
    """A conventional gilt as priced on one settlement date."""

    name: str
    isin: str
    coupon: float          # annual rate in percent, e.g. 8.75 for 8¾%
    maturity: date         # redemption date
    clean_price: float
    dirty_price: float
    accrued_interest: float
    gross_yield: float     # DMO-published yield (percent), kept for validation
    settlement_date: date


def parse_coupon(name: str) -> float:
    """Pull the coupon out of a gilt name, e.g. '8¾% Treasury Stock 2017' -> 8.75.

    The coupon isn't a column in the file, only the name. Most are unicode
    fractions (¼ ½ ¾ …); index-linked gilts use an ascii form like '0 1/8%'.
    """
    head = name.split("%", 1)[0].strip()

    fraction = 0.0
    if head and head[-1] in FRACTIONS:
        fraction = FRACTIONS[head[-1]]
        head = head[:-1].strip()
    elif "/" in head:                         # ascii fraction, e.g. "0 1/8"
        whole_part, frac_part = head.rsplit(" ", 1) if " " in head else ("0", head)
        num, den = frac_part.split("/")
        fraction = float(num) / float(den)
        head = whole_part

    return (float(head) if head else 0.0) + fraction


def is_conventional(name: str) -> bool:
    """Keep plain coupon gilts; drop index-linked gilts and STRIPS.

    We're building a nominal curve, so index-linked and STRIPS don't belong. As a
    bonus, conventional gilts satisfy dirty == clean + accrued, which index-linked
    don't (their dirty price carries the inflation uplift) -- handy as a check.
    """
    lowered = name.lower()
    return "index-linked" not in lowered and "strip" not in lowered


def _to_date(serial: float, datemode: int) -> date:
    return xldate_as_datetime(serial, datemode).date()


def cache_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "cache" / "2017-gilt-reference-prices.xls"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "gilt-bootstrapper/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


def parse(path: Path, settlement_date: date) -> list[Gilt]:
    """Read the workbook and return conventional gilts priced on settlement_date."""
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    datemode = sheet.book.datemode

    gilts = []
    for row in range(FIRST_DATA_ROW, sheet.nrows):
        name = sheet.cell_value(row, NAME)
        cob = sheet.cell_value(row, COB)
        redemption = sheet.cell_value(row, REDEMPTION)

        # Skip footer/blank rows where the dates aren't real serial numbers.
        if not name or not isinstance(cob, (int, float)) or not isinstance(redemption, (int, float)):
            continue
        if _to_date(cob, datemode) != settlement_date or not is_conventional(name):
            continue

        gilts.append(Gilt(
            name=name,
            isin=sheet.cell_value(row, ISIN),
            coupon=parse_coupon(name),
            maturity=_to_date(redemption, datemode),
            clean_price=float(sheet.cell_value(row, CLEAN)),
            dirty_price=float(sheet.cell_value(row, DIRTY)),
            accrued_interest=float(sheet.cell_value(row, ACCRUED)),
            gross_yield=float(sheet.cell_value(row, YIELD)),
            settlement_date=settlement_date,
        ))

    gilts.sort(key=lambda g: g.maturity)
    return gilts


def load_gilts(settlement_date: date = DEFAULT_SETTLEMENT, force_refresh: bool = False) -> list[Gilt]:
    """Conventional gilts priced on settlement_date, sorted by maturity.

    Downloads the DMO 2017 file on first use, then reads from the local cache.
    """
    path = cache_path()
    if force_refresh or not path.exists():
        download(DMO_2017_URL, path)
    return parse(path, settlement_date)


@dataclass(frozen=True)
class Strip:
    """A gilt STRIP: a single zero-coupon cashflow of 100 at maturity."""

    name: str
    isin: str
    maturity: date
    price: float           # clean == dirty for a zero-coupon strip (no accrued)
    settlement_date: date


def parse_strips(path: Path, settlement_date: date) -> list[Strip]:
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    datemode = sheet.book.datemode

    strips = []
    for row in range(FIRST_DATA_ROW, sheet.nrows):
        name = sheet.cell_value(row, NAME)
        cob = sheet.cell_value(row, COB)
        redemption = sheet.cell_value(row, REDEMPTION)

        if not name or not isinstance(cob, (int, float)) or not isinstance(redemption, (int, float)):
            continue
        if _to_date(cob, datemode) != settlement_date or "strip" not in name.lower():
            continue

        strips.append(Strip(
            name=name,
            isin=sheet.cell_value(row, ISIN),
            maturity=_to_date(redemption, datemode),
            price=float(sheet.cell_value(row, CLEAN)),
            settlement_date=settlement_date,
        ))

    strips.sort(key=lambda s: s.maturity)
    return strips


def load_strips(settlement_date: date = DEFAULT_SETTLEMENT, force_refresh: bool = False) -> list[Strip]:
    """Gilt STRIPS priced on settlement_date, sorted by maturity."""
    path = cache_path()
    if force_refresh or not path.exists():
        download(DMO_2017_URL, path)
    return parse_strips(path, settlement_date)
