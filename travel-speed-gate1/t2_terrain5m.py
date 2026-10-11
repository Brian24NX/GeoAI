#!/usr/bin/env python3
"""
T2: the same along-path terrain profile as t2_terrain1m.py, but read from
the 5 m USGS grids that T1 already cached for every region
(cache/layers/<region>_<tile>_q<ij>_dem5m.tif, geographic, row 0 north).

Why: (1) it runs for all 17 regions today, while the 1 m cells download
(decision #84), so terrain can face the leave-one-region-out test now;
(2) next to the 1 m version in the White Mountains it shows how much of
the gain needs 1 m lidar and how much any good DEM gives.

Per segment, along its matched path every 1 m (bilinear on the 5 m grid):
  pitch_max_5m, pitch_sd_5m, relief_sd_5m,
  hidden_grade_5m                           as in t2_terrain1m.py
  cross_slope_5m                            side slope from the 5 m grid's
                                            gradient (10 m smoothing)
STRIDE's roughness needs 1 m; it has no 5 m version here.

Output: data/t2/terrain5m_<region>.parquet (segment_id + covariates)
Run:    python t2_terrain5m.py --region <key> ...  |  --all
"""

import argparse
import json
import logging
import math
from collections import OrderedDict
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
CACHE_PIECES = 12
logging.getLogger("tifffile").setLevel(logging.ERROR)


class Pieces:
    """The region's 5 m pieces (lazily loaded): DEM and its gradient."""

    def __init__(self, key):
        stem = f"{regions.region_name(key)}_{key}_r"
        self.files = sorted(LAYERS.glob(stem + "*_dem5m.tif"))
        self.ext = [json.loads(f.with_suffix(".json").read_text())
                    for f in self.files]
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
        filled = np.where(np.isnan(z), np.nanmean(z), z)
        sm = gaussian_filter(filled, 2.0, mode="nearest")   # ~10 m
        gr, gc = np.gradient(sm)
        val = {"z": z, "gx": gc / px, "gy": -gr / py}       # east, north
        self.cache[i] = val
        if len(self.cache) > CACHE_PIECES:
            self.cache.popitem(last=False)
        return val

    def sample(self, lon, lat, layer):
        out = np.full(len(lon), np.nan)
        for i, e in enumerate(self.ext):
            m = (np.isnan(out) & (lon >= e["xmin"]) & (lon <= e["xmax"])
                 & (lat >= e["ymin"]) & (lat <= e["ymax"]))
            if not m.any():
                continue
            a = self.get(i)[layer]
            rows, cols = a.shape
            c = (lon[m] - e["xmin"]) / (e["xmax"] - e["xmin"]) * cols - 0.5
            r = (e["ymax"] - lat[m]) / (e["ymax"] - e["ymin"]) * rows - 0.5
            out[m] = map_coordinates(a, [r, c], order=1, mode="nearest")
        return out


def run(key):
    epsg = regions.utm_epsg(key)
    seg = pd.read_parquet(SEG, columns=["region", "analysis_walk",
                                        "segment_id", "geometry_wkt",
                                        "lat0", "lon0"],
                          filters=[("region", "==", key)])
    seg = seg[seg.analysis_walk].reset_index(drop=True)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    to_geo = Transformer.from_crs(epsg, 4326, always_xy=True)
    pieces = Pieces(key)
    # visit segments piece by piece so each grid is loaded about once
    owner = np.full(len(seg), len(pieces.ext))
    for i, e in enumerate(pieces.ext):
        m = ((owner == len(pieces.ext)) & (seg.lon0 >= e["xmin"])
             & (seg.lon0 <= e["xmax"]) & (seg.lat0 >= e["ymin"])
             & (seg.lat0 <= e["ymax"])).to_numpy()
        owner[m] = i
    rows = []
    for n, i in enumerate(np.argsort(owner, kind="stable")):
        lon, lat = parse(seg.geometry_wkt.iat[i])
        x, y = to_utm.transform(lon, lat)
        x, y, L = resample(np.asarray(x), np.asarray(y))
        row = {"segment_id": seg.segment_id.iat[i]}
        if x is not None:
            plon, plat = to_geo.transform(x, y)
            plon, plat = np.asarray(plon), np.asarray(plat)
            z = pieces.sample(plon, plat, "z")
            if np.isfinite(z).mean() >= 0.9:
                zz = pd.Series(z).interpolate(limit_direction="both")
                pm = profile_metrics(zz.to_numpy(), L)
                row.update({f"{k}_5m": v for k, v in pm.items()
                            if k != "slope_1m"})
                gx = pieces.sample(plon, plat, "gx")
                gy = pieces.sample(plon, plat, "gy")
                tx, ty = np.gradient(x), np.gradient(y)
                norm = np.hypot(tx, ty)
                norm[norm == 0] = np.nan
                row["cross_slope_5m"] = float(np.nanmean(np.abs(
                    gx * (-ty / norm) + gy * (tx / norm))))
        rows.append(row)
        if n % 20000 == 0:
            print(f"  {key}: {n:,} / {len(seg):,}", flush=True)
    out = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"terrain5m_{key}.parquet"
    out.to_parquet(f, index=False)
    print(f"wrote {f}: {len(out):,} segments, profile for "
          f"{out.pitch_sd_5m.notna().mean():.1%}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    keys = a.region
    if a.all:
        built = set(pd.read_parquet(SEG, columns=["region"]).region)
        keys = [k for k in regions.CANDIDATES if k in built]
    for k in keys:
        run(k)


if __name__ == "__main__":
    main()
