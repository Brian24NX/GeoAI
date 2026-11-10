#!/usr/bin/env python3
"""
Idea 1 (decision #131): does terrain still predict hiking speed when the
elevation data is coarse? Outside the US and parts of Europe, the free
elevation data is ~30 m (Copernicus GLO-30, SRTM); USGS's seamless US
layer is ~10 m. Here the 5 m USGS grids that t2_terrain5m.py reads are
block-averaged to 10 m (2 x 2 pixels) and 30 m (6 x 6 pixels), and the
same along-path measures are read from the coarse grids. Block averages
change the resolution only: real global DEMs also carry radar and canopy
errors, so this is a best case for them.

Per segment and resolution r in {10, 30} (bilinear along the matched
path, every 1 m, exactly as t2_terrain5m.py does at 5 m):
  slope_<r>m          (z_end - z_start) / length: the slope a <r> m DEM
                      gives (t3_harness.py --slope-from swaps it in for
                      T1's 5 m slope)
  pitch_max_<r>m, pitch_sd_<r>m, relief_sd_<r>m, hidden_grade_<r>m
                      as in t2_terrain1m.py
  cross_slope_<r>m    side slope from the gradient after the same 10 m
                      smoothing (at 30 m that is a third of a pixel)
Aspect and curvature (listed in the plan, never tested), from the 5 m grid
smoothed with a 25 m Gaussian, so they describe the hillside, not the
trail bed:
  northness_5m, eastness_5m   mean cos / sin of the aspect (the downhill
                      direction) along the path; on flat ground (< 2%
                      grade) both shrink toward 0
  curv_5m             mean curvature along the path (Laplacian, per
                      100 m): < 0 convex (ridges, spurs), > 0 concave
                      (valleys, hollows)

Check: --check <region> recomputes the 5 m measures with this code and
compares them with data/t2/terrain5m_<region>.parquet (they must match),
and this code's 5 m slope with T1's slope column.

Output: data/t2/terrain10m_<region>.parquet, terrain30m_<region>.parquet,
        aspcurv5m_<region>.parquet (segment_id + columns)
Run:    python t2_terrain_coarse.py --region <key> ...  |  --all
        [--workers 8]  |  --check <region>
"""

import argparse
import json
import logging
import math
import warnings
from collections import OrderedDict
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
from pyproj import Transformer
from scipy.ndimage import gaussian_filter, map_coordinates

import regions
from t2_terrain1m import parse, profile_metrics, resample

LAYERS = Path("cache/layers")
SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t2")
RES = {10: 2, 30: 6}       # target resolution (m): block size in 5 m pixels
SIGMA_5M = 2.0             # gradient smoothing in 5 m pixels (~10 m), as in
                           # t2_terrain5m.py; at block size f it is 2.0 / f
HILL_SIGMA_5M = 5.0        # aspect and curvature: ~25 m
FLAT = 0.02                # aspect is undefined on flat ground
MIN_COVER = 0.9            # share of the path with elevation, as before
CACHE_PIECES = 6
PROFILE = ["slope", "pitch_max", "pitch_sd", "relief_sd", "hidden_grade",
           "cross_slope"]
HILL = ["northness_5m", "eastness_5m", "curv_5m"]
logging.getLogger("tifffile").setLevel(logging.ERROR)


