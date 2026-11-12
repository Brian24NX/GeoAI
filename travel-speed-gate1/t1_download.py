#!/usr/bin/env python3
"""
T1 step 1: download every OSM GPS trace in a region (default: the White
Mountains; any region in regions.py with --region <key>).

Each region is cut into tiles of at most 0.25 x 0.25 degrees (the API's
limit). The White Mountains: 43.80-44.50 N, 71.95-70.95 W, 12 tiles.

Step "pages": download every usable page of every tile. A tile the API
can't answer (the query times out after 30 s: too many points in the box,
or paging too deep) is split into its 4 quarters (<tile>_q0 SW, _q1 SE,
_q2 NW, _q3 NE), and those again if needed, down to SPLIT_MIN_DEG. The
splits are kept in cache/<region>/splits.json; the builder reads the same
boxes and rejoins anonymous pieces cut at the new edges. (Added 11 Nov 2026,
decision #135: the Bay Area's tiles time out even on page 0, and 4 tiles
elsewhere timed out before their oldest uploads.)

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
       python t1_download.py --region bayarea --max-gb 8 \
              --budget-file logs/redownload_bytes.json   (size cap shared by
                                                          several runs)
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
                                         # (the API times out long before:
                                         # ~page 906 in quiet areas, page 0
                                         # in the Bay Area; then we split)
MAX_PASSES = 6                           # full-GPX step: retry failed
RETRY_WAIT_S = 300                       #   files, 5 min apart; the pages
                                         #   step retries network errors
                                         #   the same way
SPLIT_MIN_DEG = 0.01                     # quarters no smaller than ~1 km
MAX_ROUNDS = 12                          # page rounds (splits + retries)
GPX_DIR = Path("cache/t1_gpx")
TRACE_URL = "https://www.openstreetmap.org/trace/{}/data"
CAR_LOGGERS = {"sunnypilot", "dragonpilot", "openpilot", "frogpilot"}


def tiles(key="wm"):
    """Tiles named by row (south to north) and column (west to east)."""
    return regions.tiles(key)


class SizeCap(Exception):
    """The run reached the size cap Brian approved (--max-gb)."""


BUDGET = {}                              # set by main() when --max-gb given


def check_budget():
    """Add this run's bytes to the shared budget file; stop at the cap."""
    if not BUDGET:
        return
    used = BUDGET["start"] + g.DOWNLOADED_BYTES
    tmp = BUDGET["file"].with_suffix(".tmp")
    tmp.write_text(json.dumps({"bytes": used}))
    os.replace(tmp, BUDGET["file"])
    if used > BUDGET["cap"]:
        raise SizeCap(f"{used / 1e9:.2f} GB downloaded, cap "
                      f"{BUDGET['cap'] / 1e9:.1f} GB")


def splits_file(region):
    return Path("cache") / region / "splits.json"


def load_splits(region):
    path = splits_file(region)
    return json.loads(path.read_text()) if path.exists() else {}


