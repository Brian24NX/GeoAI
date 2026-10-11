#!/usr/bin/env python3
"""
T1 step 1: download every OSM GPS trace in a region (default: the White
Mountains; any region in regions.py with --region <key>).

Each region is cut into tiles of at most 0.25 x 0.25 degrees (the API's
limit). The White Mountains: 43.80-44.50 N, 71.95-70.95 W, 12 tiles.

Step "trackpoints": each tile goes through the same paged download as Gate 1
(gate1_audit.download_box): every usable page, an exact count of the unusable
points, a sample of unusable pages, and the OSM ways. Then the usual Gate 1
summary is computed for the whole region (results/t1_white_mountains/).

Step "gpx": for every identifiable trace, fetch the ORIGINAL uploaded file
once from openstreetmap.org/trace/<id>/data. That gives whole hikes rather
than box-clipped pieces, the original sampling, elevation and the recording
app. Car-logging accounts are skipped.

Everything is cached (cache/t1_<region>/, cache/t1_gpx/), so the script
can be stopped and re-run at any time without downloading anything twice.

Run:   python t1_download.py                      (White Mountains, both steps)
       python t1_download.py --region cascades    (another region)
       python t1_download.py --step gpx           (only the full-GPX step)
"""

import argparse
import json
import os
import re
import time
from pathlib import Path

import pandas as pd

import gate1_audit as g
import regions

REGION = regions.region_name("wm")       # T1 v0 region (default)
WEST, SOUTH, EAST, NORTH = regions.CANDIDATES["wm"][1]
MAX_PAGES = 2000                         # read ALL usable pages per tile
DEEP_LIMIT = 800                         # the API times out paging deeper
                                         # (~page 906: "503 first byte
                                         # timeout"); a tile stopped there is
                                         # complete up to the API's limit
MAX_PASSES = 6                           # retry tiles stopped by network
RETRY_WAIT_S = 300                       #   errors, 5 min apart
                                         # (WM's busiest tile had 98; the
                                         # Gate 1 Boulder box had ~600)
GPX_DIR = Path("cache/t1_gpx")
TRACE_URL = "https://www.openstreetmap.org/trace/{}/data"
CAR_LOGGERS = {"sunnypilot", "dragonpilot", "openpilot", "frogpilot"}


def tiles(key="wm"):
    """Tiles named by row (south to north) and column (west to east)."""
    return regions.tiles(key)


def step_trackpoints(key="wm"):
    summary, table = g.audit_region(regions.region_name(key), tiles(key),
                                    cache_dir="cache", out_dir="results",
                                    max_pages=MAX_PAGES)
    return table


def _stopped(key):
    """{tile: page where its download stopped} from the region summary."""
    path = Path("results") / regions.region_name(key) / "summary.json"
    if not path.exists():
        return None
    out = {}
    for b in json.loads(path.read_text()).get("boxes", []):
        st = str(b.get("status", ""))
        if st.startswith("stopped"):
            m = re.search(r"page (\d+)", st)
            out[b["box"]] = int(m.group(1)) if m else -1
    return out


def incomplete_tiles(key):
    """Tiles whose download stopped on an error (network outage, server
    error) before the API's depth limit. Their pages so far are cached;
    another pass continues them."""
    st = _stopped(key)
    if st is None:
        return ["(no summary yet)"]
    return [t for t, page in st.items() if page < DEEP_LIMIT]


def capped_tiles(key):
    """Tiles cut by the API's depth limit: the newest ~4.5M points of the
    tile are in, the oldest uploads aren't reachable (a stated limit)."""
    st = _stopped(key) or {}
    return {t: page for t, page in st.items() if page >= DEEP_LIMIT}


def trace_id(url):
    m = re.search(r"/traces/(\d+)", url or "")
    return int(m.group(1)) if m else None


def step_gpx(table=None, key="wm"):
    """Fetch the original file of every identifiable, non-car trace."""
    import requests

    if table is None:
        table = pd.read_csv(Path("results") / regions.region_name(key)
                            / "traces.csv")
    ids = sorted({trace_id(u) for u, user in zip(table["url"], table["user"])
                  if isinstance(u, str) and str(user).lower() not in
                  CAR_LOGGERS and trace_id(u)})
    GPX_DIR.mkdir(parents=True, exist_ok=True)
    done = {int(p.name.split(".")[0]) for p in GPX_DIR.iterdir()
            if p.name.split(".")[0].isdigit()}
    todo = [i for i in ids if i not in done]
    print(f"\nFull GPX files: {len(ids)} identifiable traces (car loggers "
          f"skipped), {len(done)} already cached, {len(todo)} to fetch")
    failed = 0
    for n, tid in enumerate(todo, 1):
        try:
            r = requests.get(TRACE_URL.format(tid), timeout=120,
                             headers={"User-Agent": g.USER_AGENT})
        except requests.RequestException as err:
            print(f"  ! {tid}: {err.__class__.__name__}")
            failed += 1
            time.sleep(5)
            continue
        finally:
            time.sleep(g.REQUEST_DELAY_S)
        if r.status_code != 200:
            print(f"  ! {tid}: HTTP {r.status_code}")
            failed += 1
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
    return failed


def main():
    ap = argparse.ArgumentParser(description="T1: download the region")
    ap.add_argument("--step", choices=["all", "trackpoints", "gpx"],
                    default="all")
    ap.add_argument("--region", default="wm", choices=sorted(
        regions.CANDIDATES))
    args = ap.parse_args()
    w, s, e, n = regions.CANDIDATES[args.region][1]
    print(f"Region {regions.region_name(args.region)}: "
          f"{len(tiles(args.region))} tiles, {w}..{e} E, {s}..{n} N")
    table = None
    if args.step in ("all", "trackpoints"):
        for n in range(1, MAX_PASSES + 1):
            table = step_trackpoints(args.region)
            bad = incomplete_tiles(args.region)
            if not bad or n == MAX_PASSES:
                break
            print(f"\n{len(bad)} tiles stopped on errors ({', '.join(bad)});"
                  f" pass {n + 1} in {RETRY_WAIT_S // 60} min")
            time.sleep(RETRY_WAIT_S)
    if args.step in ("all", "gpx"):
        for n in range(1, MAX_PASSES + 1):
            if not step_gpx(table, args.region) or n == MAX_PASSES:
                break
            time.sleep(RETRY_WAIT_S)
    bad = incomplete_tiles(args.region)
    # the build queue waits for exactly this line
    print("\nT1 DOWNLOAD DONE" if not bad else
          f"\nT1 DOWNLOAD INCOMPLETE: {', '.join(bad)}")


if __name__ == "__main__":
    main()
