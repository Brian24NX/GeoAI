#!/usr/bin/env python3
"""
Assets for the 23 Oct lab-meeting deck (build_deck.js):
  assets/contours.png  10 m contours of Tuckerman and Huntington ravines,
                       just southeast of the Mt Washington summit, from the
                       USGS 3DEP 1 m lidar cells cached for T2
                       (travel-speed-gate1/cache/dem1m/), transparent, 16:9
  assets/data.json     the numbers the slides chart (sac_scale coverage per
                       region, from results/t3_tag_transfer/coverage.csv)

Run: ../../.venv/bin/python make_assets.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import tifffile  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEM = ROOT / "travel-speed-gate1" / "cache" / "dem1m"
OUT = HERE / "assets"
X0S = range(316000, 318500, 500)          # 5 cells west -> east
Y0S = range(4903500, 4902000, -500)       # 3 cells north -> south
NAMES = {"wm": "White Mtns", "adk": "Adirondacks", "catskills": "Catskills",
         "greenmtn": "Green Mtns", "shenandoah": "Shenandoah",
         "smokies": "Smokies", "pisgah": "Pisgah", "frontrange": "Front Range",
         "wasatch": "Wasatch", "cascades": "Cascades", "gorge": "Col. Gorge",
         "olympic": "Olympic", "bayarea": "Bay Area",
         "sangabriel": "San Gabriels", "yosemite": "Yosemite",
         "tahoe": "Tahoe", "northshore": "North Shore"}


def contours():
    rows = [np.hstack([tifffile.imread(DEM / f"utm19n_{x}_{y}.tif")
                       for x in X0S]) for y in Y0S]
    z = np.vstack(rows).astype(float)                  # north up, 1 m pixels
    z = gaussian_filter(z[::2, ::2], 1.5)              # 2 m, lightly smoothed
    h = int(round(z.shape[1] * 9 / 16))                # crop to 16:9
    top = (z.shape[0] - h) // 2
    z = z[top:top + h]
    fig = plt.figure(figsize=(13.333, 7.5), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    lo, hi = np.floor(z.min() / 10) * 10, np.ceil(z.max() / 10) * 10
    minor = np.arange(lo, hi + 1, 10)
    major = minor[minor % 50 == 0]
    ax.contour(z[::-1], levels=minor, colors="#9fc2ae", linewidths=0.55,
               alpha=0.30, origin="lower")
    ax.contour(z[::-1], levels=major, colors="#b9d4c4", linewidths=1.05,
               alpha=0.42, origin="lower")
    ax.set_xlim(0, z.shape[1] - 1)
    ax.set_ylim(0, z.shape[0] - 1)
    fig.savefig(OUT / "contours.png", transparent=True)
    print(f"contours: {z.shape[1] * 2} x {z.shape[0] * 2} m, "
          f"{z.min():.0f}-{z.max():.0f} m elevation")


def data():
    c = pd.read_csv(ROOT / "travel-speed-gate1" / "results" / "t3_tag_transfer"
                    / "coverage.csv").sort_values("sac_tagged")
    out = {"coverage": [{"region": NAMES[r], "pct": round(100 * v, 1)}
                        for r, v in zip(c.region, c.sac_tagged)]}
    (OUT / "data.json").write_text(json.dumps(out, indent=1))
    print("coverage:", out["coverage"][0], "...", out["coverage"][-1])


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    contours()
    data()
