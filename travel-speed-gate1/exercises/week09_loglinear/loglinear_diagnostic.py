#!/usr/bin/env python3
"""
Week 9 (semester plan section 9): the log-linear diagnostic.

Tobler's hiking function in log space is a straight line,
    ln v = ln 6 - 3.5 * |s + 0.05|,
so if Tobler's FORM is right, the median log speed plotted against
x = |s + 0.05| lies on one straight line of slope -3.5 on both sides of
the peak. See README.md for the steps.

Data: ../../cache/exercise/walking_segments.parquet (not in git)
Run:  ../../../.venv/bin/python loglinear_diagnostic.py
Writes: fig_loglinear.png next to this script
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "cache" / "exercise" / "walking_segments.parquet"

w = pd.read_parquet(DATA)
w["lnv"] = np.log(w.speed_kmh)                   # natural log of km/h
w["x"] = (w.slope + 0.05).abs()                  # Tobler's |s + 0.05|
w["side"] = np.where(w.slope + 0.05 >= 0, "uphill side", "downhill side")
print(f"{len(w):,} segments, {w.outing.nunique():,} outings, "
      f"{w.region.nunique()} regions")
print(w.groupby("side").size().to_string())

# TODO 1: bin x into 0.01-wide bins, separately for each side, and compute
# per bin: the number of segments, the median of lnv, and its 25th and 75th
# percentiles. Keep bins with at least 200 segments.
# (Hint: w["bin"] = np.floor(w.x / 0.01), then groupby(["side", "bin"]).)
w["bin"] = np.floor(w.x / 0.01)          # bin 0 = x from 0 to 0.01, bin 1 = 0.01 to 0.02, ...
b = w.groupby(["side", "bin"]).lnv.agg(
    n="size",                            # how many segments in the bin
    med="median",
    q25=lambda v: v.quantile(0.25),
    q75=lambda v: v.quantile(0.75),      # the 75th percentile
).reset_index()
b = b[b.n >= 200]                        # keep bins with at least 200 segments
b["xc"] = (b.bin + 0.5) * 0.01           # the bin's centre (bin 0 -> 0.005)
print(b.groupby("side").size())
print(b.head())

# TODO 2: plot median lnv vs x (use the bin centre) for each side, a shaded
# band for the 25th-75th percentiles, and Tobler's line ln(6) - 3.5 * x.
# Label both axes and add a legend.
fig, ax = plt.subplots(figsize=(7, 4.5))
for side, color in [("uphill side", "#2a78d6"), ("downhill side", "#eb6834")]:
    d = b[b.side == side]
    ax.fill_between(d.xc, d.q25, d.q75, color=color, alpha=0.15, lw=0)  # middle half of hikers
    ax.plot(d.xc, d.med, "o", ms=3, color=color, label=f"{side}, median")
xs = np.linspace(0, 0.5, 101)
ax.plot(xs, np.log(6) - 3.5 * xs, "k--", label="Tobler: ln 6 − 3.5x")  # a straight line in log space
ax.set_xlabel("x = |slope + 0.05|  (distance from Tobler's fastest slope)")
ax.set_ylabel("ln(speed in km/h)")
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(HERE / "fig_loglinear.png", dpi=200)
print("wrote fig_loglinear.png")

# TODO 3: fit a straight line to the bin medians on each side for
# 0.05 <= x <= 0.40 (np.polyfit(x, median, 1, w=np.sqrt(n)) is fine).
# Print each side's slope, and exp(intercept) in km/h; compare them with
# Tobler's -3.5 and 6 km/h.
for side in ["uphill side", "downhill side"]:
    d = b[(b.side == side) & (b.xc >= 0.05) & (b.xc <= 0.40)]
    k, c = np.polyfit(d.xc, d.med, 1, w=np.sqrt(d.n))   # returns [slope, intercept]
    print(f"{side}: slope {k:.2f} (Tobler -3.5); the line starts at "
          f"{np.exp(c):.2f} km/h (Tobler 6)")
top = b.loc[b.med.idxmax()]
s_top = top.xc - 0.05 if top.side == "uphill side" else -top.xc - 0.05
print(f"fastest bin: slope {100 * s_top:+.1f}%, median {np.exp(top.med):.2f} km/h "
      f"(Tobler: 6 km/h at -5%)")

# TODO 4: in a comment or a note for the meeting, 3-4 sentences: is it a
# straight line? Where does it bend? Are the two sides the same? How does
# the peak speed compare with 6 km/h?