def block_mean(z, f):
    """Mean of f x f blocks, ignoring missing pixels; the last row and
    column of blocks may be partial."""
    if f == 1:
        return z
    rows, cols = z.shape
    R, C = -(-rows // f), -(-cols // f)
    p = np.full((R * f, C * f), np.nan)
    p[:rows, :cols] = z
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-missing blocks
        return np.nanmean(p.reshape(R, f, C, f), axis=(1, 3))


def gradient(z, px, py, sigma):
    """Gradient (east, north) per meter after Gaussian smoothing (sigma in
    pixels); missing pixels are filled with the mean first, as in
    t2_terrain5m.py."""
    filled = np.where(np.isnan(z), np.nanmean(z), z)
    sm = gaussian_filter(filled, sigma, mode="nearest")
    gr, gc = np.gradient(sm)
    return gc / px, -gr / py


class Pieces:
    """The region's 5 m pieces (lazily loaded) and every layer read here:
    name -> (array, block size in 5 m pixels)."""

    def __init__(self, key, check=False):
        stem = f"{regions.region_name(key)}_{key}_r"
        self.files = sorted(LAYERS.glob(stem + "*_dem5m.tif"))
        self.ext = [json.loads(f.with_suffix(".json").read_text())
                    for f in self.files]
        self.check = check
        self.cache = OrderedDict()

    def get(self, i):
        if i in self.cache:
            self.cache.move_to_end(i)
            return self.cache[i]
        z = tifffile.imread(self.files[i]).astype(np.float64)
        z[z < -1000] = np.nan
        e = self.ext[i]
        rows, cols = z.shape
        lat = (e["ymin"] + e["ymax"]) / 2
        px = (e["xmax"] - e["xmin"]) / cols * 111_320 * math.cos(
            math.radians(lat))                   # m per column
        py = (e["ymax"] - e["ymin"]) / rows * 111_132   # m per row
        lay = {"shape": (rows, cols), "z5": (z, 1)}
        if self.check:
            gx, gy = gradient(z, px, py, SIGMA_5M)
            lay.update({"gx5": (gx, 1), "gy5": (gy, 1)})
        else:
            for r, f in RES.items():
                zc = block_mean(z, f)
                gx, gy = gradient(zc, px * f, py * f, SIGMA_5M / f)
                lay.update({f"z{r}": (zc, f), f"gx{r}": (gx, f),
                            f"gy{r}": (gy, f)})
            hx, hy = gradient(z, px, py, HILL_SIGMA_5M)
            lap = (np.gradient(hx, axis=1) / px
                   - np.gradient(hy, axis=0) / py)   # d/dx east + d/dy north
            lay.update({"hx": (hx, 1), "hy": (hy, 1), "lap": (lap, 1)})
        self.cache[i] = lay
        if len(self.cache) > CACHE_PIECES:
            self.cache.popitem(last=False)
        return lay

    def sample(self, lon, lat, layer):
        """Bilinear sample of one layer (NaN outside the data)."""
        out = np.full(len(lon), np.nan)
        for i, e in enumerate(self.ext):
            m = (np.isnan(out) & (lon >= e["xmin"]) & (lon <= e["xmax"])
                 & (lat >= e["ymin"]) & (lat <= e["ymax"]))
            if not m.any():
                continue
            lay = self.get(i)
            a, f = lay[layer]
            rows, cols = lay["shape"]
            c = (lon[m] - e["xmin"]) / (e["xmax"] - e["xmin"]) * cols / f - 0.5
            r = (e["ymax"] - lat[m]) / (e["ymax"] - e["ymin"]) * rows / f - 0.5
            out[m] = map_coordinates(a, [r, c], order=1, mode="nearest")
        return out


def profile(pieces, plon, plat, x, y, L, r):
    """The along-path measures from the resolution-r layers."""
    z = pieces.sample(plon, plat, f"z{r}")
    if np.isfinite(z).mean() < MIN_COVER:
        return {}
    zz = pd.Series(z).interpolate(limit_direction="both").to_numpy()
    pm = profile_metrics(zz, L)
    row = {("slope" if k == "slope_1m" else k) + f"_{r}m": v
           for k, v in pm.items()}
    gx = pieces.sample(plon, plat, f"gx{r}")
    gy = pieces.sample(plon, plat, f"gy{r}")
    tx, ty = np.gradient(x), np.gradient(y)
    norm = np.hypot(tx, ty)
    norm[norm == 0] = np.nan
    row[f"cross_slope_{r}m"] = float(np.nanmean(np.abs(
        gx * (-ty / norm) + gy * (tx / norm))))
    return row


def hillside(pieces, plon, plat):
    """Aspect and curvature along the path (5 m grid, 25 m smoothing)."""
    if np.isfinite(pieces.sample(plon, plat, "z5")).mean() < MIN_COVER:
        return {}
    hx = pieces.sample(plon, plat, "hx")
    hy = pieces.sample(plon, plat, "hy")
    g = np.maximum(np.hypot(hx, hy), FLAT)
    return {"northness_5m": float(np.nanmean(-hy / g)),   # downhill = north
            "eastness_5m": float(np.nanmean(-hx / g)),
            "curv_5m": float(np.nanmean(pieces.sample(plon, plat, "lap"))
                             * 100)}


def run(key, check=False):
    epsg = regions.utm_epsg(key)
    seg = pd.read_parquet(SEG, columns=["region", "analysis_walk",
                                        "segment_id", "geometry_wkt",
                                        "lat0", "lon0", "slope"],
                          filters=[("region", "==", key)])
    seg = seg[seg.analysis_walk].reset_index(drop=True)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    to_geo = Transformer.from_crs(epsg, 4326, always_xy=True)
    pieces = Pieces(key, check)
    # visit segments piece by piece so each grid is loaded about once
    owner = np.full(len(seg), len(pieces.ext))
    for i, e in enumerate(pieces.ext):
        m = ((owner == len(pieces.ext)) & (seg.lon0 >= e["xmin"])
             & (seg.lon0 <= e["xmax"]) & (seg.lat0 >= e["ymin"])
             & (seg.lat0 <= e["ymax"])).to_numpy()
        owner[m] = i
    cols = ({"check": [f"{c}_5m" for c in PROFILE] + ["slope_t1"]} if check
            else {**{f"terrain{r}m": [f"{c}_{r}m" for c in PROFILE]
                     for r in RES}, "aspcurv5m": HILL})
    out = {p: [] for p in cols}
    for n, i in enumerate(np.argsort(owner, kind="stable")):
        lon, lat = parse(seg.geometry_wkt.iat[i])
        x, y = to_utm.transform(lon, lat)
        x, y, L = resample(np.asarray(x), np.asarray(y))
        rows = {p: {"segment_id": seg.segment_id.iat[i]} for p in cols}
        if x is not None:
            plon, plat = to_geo.transform(x, y)
            plon, plat = np.asarray(plon), np.asarray(plat)
            if check:
                rows["check"].update(profile(pieces, plon, plat, x, y, L, 5))
                rows["check"]["slope_t1"] = seg.slope.iat[i]
            else:
                for r in RES:
                    rows[f"terrain{r}m"].update(
                        profile(pieces, plon, plat, x, y, L, r))
                rows["aspcurv5m"].update(hillside(pieces, plon, plat))
        for p in cols:
            out[p].append(rows[p])
        if n % 20000 == 0:
            print(f"  {key}: {n:,} / {len(seg):,}", flush=True)
    frames = {p: pd.DataFrame(out[p]).reindex(columns=["segment_id"] + c)
              for p, c in cols.items()}             # same columns everywhere
    if check:
        return frames["check"]
    OUT.mkdir(parents=True, exist_ok=True)
    msg = []
    for p, df in frames.items():
        f = OUT / f"{p}_{key}.parquet"
        df.to_parquet(f, index=False)
        msg.append(f"{f.name} {df.iloc[:, 1].notna().mean():.1%}")
    return f"{key}: {len(seg):,} segments; " + ", ".join(msg)


def check(key):
    """This code at 5 m must reproduce t2_terrain5m.py's columns."""
    new = run(key, check=True)
    old = pd.read_parquet(OUT / f"terrain5m_{key}.parquet")
    m = old.merge(new, on="segment_id", suffixes=("_old", "_new"))
    print(f"{key}: {len(old):,} old rows, {len(new):,} new, {len(m):,} "
          "matched")
    for c in ["pitch_max_5m", "pitch_sd_5m", "relief_sd_5m",
              "hidden_grade_5m", "cross_slope_5m"]:
        a, b = m[c + "_old"], m[c + "_new"]
        both = a.notna() & b.notna()
        print(f"  {c:16s} missing in the same rows: "
              f"{(a.isna() == b.isna()).mean():.4f}; max |diff| "
              f"{(a - b)[both].abs().max():.2e}")
    ok = m.slope_5m.notna() & m.slope_t1.notna()
    d = (m.slope_5m - m.slope_t1)[ok]
    print(f"  slope_5m vs T1 slope: r {np.corrcoef(m.slope_5m[ok], m.slope_t1[ok])[0, 1]:.4f}, "
          f"median |diff| {d.abs().median():.4f}, 90th pct "
          f"{d.abs().quantile(0.9):.4f} (grade)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--check", metavar="REGION",
                    help="compare this code at 5 m with terrain5m_<REGION>")
    a = ap.parse_args()
    if a.check:
        check(a.check)
        return
    keys = a.region
    if a.all:
        built = set(pd.read_parquet(SEG, columns=["region"]).region)
        keys = [k for k in regions.CANDIDATES if k in built]
    if a.workers > 1:
        with Pool(a.workers) as pool:
            for msg in pool.imap_unordered(run, keys):
                print(msg, flush=True)
    else:
        for k in keys:
            print(run(k), flush=True)


if __name__ == "__main__":
    main()
