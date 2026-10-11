#!/usr/bin/env python3
"""
T2 tier 1: vegetation and land cover along every walking segment, from the
national 30 m Landsat-based maps (MRLC; US only, so the North Shore gets
none):
  - NLCD 2021 Tree Canopy Cover (USFS, % per pixel);
  - NLCD 2021 Land Cover (class per pixel).

Each T1 tile is fetched once per layer (WCS, ~30 m pixels, geographic) into
cache/layers/<tile>_{tcc,nlcd}2021.tif. Per segment, the layers are read
every 10 m along the matched path:
  tcc_mean, tcc_max         canopy cover (%) under the path
  lc_forest, lc_shrub,      share of the path in each land-cover group:
  lc_open, lc_developed,      forest 41-43; shrub 51-52; open = grass,
  lc_wet                      herbaceous, barren 31, 71-74; developed 21-24;
                              wet = water and wetlands 11, 90, 95

Output: data/t2/landcover_<region>.parquet (segment_id + covariates)
Run:    python t2_landcover.py --all  |  --region <key> ...
"""

import argparse
import logging
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import tifffile

import regions
from t2_terrain1m import parse

URL = "https://www.mrlc.gov/geoserver/mrlc_download/wcs"
LAYERS = {"tcc2021": "mrlc_download:nlcd_tcc_conus_2021_v2021-4",
          "nlcd2021": "mrlc_download:NLCD_2021_Land_Cover_L48"}
AGENT = {"User-Agent": "WashU-MVRL-travel-speed/0.2 (research)"}
CACHE = Path("cache/layers")
SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t2")
PX_M, STEP_M = 30.0, 10.0
NOT_US = {"northshore"}
GROUPS = {"lc_forest": {41, 42, 43}, "lc_shrub": {51, 52},
          "lc_open": {31, 71, 72, 73, 74}, "lc_developed": {21, 22, 23, 24},
          "lc_wet": {11, 90, 95}}
logging.getLogger("tifffile").setLevel(logging.ERROR)


def fetch(tile, layer):
    """One tile of one layer, cached; returns (array, (w, s, e, n))."""
    name, w, s, e, n = tile
    f = CACHE / f"{name}_{layer}.tif"
    if not f.exists():
        width = math.ceil((e - w) * 111_320 * math.cos(math.radians(
            (s + n) / 2)) / PX_M)
        height = math.ceil((n - s) * 111_132 / PX_M)
        params = {"service": "WCS", "version": "1.0.0",
                  "request": "GetCoverage", "coverage": LAYERS[layer],
                  "crs": "EPSG:4326", "bbox": f"{w},{s},{e},{n}",
                  "width": width, "height": height, "format": "GeoTIFF"}
        for attempt in range(4):
            try:
                r = requests.get(URL, params=params, headers=AGENT,
                                 timeout=300)
                r.raise_for_status()
                if r.content[:2] not in (b"II", b"MM"):
                    raise ValueError(r.text[:200])
                break
            except (requests.RequestException, ValueError):
                if attempt == 3:
                    raise
                time.sleep(30 * (attempt + 1))
        tmp = f.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.rename(f)
        time.sleep(1.0)
    return tifffile.imread(f), (w, s, e, n)


def sample(grids, lon, lat):
    """Nearest-pixel values at the points from the first tile holding each."""
    out = np.full(len(lon), np.nan)
    for a, (w, s, e, n) in grids:
        m = np.isnan(out) & (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        if not m.any():
            continue
        r = np.clip(((n - lat[m]) / (n - s) * a.shape[0]).astype(int), 0,
                    a.shape[0] - 1)
        c = np.clip(((lon[m] - w) / (e - w) * a.shape[1]).astype(int), 0,
                    a.shape[1] - 1)
        out[m] = a[r, c]
    return out


def densify(lon, lat):
    kx = 111_320 * math.cos(math.radians(float(np.mean(lat))))
    d = np.r_[0.0, np.cumsum(np.hypot(np.diff(lon) * kx,
                                      np.diff(lat) * 111_132))]
    t = np.arange(0.0, d[-1] + 1e-9, STEP_M) if d[-1] > 0 else [0.0]
    return np.interp(t, d, lon), np.interp(t, d, lat)


def run(key):
    seg = pd.read_parquet(SEG, columns=["region", "analysis_walk",
                                        "segment_id", "geometry_wkt"],
                          filters=[("region", "==", key)])
    seg = seg[seg.analysis_walk].reset_index(drop=True)
    rows = []
    if key not in NOT_US:
        tiles = regions.tiles(key)
        tcc = [fetch(t, "tcc2021") for t in tiles]
        lc = [fetch(t, "nlcd2021") for t in tiles]
        for sid, wkt in zip(seg.segment_id, seg.geometry_wkt):
            lon, lat = densify(*parse(wkt))
            c = sample(tcc, lon, lat)
            c[c > 100] = np.nan                       # 254/255: no data
            k = sample(lc, lon, lat)
            row = {"segment_id": sid,
                   "tcc_mean": float(np.nanmean(c)) if np.isfinite(c).any()
                   else np.nan,
                   "tcc_max": float(np.nanmax(c)) if np.isfinite(c).any()
                   else np.nan}
            ok = np.isfinite(k) & (k > 0) & (k < 250)
            for g, codes in GROUPS.items():
                row[g] = float(np.isin(k[ok], list(codes)).mean()) \
                    if ok.any() else np.nan
            rows.append(row)
    else:
        rows = [{"segment_id": sid} for sid in seg.segment_id]
    out = pd.DataFrame(rows)
    for col in ["tcc_mean", "tcc_max"] + list(GROUPS):
        if col not in out:
            out[col] = np.nan
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"landcover_{key}.parquet"
    out.to_parquet(f, index=False)
    print(f"wrote {f}: {len(out):,} segments; canopy for "
          f"{out.tcc_mean.notna().mean():.0%}, mean "
          f"{out.tcc_mean.mean():.0f}%; forest share "
          f"{out.lc_forest.mean():.0%}", flush=True)


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
