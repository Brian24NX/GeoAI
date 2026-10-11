"""Download the 5 m elevation grids for every T1 tile once (cached).

USGS times out (HTTP 504) on one 4,000 x 5,000-pixel image per tile, so each
tile is fetched as SPLIT x SPLIT smaller pieces with a little overlap. The
dataset builder reads every piece; no stitching is needed.
"""
import time
from pathlib import Path

import numpy as np

import first_look_slope as fl

CACHE = Path("cache/layers")
SPLIT = 2
PAD = 0.002          # degrees of overlap so pieces and tiles meet cleanly


def piece_names(region, box, split=SPLIT):
    """[(file name stem, extent)] for the pieces of one tile."""
    name, w, s, e, n = box
    xs, ys = np.linspace(w, e, split + 1), np.linspace(s, n, split + 1)
    return [(f"{region}_{name}_q{i}{j}",
             (xs[j] - PAD, ys[i] - PAD, xs[j + 1] + PAD, ys[i + 1] + PAD))
            for i in range(split) for j in range(split)]


def ensure_dems(region, boxes):
    for box in boxes:
        for stem, extent in piece_names(region, box):
            t0 = time.time()
            for attempt in range(3):
                try:
                    a, _ = fl.dem(CACHE, stem, extent)
                    break
                except Exception as err:          # server busy: wait, retry
                    if attempt == 2:
                        raise
                    print(f"  {stem}: {err.__class__.__name__}, retrying",
                          flush=True)
                    time.sleep(60)
            print(f"{stem}: {a.shape}, {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    import argparse
    import regions
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="wm", choices=sorted(
        regions.CANDIDATES))
    key = ap.parse_args().region
    ensure_dems(regions.region_name(key), regions.tiles(key))
    print("DEM PREFETCH DONE")
