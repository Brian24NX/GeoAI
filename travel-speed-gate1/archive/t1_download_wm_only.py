#!/usr/bin/env python3
"""
T1 step 1: download every OSM GPS trace in the White Mountains region.

The region is the White Mountain National Forest (NH, with a strip of
Maine), 43.80-44.50 N, 71.95-70.95 W, cut into 12 tiles of 0.25 x 0.233
degrees (the API allows at most 0.25 degrees per side).

Step "trackpoints": each tile goes through the same paged download as Gate 1
(gate1_audit.download_box): every usable page, an exact count of the unusable
points, a sample of unusable pages, and the OSM ways. Then the usual Gate 1
summary is computed for the whole region (results/t1_white_mountains/).

Step "gpx": for every identifiable trace, fetch the ORIGINAL uploaded file
once from openstreetmap.org/trace/<id>/data. That gives whole hikes rather
than box-clipped pieces, the original sampling, elevation and the recording
app. Car-logging accounts are skipped.

Everything is cached (cache/t1_white_mountains/, cache/t1_gpx/), so the
script can be stopped and re-run at any time without downloading anything
twice.

Run:   python t1_download.py               (both steps)
       python t1_download.py --step gpx    (only the full-GPX step)
"""

import argparse
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

import gate1_audit as g

REGION = "t1_white_mountains"
WEST, SOUTH, EAST, NORTH = -71.95, 43.80, -70.95, 44.50
N_COLS, N_ROWS = 4, 3                    # 0.25 deg x 0.2333 deg tiles
MAX_PAGES = 600                          # read ALL usable pages per tile
GPX_DIR = Path("cache/t1_gpx")
TRACE_URL = "https://www.openstreetmap.org/trace/{}/data"
CAR_LOGGERS = {"sunnypilot", "dragonpilot", "openpilot", "frogpilot"}


def tiles():
    """The 12 tiles, named by row (south to north) and column (west to east)."""
    xs = np.linspace(WEST, EAST, N_COLS + 1)
    ys = np.linspace(SOUTH, NORTH, N_ROWS + 1)
    return [(f"wm_r{r}_c{c}", float(round(xs[c], 4)), float(round(ys[r], 4)),
             float(round(xs[c + 1], 4)), float(round(ys[r + 1], 4)))
            for r in range(N_ROWS) for c in range(N_COLS)]


def step_trackpoints():
    summary, table = g.audit_region(REGION, tiles(), cache_dir="cache",
                                    out_dir="results", max_pages=MAX_PAGES)
    return table


def trace_id(url):
    m = re.search(r"/traces/(\d+)", url or "")
    return int(m.group(1)) if m else None


def step_gpx(table=None):
    """Fetch the original file of every identifiable, non-car trace."""
    import requests

    if table is None:
        table = pd.read_csv(Path("results") / REGION / "traces.csv")
    ids = sorted({trace_id(u) for u, user in zip(table["url"], table["user"])
                  if isinstance(u, str) and str(user).lower() not in
                  CAR_LOGGERS and trace_id(u)})
    GPX_DIR.mkdir(parents=True, exist_ok=True)
    done = {int(p.name.split(".")[0]) for p in GPX_DIR.iterdir()
            if p.name.split(".")[0].isdigit()}
    todo = [i for i in ids if i not in done]
    print(f"\nFull GPX files: {len(ids)} identifiable traces (car loggers "
          f"skipped), {len(done)} already cached, {len(todo)} to fetch")
    for n, tid in enumerate(todo, 1):
        try:
            r = requests.get(TRACE_URL.format(tid), timeout=120,
                             headers={"User-Agent": g.USER_AGENT})
        except requests.RequestException as err:
            print(f"  ! {tid}: {err.__class__.__name__}")
            time.sleep(5)
            continue
        finally:
            time.sleep(g.REQUEST_DELAY_S)
        if r.status_code != 200:
            print(f"  ! {tid}: HTTP {r.status_code}")
            continue
        # keep the original format: plain GPX, gzip, bzip2, zip or tar
        ctype = r.headers.get("Content-Type", "")
        disp = r.headers.get("Content-Disposition", "")
        name = re.search(r'filename="?([^";]+)', disp)
        ext = ".gpx"
        if name and "." in name.group(1):
            ext = "." + ".".join(name.group(1).split(".")[1:])[-12:]
        elif "gzip" in ctype:
            ext = ".gpx.gz"
        path = GPX_DIR / f"{tid}{ext}"
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(r.content)
        os.replace(tmp, path)
        if n % 25 == 0 or n == len(todo):
            print(f"  {n}/{len(todo)} fetched")


def main():
    ap = argparse.ArgumentParser(description="T1: download the region")
    ap.add_argument("--step", choices=["all", "trackpoints", "gpx"],
                    default="all")
    args = ap.parse_args()
    print(f"Region {REGION}: {len(tiles())} tiles, "
          f"{WEST}..{EAST} E, {SOUTH}..{NORTH} N")
    table = None
    if args.step in ("all", "trackpoints"):
        table = step_trackpoints()
    if args.step in ("all", "gpx"):
        step_gpx(table)
    print("\nT1 DOWNLOAD DONE")


if __name__ == "__main__":
    main()
