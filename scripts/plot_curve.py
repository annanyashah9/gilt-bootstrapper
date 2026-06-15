"""Plot the bootstrapped vs NSS-fitted gilt curve, saved to docs/curve.png.

Run from the repo root: python scripts/plot_curve.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")  # headless backend, so it runs without a display
import matplotlib.pyplot as plt

from gilt_bootstrapper.bootstrap import IRREGULAR_FIRST_COUPON, bootstrap
from gilt_bootstrapper.data import load_gilts
from gilt_bootstrapper.nss import NSS


def main():
    gilts = [g for g in load_gilts() if g.isin not in IRREGULAR_FIRST_COUPON]
    curve = bootstrap(gilts)
    nss = NSS.fit(gilts)

    maturities = [curve.yearfrac(g.maturity) for g in gilts]
    grid = [t / 10 for t in range(2, int(max(maturities) * 10) + 1)]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(maturities, [g.gross_yield for g in gilts], s=18, color="0.5",
               zorder=3, label="Gilt gross yields (market)")
    ax.plot(grid, [curve.zero_rate(t) * 100 for t in grid], color="C0",
            label="Bootstrap spot (exact, log-linear DF)")
    ax.plot(grid, [nss.zero_rate(t) * 100 for t in grid], color="C3", ls="--",
            label=f"NSS spot (smooth fit, RMS {nss.rms:.2f})")
    ax.plot(grid[10:], [curve.forward_rate(t - 1, t) * 100 for t in grid[10:]],
            color="C2", lw=1, alpha=0.6, label="Bootstrap 1y forward")

    ax.set_title("UK gilt spot curve, 21 Jul 2017 (bootstrap vs Nelson-Siegel-Svensson)")
    ax.set_xlabel("Maturity (years)")
    ax.set_ylabel("Rate (%)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)

    out = Path(__file__).resolve().parents[1] / "docs" / "curve.png"
    out.parent.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
