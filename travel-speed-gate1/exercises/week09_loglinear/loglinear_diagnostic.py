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

# TODO 2: plot median lnv vs x (use the bin centre) for each side, a shaded
# band for the 25th-75th percentiles, and Tobler's line ln(6) - 3.5 * x.
# Label both axes and add a legend.

# TODO 3: fit a straight line to the bin medians on each side for
# 0.05 <= x <= 0.40 (np.polyfit(x, median, 1, w=np.sqrt(n)) is fine).
# Print each side's slope, and exp(intercept) in km/h; compare them with
# Tobler's -3.5 and 6 km/h.

# TODO 4: in a comment or a note for the meeting, 3-4 sentences: is it a
# straight line? Where does it bend? Are the two sides the same? How does
# the peak speed compare with 6 km/h?

# fig.savefig(HERE / "fig_loglinear.png", dpi=200)
