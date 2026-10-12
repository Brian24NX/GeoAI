#!/usr/bin/env python3
"""
T2 tier 1: terrain from the 1 m lidar DEM for every walking segment,
measured along the segment's own matched path (geometry_wkt). Piloted on
the White Mountains on 11 Oct (decision #83), then run for every region.

Each segment's path is resampled every 1 m and the 1 m DEM is read there
(bilinear). Per segment:
  slope_1m     (z_end - z_start) / length, from the 1 m DEM
  pitch_max    steepest 5 m pitch along the path, |dz| / 5 m
  pitch_sd     spread of the 5 m pitches (steps, short steep bits)
  relief_sd    SD of the profile around its 11 m moving average: rock
               steps, roots and water bars felt along the line of travel
  rough_mad    roughness: mean |DTM - DTM smoothed with a 2 m Gaussian| on
               the path
  rough_stride STRIDE's exact definition (Campbell, Cutler & Dennison
               2024; R package `stride`, gen_rgh): mean |DTM - DTM smoothed
               with a circular mean filter of 2 m radius|, here on the path
               (STRIDE averages it over 10 m pixels)
  cross_slope  mean side slope across the path (sidehill trails), from
               the smoothed DEM's gradient
  dem1m_cover  share of the path's points with 1 m data
Bare-earth DEM: rocks and roots show only where lidar ground points
resolve them (~1-2 m spacing), so these are lower bounds on roughness.

Input:  cache/dem1m/utm<zone>n_<x0>_<y0>.tif (t2_dem1m.py; 500 m cells,
        1 m pixels, row 0 = north edge)
        data/t1_all/segments_L50.parquet (walking segments' paths)
Output: data/t2/terrain1m_<region>.parquet (segment_id + covariates)
Run:    python t2_terrain1m.py --region <key> ...  |  --all
"""

import argparse
import logging
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
from pyproj import Transformer
from scipy.ndimage import convolve, gaussian_filter, map_coordinates

import regions

DEM = Path("cache/dem1m")
SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t2")
CELL = 500
SIGMA_M = 2.0                      # STRIDE: 2 m smoothing
NODATA_BELOW = -1000.0
CACHE_CELLS = 150                  # ~10 MB each in memory
_yy, _xx = np.mgrid[-2:3, -2:3]
DISK = ((_xx ** 2 + _yy ** 2) <= 4).astype(float)    # 2 m radius, 13 px
DISK /= DISK.sum()
logging.getLogger("tifffile").setLevel(logging.ERROR)


class Cells:
    """Lazily loaded 1 m cells: DEM, residual (DEM - smoothed), gradient."""

    def __init__(self, prefix):
        self.prefix = prefix
        self.cache = OrderedDict()

    def get(self, x0, y0):
        key = (x0, y0)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        f = DEM / f"{self.prefix}_{x0}_{y0}.tif"
        if not f.exists():
            val = None
        else:
            z = tifffile.imread(f).astype(np.float64)
            z[z < NODATA_BELOW] = np.nan
            filled = np.where(np.isnan(z), np.nanmean(z), z)
            sm = gaussian_filter(filled, SIGMA_M, mode="nearest")
            gy, gx = np.gradient(sm)          # per pixel = per meter
            val = {"z": z, "res": z - sm, "gx": gx, "gy": -gy,  # north = up
                   "resc": z - convolve(filled, DISK, mode="nearest")}
        self.cache[key] = val
        if len(self.cache) > CACHE_CELLS:
            self.cache.popitem(last=False)
        return val

    def sample(self, x, y, layer):
        """Bilinear sample of one layer at UTM points (NaN outside data)."""
        out = np.full(len(x), np.nan)
        cx = (np.floor(x / CELL) * CELL).astype(int)
        cy = (np.floor(y / CELL) * CELL).astype(int)
        for (a, b) in set(zip(cx, cy)):
            m = (cx == a) & (cy == b)
            c = self.get(a, b)
            if c is None:
                continue
            col = x[m] - a - 0.5
            row = (b + CELL) - y[m] - 0.5
            out[m] = map_coordinates(c[layer], [row, col], order=1,
                                     mode="nearest")
        return out


def parse(wkt):
    body = wkt[wkt.index("(") + 1: wkt.rindex(")")]
    xy = np.array([p.split() for p in body.split(",")], dtype=float)
    return xy[:, 0], xy[:, 1]


