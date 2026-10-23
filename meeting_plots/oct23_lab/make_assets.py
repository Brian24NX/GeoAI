#!/usr/bin/env python3
"""
Assets for the 23 Oct lab-meeting deck (build_deck.js):
  assets/contours.png  10 m contours of Tuckerman and Huntington ravines,
                       just southeast of the Mt Washington summit, from the
                       USGS 3DEP 1 m lidar cells cached for T2
                       (travel-speed-gate1/cache/dem1m/), transparent, 16:9
  assets/data.json     the numbers the slides chart (sac_scale coverage per
                       region, from results/t3_tag_transfer/coverage.csv)
  assets/slide_curve.png    speed vs slope, real hikers vs Tobler (slide 5)
  assets/slide_regions.png  terrain vs map tags in each held-out region (slide 6)
  assets/slide_map.png      the 17 regions, circle area = walking hours (slide 4)

Run: ../../.venv/bin/python make_assets.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.legend_handler import HandlerTuple  # noqa: E402
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


SLIDE = {"font.size": 15, "axes.labelsize": 16, "xtick.labelsize": 14,
         "ytick.labelsize": 14, "legend.fontsize": 15,
         "font.family": ["Arial", "DejaVu Sans"]}
TS = ROOT / "travel-speed-gate1" / "results"


def slide_curve():
    """Slide 5: real hikers vs Tobler (speed vs slope), large type."""
    nums = json.loads((TS / "t1_findings" / "numbers.json").read_text())
    a, ku, kd, s0, e = nums["forms_cv"]["smooth_asym"]["params_all"]
    b = pd.read_csv(TS / "t1_findings" / "slope_bins.csv")
    s = np.linspace(-0.4, 0.4, 321)
    x = s + s0
    ours = np.exp(a - np.where(x >= 0, ku, kd) * (np.sqrt(x ** 2 + e ** 2) - e))
    tobler = 6 * np.exp(-3.5 * np.abs(s + 0.05))
    keep = b.slope_mid.abs() <= 0.4
    with plt.rc_context(SLIDE):
        fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=200)
        dots, = ax.plot(100 * b.slope_mid[keep], b.median_kmh[keep], "o", ms=6,
                        color="#9ec5f0")
        line, = ax.plot(100 * s, ours, color="#2a78d6", lw=3.5)
        tob, = ax.plot(100 * s, tobler, "--", color="#1c2321", lw=2.5)
        ax.annotate("6 km/h", (-5, 6.0), (4, 6.1), fontsize=16, fontweight="bold",
                    va="center", arrowprops=dict(arrowstyle="-", color="#1c2321", lw=1))
        ax.text(-4.5, 3.78, "4.2 km/h", ha="center", va="top", fontsize=16,
                fontweight="bold", color="#2a78d6")
        ax.set_xlim(-40, 40)
        ax.set_ylim(0, 6.6)
        ax.set_xlabel("slope (%)      ← downhill    uphill →")
        ax.set_ylabel("walking speed (km/h)")
        ax.grid(color="#e4e3df", lw=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend([(dots, line), tob], ["real hikers (17 regions)", "Tobler 1993"],
                  handler_map={tuple: HandlerTuple(ndivide=None)},
                  frameon=False, loc="lower center", fontsize=15, handlelength=3)
        fig.tight_layout()
        fig.savefig(OUT / "slide_curve.png", transparent=True)
        plt.close(fig)
    print("slide_curve.png")


def slide_regions():
    """Slide 6: each region held out, terrain vs map tags, large type."""
    b = pd.read_csv(TS / "t3_harness_terrain15m" / "loro_by_region.csv").pivot(
        index="region", columns="arm", values="crps_skill_vs_slope_pct")
    b = b.sort_values("lin_rs")
    y = np.arange(len(b))
    with plt.rc_context(SLIDE):
        fig, ax = plt.subplots(figsize=(7.0, 5.45), dpi=200)
        for i, (t_, r_) in enumerate(zip(b.lin_tags, b.lin_rs)):
            ax.plot([t_, r_], [i, i], color="#c9c8c3", lw=2, zorder=1)
        ax.scatter(b.lin_tags, y, s=70, color="#eb6834", label="map tags", zorder=2)
        ax.scatter(b.lin_rs, y, s=70, color="#2a78d6", label="terrain (elevation)",
                   zorder=3)
        ax.axvline(0, color="#1c2321", lw=1)
        ax.set_yticks(y, [NAMES[r] for r in b.index], fontsize=13)
        ax.set_xlabel("improvement over slope alone (%)")
        ax.grid(axis="x", color="#e4e3df", lw=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, loc="lower right", fontsize=14)
        fig.tight_layout()
        fig.savefig(OUT / "slide_regions.png", transparent=True)
        plt.close(fig)
    print("slide_regions.png:", int((b.lin_rs > b.lin_tags).sum()), "of", len(b),
          "regions with terrain ahead")


LABELS = {  # region: (side of the circle, vertical nudge in points)
    "northshore": ("left", 0), "olympic": ("left", -2), "cascades": ("right", 2),
    "gorge": ("left", -3), "bayarea": ("left", 0), "tahoe": ("right", 3),
    "yosemite": ("right", -4), "sangabriel": ("left", -6), "wasatch": ("right", 0),
    "frontrange": ("right", 0), "smokies": ("above", 0), "pisgah": ("right", -6),
    "shenandoah": ("right", 0), "catskills": ("right", -6), "adk": ("left", 2),
    "greenmtn": ("above", 0), "wm": ("right", 1)}


def slide_map():
    """Slide 4: the 17 regions, circle area = walking hours, large labels."""
    import sys
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Polygon
    from pyproj import Transformer
    gate1 = ROOT / "travel-speed-gate1"
    sys.path.insert(0, str(gate1))
    import regions
    ne = gate1 / "cache" / "naturalearth"
    to = Transformer.from_crs(4326, 5070, always_xy=True)       # CONUS Albers
    cx, cy = to.transform(*zip(*[(-130.0, 32.0), (-130.0, 50.3), (-66.0, 47.5),
                                 (-66.0, 30.0), (-96, 50.5), (-96, 26.5)]))
    xr, yr = (min(cx), max(cx)), (min(cy), max(cy))
    xr = (xr[0], xr[1] + 0.05 * (xr[1] - xr[0]))      # room for "White Mtns"
    w = 7.4
    fig = plt.figure(figsize=(w, w * (yr[1] - yr[0]) / (xr[1] - xr[0])), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    for f in json.loads((ne / "ne_110m_admin_0_countries.geojson").read_text())["features"]:
        if f["properties"].get("ADM0_A3") not in ("USA", "CAN", "MEX"):
            continue
        g = f["geometry"]
        for poly in [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]:
            ring = np.array(poly[0])
            ax.add_patch(Polygon(np.c_[to.transform(ring[:, 0], ring[:, 1])],
                                 fc="#eef2ef", ec="#b5b3ad", lw=0.8, zorder=1))
    segs = []
    for f in json.loads((ne / "ne_110m_admin_1_states_provinces_lines.geojson")
                        .read_text())["features"]:
        g = f["geometry"]
        for ln in [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]:
            a = np.array(ln)
            segs.append(np.c_[to.transform(a[:, 0], a[:, 1])])
    ax.add_collection(LineCollection(segs, colors="white", lw=1.0, zorder=2))
    r = pd.read_csv(gate1 / "results" / "t1_summary" / "regions.csv") \
        .set_index("region").drop("ALL", errors="ignore")
    hmax = r.walking_hours.max()
    for key, row in r.sort_values("walking_hours", ascending=False).iterrows():
        lon0, lat0, lon1, lat1 = regions.CANDIDATES[key][1]
        x, y = to.transform((lon0 + lon1) / 2, (lat0 + lat1) / 2)
        area = 40 + 1100 * row.walking_hours / hmax               # points^2
        ax.scatter(x, y, s=area, color="#5e8c75", alpha=0.85, edgecolor="white",
                   lw=1.2, zorder=3)
        side, dy = LABELS[key]
        r = np.sqrt(area / np.pi) + 4                     # clear the circle
        off, ha = {"left": ((-r, dy), "right"), "right": ((r, dy), "left"),
                   "above": ((0, r + 5), "center")}[side]
        ax.annotate(NAMES[key], (x, y), xytext=off, textcoords="offset points",
                    fontsize=12.5, ha=ha, va="center", color="#1c2321", zorder=4)
    ax.set_xlim(*xr)
    ax.set_ylim(*yr)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(OUT / "slide_map.png", transparent=True)
    plt.close(fig)
    print(f"slide_map.png: {w} x {fig.get_figheight():.2f} in")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    contours()
    data()
    slide_curve()
    slide_regions()
    slide_map()
