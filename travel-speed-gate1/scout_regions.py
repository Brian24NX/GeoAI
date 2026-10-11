#!/usr/bin/env python3
"""
Scout the candidate regions with the lab's trace index (no downloading).

The lab crawl (cluster/build_lab_index.py) has one row per OSM trace with its
bounding box, duration, distance and average speed, for public +
identifiable traces uploaded 2016-2022. For every region in regions.py this
counts the traces that sit inside the region and LOOK like hikes or rides.
It's a first cut, to rank regions before the slow part (OSM API pages,
map-matching). Real counts come from the T1 build.

  hike-like:  20 min - 16 h, >= 1 km, average speed 0.8-6 km/h (stops included)
  ride-like:  20 min - 16 h, >= 2 km, average speed 6-25 km/h
  local:      the trace's bbox is inside the region and < 0.3 deg across

Input:  cache/lab_index/index.parquet, uploaders.parquet (copied from the
        cluster)
Output: results/region_scout.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

import regions

IDX = Path("cache/lab_index")
OUT = Path("results/region_scout.csv")


def load():
    ix = pd.read_parquet(IDX / "index.parquet", columns=[
        "trace_id", "start_time", "duration_seconds", "total_distance_km",
        "avg_speed_kmh", "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy",
        "point_count"])
    up = pd.read_parquet(IDX / "uploaders.parquet").drop_duplicates(
        "trace_id")
    return ix.merge(up[["trace_id", "user"]], on="trace_id", how="left")


def classify(t):
    dur_h = t.duration_seconds / 3600
    ok = (dur_h >= 1 / 3) & (dur_h <= 16)
    hike = ok & (t.total_distance_km >= 1) & t.avg_speed_kmh.between(0.8, 6)
    ride = ok & (t.total_distance_km >= 2) & (t.avg_speed_kmh > 6) \
        & (t.avg_speed_kmh <= 25)
    return hike, ride


def main():
    t = load()
    print(f"{len(t):,} traces in the lab index")
    hike, ride = classify(t)
    rows = []
    for key, (label, (w, s, e, n), tz, veg) in regions.CANDIDATES.items():
        local = ((t.bbox_minx >= w) & (t.bbox_maxx <= e) & (t.bbox_miny >= s)
                 & (t.bbox_maxy <= n) & (t.bbox_maxx - t.bbox_minx < 0.3)
                 & (t.bbox_maxy - t.bbox_miny < 0.3))
        h = t[local & hike]
        rows.append({
            "region": key, "label": label, "vegetation": veg,
            "traces_local": int(local.sum()),
            "hike_like": len(h), "ride_like": int((local & ride).sum()),
            "hike_uploaders": int(h.user.nunique()),
            "top_uploader_share_pct": float(
                100 * h.user.value_counts().iloc[0] / len(h)) if len(h)
            else np.nan,
            "hike_hours": float(h.duration_seconds.sum() / 3600),
            "median_hike_km": float(h.total_distance_km.median())
            if len(h) else np.nan,
            "years": f"{h.start_time.dt.year.min()}-"
                     f"{h.start_time.dt.year.max()}" if len(h) else ""})
    r = pd.DataFrame(rows).sort_values("hike_like", ascending=False)
    OUT.parent.mkdir(exist_ok=True)
    r.to_csv(OUT, index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(r.drop(columns=["label", "vegetation"]).round(1)
              .to_string(index=False))
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