def resample(x, y, step=1.0):
    """Points every `step` m along the polyline, and its length."""
    d = np.r_[0.0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
    if d[-1] < 5:
        return None, None, d[-1]
    s = np.arange(0.0, d[-1] + 1e-9, step)
    return np.interp(s, d, x), np.interp(s, d, y), d[-1]


def tobler(s):
    return 6.0 * np.exp(-3.5 * np.abs(s + 0.05))


def profile_metrics(z, L):
    out = {"slope_1m": (z[-1] - z[0]) / L if L > 0 else np.nan}
    if len(z) >= 11:
        p = (z[5:] - z[:-5]) / 5.0
        out["pitch_max"] = float(np.nanmax(np.abs(p)))
        out["pitch_sd"] = float(np.nanstd(p))
        ma = np.convolve(z, np.ones(11) / 11, mode="valid")
        out["relief_sd"] = float(np.nanstd(z[5:-5] - ma))
        # hidden climbing: extra time a slope-speed curve (Tobler's, fixed,
        # so nothing is fitted on the data) predicts when the 50 m is walked
        # as 5 m pieces instead of at its average grade. A control: is the
        # profile's gain just uneven grade within the segment?
        q = (z[5::5] - z[:-5:5]) / 5.0
        if len(q) and np.isfinite(out["slope_1m"]):
            out["hidden_grade"] = float(np.mean(1 / tobler(q))
                                        * tobler(out["slope_1m"]) - 1)
    return out


def run(key):
    epsg = regions.utm_epsg(key)
    seg = pd.read_parquet(SEG, columns=["region", "analysis_walk",
                                        "segment_id", "geometry_wkt",
                                        "lat0", "lon0", "lat1", "lon1"],
                          filters=[("region", "==", key)])
    seg = seg[seg.analysis_walk].reset_index(drop=True)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    mx, my = to_utm.transform(((seg.lon0 + seg.lon1) / 2).to_numpy(),
                              ((seg.lat0 + seg.lat1) / 2).to_numpy())
    order = np.lexsort((np.floor(my / CELL), np.floor(mx / CELL)))
    cells, rows = Cells(f"utm{epsg - 26900}n"), []
    for n, i in enumerate(order):
        lon, lat = parse(seg.geometry_wkt.iat[i])
        x, y = to_utm.transform(lon, lat)
        x, y, L = resample(np.asarray(x), np.asarray(y))
        row = {"segment_id": seg.segment_id.iat[i]}
        if x is not None:
            z = cells.sample(x, y, "z")
            ok = np.isfinite(z)
            row["dem1m_cover"] = float(ok.mean())
            if ok.mean() >= 0.9:
                zz = pd.Series(z).interpolate(limit_direction="both")
                row.update(profile_metrics(zz.to_numpy(), L))
                row["rough_mad"] = float(np.nanmean(np.abs(
                    cells.sample(x, y, "res"))))
                row["rough_stride"] = float(np.nanmean(np.abs(
                    cells.sample(x, y, "resc"))))
                gx, gy = cells.sample(x, y, "gx"), cells.sample(x, y, "gy")
                tx, ty = np.gradient(x), np.gradient(y)
                norm = np.hypot(tx, ty)
                norm[norm == 0] = np.nan
                nx, ny = -ty / norm, tx / norm          # unit normal
                row["cross_slope"] = float(np.nanmean(np.abs(gx * nx
                                                             + gy * ny)))
        rows.append(row)
        if n % 20000 == 0:
            print(f"  {key}: {n:,} / {len(seg):,}", flush=True)
    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"terrain1m_{key}.parquet"
    out.to_parquet(f, index=False)
    print(f"wrote {f}: {len(out):,} segments; 1 m grid under >= 90% of "
          f"the path for {(out.dem1m_cover >= 0.9).mean():.1%}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    keys = a.region
    if a.all:
        have = {f.name.split("_")[0] for f in DEM.glob("utm*n_*.tif")}
        built = set(pd.read_parquet(SEG, columns=["region"]).region)
        keys = [k for k in regions.CANDIDATES if k in built
                and f"utm{regions.utm_epsg(k) - 26900}n" in have]
    for k in keys:
        run(k)


if __name__ == "__main__":
    main()
