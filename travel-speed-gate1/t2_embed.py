#!/usr/bin/env python3
"""
T2 tier 1 (pilot): AlphaEarth Foundations satellite embeddings (Google /
Google DeepMind, CC-BY 4.0) at each walking segment, from the free mirror
on Source Cooperative (data.source.coop/tge-labs/aef, no account).

The embeddings are 64 numbers per 10 m pixel per year, a summary of
Sentinel-2, Landsat, radar and more, learned by a frozen foundation model.
Tiles: 8192 x 8192 px Cloud-Optimized GeoTIFFs per UTM zone and year,
int8 (-128 = no data), stored "bottom-up" (positive y resolution; the
companion .vrt files don't resolve over HTTP, so the .tiff is read
directly; rasterio handles the orientation through the transform).
Dequantize: v = (q / 127.5)^2 * sign(q).

Per segment: the embedding at the midpoint of its matched path, for one
year (default 2022; the trails and forests change little year to year).
Only the image blocks under the walked trails are read (GDAL range
requests, cached in memory).

Input:  cache/aef/aef_index.parquet (the mirror's tile index, 78 MB)
        data/t1_all/segments_L50.parquet
Output: data/t2/aef<year>_<region>.parquet (segment_id + aef00..aef63)
Run:    python t2_embed.py --region wm [--year 2022]
Note:   these are location-rich features; in leave-one-region-out they
        must earn their keep on regions they never saw (plan: no location
        encoders).
"""

import argparse
import os
import time
from pathlib import Path

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tiff")
os.environ.setdefault("GDAL_CACHEMAX", "3000")          # MB of block cache
os.environ.setdefault("GDAL_HTTP_USERAGENT",
                      "WashU-MVRL-travel-speed/0.2 (research)")

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

INDEX = Path("cache/aef/aef_index.parquet")
SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t2")
HTTPS = "/vsicurl/https://data.source.coop/"


def midpoints(key):
    s = pd.read_parquet(SEG, columns=["region", "analysis_walk",
                                      "segment_id", "lat0", "lon0", "lat1",
                                      "lon1"],
                        filters=[("region", "==", key)])
    s = s[s.analysis_walk].reset_index(drop=True)
    return (s.segment_id.to_numpy(), ((s.lon0 + s.lon1) / 2).to_numpy(),
            ((s.lat0 + s.lat1) / 2).to_numpy())


def run(key, year):
    sid, lon, lat = midpoints(key)
    idx = pd.read_parquet(INDEX, columns=["path", "crs", "year",
                                          "wgs84_west", "wgs84_south",
                                          "wgs84_east", "wgs84_north",
                                          "utm_west", "utm_south",
                                          "utm_east", "utm_north"])
    idx = idx[(idx.year == year) & (idx.wgs84_east > lon.min())
              & (idx.wgs84_west < lon.max()) & (idx.wgs84_north > lat.min())
              & (idx.wgs84_south < lat.max())]
    emb = np.full((len(sid), 64), np.nan, dtype=np.float32)
    done = np.zeros(len(sid), bool)
    t0 = time.time()
    for row in idx.itertuples():
        to_utm = Transformer.from_crs(4326, row.crs, always_xy=True)
        x, y = to_utm.transform(lon, lat)
        m = (~done & (x >= row.utm_west) & (x < row.utm_east)
             & (y >= row.utm_south) & (y < row.utm_north))
        if not m.any():
            continue
        url = HTTPS + row.path.split("opendata.source.coop/", 1)[1]
        pts = np.nonzero(m)[0]
        with rasterio.open(url) as src:
            # visit points block by block so each block is fetched once
            r, c = rasterio.transform.rowcol(src.transform, x[pts], y[pts])
            order = np.lexsort((np.asarray(c) // 1024,
                                np.asarray(r) // 1024))
            pts = pts[order]
            vals = np.array(list(src.sample(zip(x[pts], y[pts]))),
                            dtype=np.float32)
        bad = (vals == -128).all(axis=1)
        vals = (vals / 127.5) ** 2 * np.sign(vals)
        vals[bad] = np.nan
        emb[pts] = vals
        done[pts] = ~bad
        print(f"  {key} {year}: {row.path.rsplit('/', 1)[1]}: "
              f"{len(pts):,} points, {time.time() - t0:.0f} s", flush=True)
    out = pd.DataFrame(emb, columns=[f"aef{i:02d}" for i in range(64)])
    out.insert(0, "segment_id", sid)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"aef{year}_{key}.parquet"
    out.to_parquet(f, index=False)
    print(f"wrote {f}: {len(out):,} segments, embedding for "
          f"{done.mean():.1%}, {time.time() - t0:.0f} s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", nargs="+", required=True)
    ap.add_argument("--year", type=int, default=2022)
    a = ap.parse_args()
    for k in a.region:
        run(k, a.year)


if __name__ == "__main__":
    main()
