"""Z-spread of non-gilt instruments against the bootstrapped gilt curve.

Run from the repo root: python scripts/relative_value.py

Two demos:
  1. A gilt STRIP straight from the DMO file -- fully data-driven and reproducible.
  2. A real GBP supranational (EIB), at an ILLUSTRATIVE price, to show the headline
     "trades +N bp over the gilt curve" use case.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gilt_bootstrapper.bond import Bond
from gilt_bootstrapper.bootstrap import bootstrap
from gilt_bootstrapper.data import load_gilts, load_strips
from gilt_bootstrapper.zspread import z_spread


def main():
    curve = bootstrap(load_gilts())

    # 1) Gilt STRIP (data-driven): single cashflow of 100 at redemption.
    strips = load_strips()
    strip = min(strips, key=lambda s: abs((s.maturity - date(2037, 9, 7)).days))
    s_strip = z_spread(curve, [(strip.maturity, 100.0)], strip.price)
    print("STRIP (real DMO data):")
    print(f"  {strip.name}  price {strip.price:.3f}")
    print(f"  Z-spread vs gilt curve: {s_strip * 1e4:+.1f} bp\n")

    # 2) EIB 5.625% 07-Jun-2032 GBP (XS0114126294), a real AAA supranational.
    #    Price below is ILLUSTRATIVE (free historical single-bond prices are scarce).
    eib = Bond(coupon=5.625, maturity=date(2032, 6, 7), value_date=curve.value_date)
    illustrative_clean = 151.18  # ~20 bp over gilts, a realistic level for AAA EIB
    dirty = illustrative_clean + eib.accrued_interest()
    s_eib = z_spread(curve, eib.cashflows(), dirty)
    print("EIB 5.625% 2032 (real bond, ILLUSTRATIVE price):")
    print(f"  clean {illustrative_clean:.2f}  (dirty {dirty:.3f})")
    print(f"  Z-spread vs gilt curve: {s_eib * 1e4:+.1f} bp")


if __name__ == "__main__":
    main()
