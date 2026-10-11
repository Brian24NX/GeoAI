#!/usr/bin/env python3
"""
T2 step 1: download the 1 m USGS 3DEP elevation along every walked trail.

T1 used a 5 m elevation grid. T2 switches to 1 m (plan sec. 5): slope at
1 m, and surface roughness, which 5 m can't see. The White Mountains are
100% covered by 1 m lidar DEMs (Gate 1), but the whole forest at 1 m would
be ~5 billion pixels, so we only fetch the 500 m x 500 m cells that the
T1 hikes actually walked through (plus any cell within 25 m of a walked
point, so a buffer around a trail near a cell edge is never cut off).

Grid: NAD83 / UTM zone 19N (EPSG:26919), cells aligned to multiples of
500 m, 1 m pixels -> every cell is 500 x 500 and they tile one global grid.
Each cell is saved once in cache/dem1m/ as utm19n_<x0>_<y0>.tif (x0, y0 =
the south-west corner in meters; row 0 of the array is the north edge).
Re-running skips cells already on disk, so a stopped run just resumes.

Run after t1_build_dataset.py:  python t2_prefetch_dem1m.py [--dry-run]
"""

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

import t1_build_dataset as b
import t1_download as t1

DATA = Path("data/t1_white_mountains")
OUT = Path("cache/dem1m")
EPSG = 26919                  # NAD83 / UTM zone 19N (all of the WMNF)
CELL_M = 500                  # cell size (m); 500 x 500 pixels at 1 m
MARGIN_M = 25                 # also fetch cells within this of a walked point
URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/"
       "3DEPElevation/ImageServer/exportImage")
AGENT = {"User-Agent": "WashU-MVRL-travel-speed/0.2 (research)"}
PAUSE_S = 1.0                 # be polite: one request at a time, 1 s apart
logging.getLogger("tifffile").setLevel(logging.ERROR)


def walked_points():
    """UTM x, y of every map-matched trail point of every hiking trace."""
    b.init_layers(t1.REGION, t1.tiles())
    cls = np.array(b.W["cls"])
    p = pd.read_parquet(DATA / "points.parquet")
    tr = pd.read_csv(DATA / "traces.csv")
    p = p[p.trace_id.isin(set(tr.loc[tr.hiking_trace, "trace_id"]))
          & (p.way_index >= 0) & p.mlat.notna()]
    p = p[cls[p.way_index.to_numpy().astype(int)] == "trail"]
    to_utm = Transformer.from_crs(4326, EPSG, always_xy=True)
    return to_utm.transform(p.mlon.to_numpy(), p.mlat.to_numpy())


def cells(x, y):
    """South-west corners of every cell within MARGIN_M of a walked point."""
    out = set()
    for dx in (-MARGIN_M, 0, MARGIN_M):
        for dy in (-MARGIN_M, 0, MARGIN_M):
            out |= set(zip((x + dx) // CELL_M * CELL_M,
                           (y + dy) // CELL_M * CELL_M))
    return sorted((int(a), int(c)) for a, c in out)


def path(x0, y0):
    return OUT / f"utm19n_{x0}_{y0}.tif"


def read(x0, y0):
    """The cell as a float array (NaN = no data); row 0 is the north edge."""
    a = tifffile.imread(path(x0, y0)).astype(float)
    a[a < -1000] = np.nan
    return a


def fetch(x0, y0):
    """Download one cell; returns its share of no-data pixels."""
    params = {"bbox": f"{x0},{y0},{x0 + CELL_M},{y0 + CELL_M}",
              "bboxSR": EPSG, "imageSR": EPSG, "size": f"{CELL_M},{CELL_M}",
              "format": "tiff", "pixelType": "F32", "noData": -9999,
              "interpolation": "RSP_BilinearInterpolation",
              "adjustAspectRatio": "false", "f": "json"}
    r = requests.get(URL, params=params, headers=AGENT, timeout=120)
    r.raise_for_status()
    info = r.json()
    e = info["extent"]
    if abs(e["xmin"] - x0) > 0.01 or abs(e["ymax"] - y0 - CELL_M) > 0.01:
        raise ValueError(f"unexpected extent {e}")
    img = requests.get(info["href"], headers=AGENT, timeout=120)
    img.raise_for_status()
    a = tifffile.imread(io.BytesIO(img.content))
    if a.shape != (CELL_M, CELL_M):
        raise ValueError(f"unexpected shape {a.shape}")
    tmp = path(x0, y0).with_suffix(".part")
    tmp.write_bytes(img.content)
    tmp.rename(path(x0, y0))          # only complete files count as done
    return float((a < -1000).mean())


def fetch_all(todo, waits):
    """One pass over todo; returns (failed cells, {cell: no-data share})."""
    failed, nodata, t0 = [], {}, time.time()
    for i, (x0, y0) in enumerate(todo, 1):
        for attempt, wait in enumerate(waits):
            try:
                nodata[(x0, y0)] = fetch(x0, y0)
                break
            except Exception as err:   # unattended run: never crash
                if attempt == len(waits) - 1:
                    print(f"  FAILED {x0},{y0}: {type(err).__name__}: {err}",
                          flush=True)
                    failed.append((x0, y0))
                else:
                    time.sleep(wait)
        time.sleep(PAUSE_S)
        if i % 50 == 0 or i == len(todo):
            rate = (time.time() - t0) / i
            print(f"{time.strftime('%H:%M:%S')}  {i:,}/{len(todo):,} cells, "
                  f"{len(failed)} failed, ~{rate * (len(todo) - i) / 60:.0f}"
                  f" min left", flush=True)
    return failed, nodata


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="only count the cells")
    args = ap.parse_args()
    x, y = walked_points()
    want = cells(x, y)
    print(f"{len(x):,} walked trail points -> {len(want):,} cells of "
          f"{CELL_M} m (~{len(want) * CELL_M ** 2 * 4 / 1e9:.2f} GB)",
          flush=True)
    if args.dry_run:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(want, columns=["x0", "y0"]).to_csv(OUT / "cells.csv",
                                                   index=False)
    todo = [c for c in want if not path(*c).exists()]
    print(f"{len(want) - len(todo):,} already on disk, {len(todo):,} to "
          f"fetch", flush=True)
    start = time.time()
    failed, nodata = fetch_all(todo, waits=(10, 30, 60, 0))
    if failed:                         # second pass, slower, for the stragglers
        print(f"retrying {len(failed)} failed cells in 5 min", flush=True)
        time.sleep(300)
        failed, more = fetch_all(failed, waits=(60, 120, 300, 0))
        nodata.update(more)

    # check: does every walked point now have a 1 m elevation?
    have = {c for c in want if path(*c).exists()}
    cx, cy = x // CELL_M * CELL_M, y // CELL_M * CELL_M
    covered = np.array([(int(a), int(c)) in have for a, c in zip(cx, cy)])
    summary = {"cells_wanted": len(want), "cells_on_disk": len(have),
               "failed": [list(c) for c in failed],
               "cells_with_any_nodata": int(sum(v > 0 for v in
                                                nodata.values())),
               "walked_points_covered_pct": float(100 * covered.mean()),
               "gb_on_disk": sum(path(*c).stat().st_size for c in have) / 1e9,
               "minutes": (time.time() - start) / 60,
               "grid": f"EPSG:{EPSG}, {CELL_M} m cells, 1 m pixels",
               "margin_m": MARGIN_M, "source": URL}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("DEM1M DONE" if not failed else "DEM1M DONE WITH FAILURES")


if __name__ == "__main__":
    main()