def save_splits(region, splits):
    tmp = splits_file(region).with_suffix(".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(splits, indent=1))
    os.replace(tmp, splits_file(region))


def quarters(box):
    """The 4 quarters of a box: _q0 SW, _q1 SE, _q2 NW, _q3 NE."""
    name, w, s, e, n = box
    mx, my = round((w + e) / 2, 6), round((s + n) / 2, 6)
    return [(f"{name}_q0", w, s, mx, my), (f"{name}_q1", mx, s, e, my),
            (f"{name}_q2", w, my, mx, n), (f"{name}_q3", mx, my, e, n)]


def leaf_boxes(region, boxes):
    """The boxes the API pages come from: each tile, or its quarters
    (recursively) where the tile was split (cache/<region>/splits.json).
    Elevation and OSM ways stay per tile."""
    splits, out = load_splits(region), []

    def walk(box):
        if box[0] in splits:
            for q in quarters(box):
                walk(q)
        else:
            out.append(box)
    for b in boxes:
        walk(b)
    return out


def _stop_page(status):
    m = re.search(r"page (\d+)", status)
    return int(m.group(1)) if m else -1


def step_pages(key="wm"):
    """Download every usable page of every box, splitting boxes the API
    can't answer (see the top of the file). Pages only, no parsing."""
    region = regions.region_name(key)
    splits, last_failed = load_splits(region), {}
    for rnd in range(1, MAX_ROUNDS + 1):
        boxes = leaf_boxes(region, tiles(key))
        split, failed, capped, pages = [], {}, [], 0
        for box in boxes:
            _, info, _ = g.download_box(
                "cache", region, box, max_pages=MAX_PAGES,
                count_untimed=not re.search(r"_q\d$", box[0]))
            check_budget()
            pages += info["usable_pages_used"]
            st = str(info["status"])
            if info["usable_part_complete"] or not (
                    st.startswith("stopped") or st.startswith("usable part")):
                continue
            page = _stop_page(st)
            # too heavy for the API: a timeout, the page cap, or the same
            # page failing twice in a row
            heavy = st.endswith("timeout") or st.startswith("usable part") \
                or last_failed.get(box[0]) == page
            side = min(box[3] - box[1], box[4] - box[2])
            if heavy and side / 2 >= SPLIT_MIN_DEG:
                splits[box[0]] = f"{time.strftime('%Y-%m-%d')}: {st}"
                save_splits(region, splits)
                split.append(box[0])
            elif heavy:
                capped.append(box[0])
            else:
                failed[box[0]] = page
        print(f"\nRound {rnd}: {len(boxes)} boxes, {pages:,} usable pages; "
              f"split {len(split)}, network errors {len(failed)}, "
              f"capped {len(capped)} ({g.DOWNLOADED_BYTES / 1e9:.2f} GB "
              f"this run)", flush=True)
        if split:
            print(f"  split into quarters: {', '.join(split)}")
        if failed:
            print(f"  network errors: {failed}")
        if capped:
            print(f"  capped (smallest box still times out): "
                  f"{', '.join(capped)}")
        if not split and not failed:
            return
        last_failed = failed
        if not split:
            print(f"  next round in {RETRY_WAIT_S // 60} min", flush=True)
            time.sleep(RETRY_WAIT_S)


def step_trackpoints(key="wm"):
    region = regions.region_name(key)
    summary, table = g.audit_region(region, leaf_boxes(region, tiles(key)),
                                    cache_dir="cache", out_dir="results",
                                    max_pages=MAX_PAGES)
    return table


def _stopped(key):
    """{box: (page, status)} for boxes whose usable part is incomplete, from
    the region summary (a box that stopped later, while counting untimed
    points, has all its usable pages)."""
    path = Path("results") / regions.region_name(key) / "summary.json"
    if not path.exists():
        return None
    out = {}
    for b in json.loads(path.read_text()).get("boxes", []):
        st = str(b.get("status", ""))
        if (st.startswith("stopped") or st.startswith("usable part")) and \
                not b.get("usable_part_complete"):
            out[b["box"]] = (_stop_page(st), st)
    return out


def incomplete_tiles(key):
    """Boxes stopped by a network error (not the API's query limit): their
    pages so far are cached; another run continues."""
    st = _stopped(key)
    if st is None:
        return ["(no summary yet)"]
    return [t for t, (page, s) in st.items()
            if not (s.endswith("timeout") or s.startswith("usable part"))]


def capped_tiles(key):
    """Boxes cut by the API's limits even at the smallest split: the newest
    uploads are in, the oldest aren't reachable. A stated limitation, on the
    data card. ({box: page where it stopped})"""
    st = _stopped(key) or {}
    return {t: page for t, (page, s) in st.items()
            if s.endswith("timeout") or s.startswith("usable part")}


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
        g.DOWNLOADED_BYTES += len(r.content)
        check_budget()
        if n % 25 == 0 or n == len(todo):
            print(f"  {n}/{len(todo)} fetched")
    return failed


def main():
    ap = argparse.ArgumentParser(description="T1: download the region")
    ap.add_argument("--step", choices=["all", "trackpoints", "gpx"],
                    default="all")
    ap.add_argument("--region", default="wm", choices=sorted(
        regions.CANDIDATES))
    ap.add_argument("--max-gb", type=float, help="stop once the downloads "
                    "(this run plus earlier runs in --budget-file) pass this")
    ap.add_argument("--budget-file", type=Path,
                    default=Path("logs/download_bytes.json"))
    args = ap.parse_args()
    if args.max_gb:
        f = args.budget_file
        BUDGET.update(file=f, cap=args.max_gb * 1e9, start=json.loads(
            f.read_text())["bytes"] if f.exists() else 0)
    w, s, e, n = regions.CANDIDATES[args.region][1]
    print(f"Region {regions.region_name(args.region)}: "
          f"{len(tiles(args.region))} tiles, {w}..{e} E, {s}..{n} N")
    table = None
    try:
        if args.step in ("all", "trackpoints"):
            step_pages(args.region)
            table = step_trackpoints(args.region)
        if args.step in ("all", "gpx"):
            for n in range(1, MAX_PASSES + 1):
                if not step_gpx(table, args.region) or n == MAX_PASSES:
                    break
                time.sleep(RETRY_WAIT_S)
    except SizeCap as err:
        # the build queue waits for exactly this line
        print(f"\nT1 DOWNLOAD STOPPED: size cap ({err})")
        raise SystemExit(3)
    bad = incomplete_tiles(args.region)
    # the build queue waits for exactly this line
    print("\nT1 DOWNLOAD DONE" if not bad else
          f"\nT1 DOWNLOAD INCOMPLETE: {', '.join(bad)}")


if __name__ == "__main__":
    main()
