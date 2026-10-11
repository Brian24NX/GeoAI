#!/usr/bin/env python3
"""
T2 tier 1: the 1 m USGS 3DEP elevation under every walked trail, for any
region. Generalizes t2_prefetch_dem1m.py (White Mountains only):

- walked paths come from the combined T1 dataset (data/t1_all,
  `analysis_walk` segments, their matched paths), sampled every 10 m;
- the grid is the region's own NAD83 / UTM zone (regions.utm_epsg);
- 500 m x 500 m cells, 1 m pixels, every cell within 25 m of a walked path
  point, saved once as cache/dem1m/utm<zone>n_<x0>_<y0>.tif (the White
  Mountains' existing utm19n cells are reused as they are);
- one request at a time, 1 s apart; a stopped run resumes where it was.

The North Shore (Canada) is outside 3DEP's 1 m coverage and is skipped; T2
uses Canada's NRCan HRDEM there. Where 3DEP has no 1 m data (parts of
Olympic, Yosemite, the Gorge), the service mosaics coarser sources into the
1 m grid; t2_terrain1m.py flags those segments via t1_dem_quality.

Run:  python t2_dem1m.py --region <key> [--dry-run]
      python t2_dem1m.py --all [--dry-run]        (every US region)
"""

import argparse
import io
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import tifffile
from pyproj import Transformer

import regions

SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("cache/dem1m")
CELL_M, MARGIN_M, STEP_M = 500, 25, 10.0
URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/"
       "3DEPElevation/ImageServer/exportImage")
AGENT = {"User-Agent": "WashU-MVRL-travel-speed/0.2 (research)"}
PAUSE_S = 1.0
NOT_US = {"northshore"}
logging.getLogger("tifffile").setLevel(logging.ERROR)


def prefix(key):
    return f"utm{regions.utm_epsg(key) - 26900}n"


def path(key, x0, y0):
    return OUT / f"{prefix(key)}_{x0}_{y0}.tif"


def walked_points(key):
    """UTM x, y every STEP_M along every walking segment's matched path."""
    s = pd.read_parquet(SEG, columns=["region", "analysis_walk",
                                      "geometry_wkt"],
                        filters=[("region", "==", key)])
    s = s[s.analysis_walk]
    to_utm = Transformer.from_crs(4326, regions.utm_epsg(key),
                                  always_xy=True)
    xs, ys = [], []
    for wkt in s.geometry_wkt:
        body = wkt[wkt.index("(") + 1: wkt.rindex(")")]
        lon, lat = np.array([p.split() for p in body.split(",")],
                            dtype=float).T
        x, y = to_utm.transform(lon, lat)
        d = np.r_[0.0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
        t = np.arange(0.0, d[-1] + 1e-9, STEP_M) if d[-1] > 0 else [0.0]
        xs.append(np.interp(t, d, x))
        ys.append(np.interp(t, d, y))
    return np.concatenate(xs), np.concatenate(ys)


def cells(x, y):
    out = set()
    for dx in (-MARGIN_M, 0, MARGIN_M):
        for dy in (-MARGIN_M, 0, MARGIN_M):
            out |= set(zip((x + dx) // CELL_M * CELL_M,
                           (y + dy) // CELL_M * CELL_M))
    return sorted((int(a), int(c)) for a, c in out)


def fetch(key, x0, y0):
    """Download one cell (output link first, the image directly if the link
    fails); returns its share of no-data pixels."""
    epsg = regions.utm_epsg(key)
    params = {"bbox": f"{x0},{y0},{x0 + CELL_M},{y0 + CELL_M}",
              "bboxSR": epsg, "imageSR": epsg, "size": f"{CELL_M},{CELL_M}",
              "format": "tiff", "pixelType": "F32", "noData": -9999,
              "interpolation": "RSP_BilinearInterpolation",
              "adjustAspectRatio": "false"}
    try:
        r = requests.get(URL, params={**params, "f": "json"}, headers=AGENT,
                         timeout=120)
        r.raise_for_status()
        img = requests.get(r.json()["href"], headers=AGENT, timeout=120)
        img.raise_for_status()
        raw = img.content
    except (requests.RequestException, KeyError, ValueError):
        r = requests.get(URL, params={**params, "f": "image"}, headers=AGENT,
                         timeout=300)
        r.raise_for_status()
        raw = r.content
    if raw[:2] not in (b"II", b"MM"):
        raise ValueError("exportImage did not return a TIFF")
    a = tifffile.imread(io.BytesIO(raw))
    if a.shape != (CELL_M, CELL_M):
        raise ValueError(f"unexpected shape {a.shape}")
    tmp = path(key, x0, y0).with_suffix(".part")
    tmp.write_bytes(raw)
    tmp.rename(path(key, x0, y0))     # only complete files count as done
    return float((a < -1000).mean())


def fetch_all(key, todo, waits):
    failed, t0 = [], time.time()
    for i, (x0, y0) in enumerate(todo, 1):
        for attempt, wait in enumerate(waits):
            try:
                fetch(key, x0, y0)
                break
            except Exception as err:          # unattended: never crash
                if attempt == len(waits) - 1:
                    print(f"  FAILED {x0},{y0}: {type(err).__name__}: {err}",
                          flush=True)
                    failed.append((x0, y0))
                else:
                    time.sleep(wait)
        time.sleep(PAUSE_S)
        if i % 100 == 0 or i == len(todo):
            rate = (time.time() - t0) / i
            print(f"{time.strftime('%H:%M:%S')}  {key}: {i:,}/{len(todo):,} "
                  f"cells, {len(failed)} failed, "
                  f"~{rate * (len(todo) - i) / 60:.0f} min left", flush=True)
    return failed


def run(key, dry):
    x, y = walked_points(key)
    want = cells(x, y)
    todo = [c for c in want if not path(key, *c).exists()]
    print(f"{key}: {len(x):,} path points -> {len(want):,} cells "
          f"(~{len(want) * CELL_M ** 2 * 4 / 1e9:.2f} GB), "
          f"{len(todo):,} to fetch", flush=True)
    if dry or not todo:
        return {"region": key, "cells": len(want), "todo": len(todo),
                "failed": 0}
    OUT.mkdir(parents=True, exist_ok=True)
    failed = fetch_all(key, todo, waits=(10, 30, 60, 0))
    if failed:
        print(f"{key}: retrying {len(failed)} failed cells in 5 min",
              flush=True)
        time.sleep(300)
        failed = fetch_all(key, failed, waits=(60, 120, 300, 0))
    print(f"DEM1M {key}: {'DONE' if not failed else 'DONE WITH FAILURES'}",
          flush=True)
    return {"region": key, "cells": len(want), "todo": len(todo),
            "failed": len(failed)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    keys = a.region
    if a.all:
        built = set(pd.read_parquet(SEG, columns=["region"]).region)
        keys = [k for k in regions.CANDIDATES if k in built
                and k not in NOT_US]
    rows = [run(k, a.dry_run) for k in keys]
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    print(f"total: {df.cells.sum():,} cells (~{df.cells.sum() * 1e-3:.1f} "
          f"GB), {df.todo.sum():,} to fetch")
    if not a.dry_run:
        Path("results").mkdir(exist_ok=True)
        (Path("results") / "t2_dem1m_summary.json").write_text(
            json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
