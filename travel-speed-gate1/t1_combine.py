#!/usr/bin/env python3
"""
T1 close-out: one dataset for all built regions.

Reads every built region (data/t1_<region>/, regions.py) and writes
data/t1_all/:
  segments_L50.parquet  every 50 m segment of every hiking trace, on any
                        kind of way (so whole hikes can be timed), plus
                        region and analysis_walk (True = the walking trail
                        segments that every T1 fit uses)
  traces.csv            one row per processed trace, plus region and the
                        mode features from t1_modes.py
  regions.csv           one row per region: data source, counts, curve
                        fit, elevation quality, capped tiles
  DATA_CARD.md          what the dataset is, how it was built, every
                        column, known limitations, terms of use
Run after any region is (re)built, and after t1_summary.py,
t1_dem_quality.py and t1_mode_check.py:   python t1_combine.py
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import regions
import t1_variants as v
from t1_build_dataset import depth_capped

OUT = Path("data/t1_all")

COLUMNS = [  # (column, meaning) for the data card, in file order
    ("region", "region key (regions.py), e.g. wm = White Mountains"),
    ("trace_id", "osm<id> = OSM GPS trace id (named uploads); anon<n> = "
     "anonymous points stitched from the API's tile pages"),
    ("uploader", "OSM user name (named traces only). Personal data: never "
     "publish"),
    ("identifiable", "True = the upload is identifiable or public on OSM"),
    ("source", "original GPX (uploader's file, via the API) / tile pieces "
     "(stitched from API pages) / lab original file (lab crawl, uploads "
     "2016-2022)"),
    ("piece", "continuous piece of the trace (split at gaps > 300 s or "
     "steps > 60 km/h)"),
    ("segment_id", "unique id <trace>_p<piece>_L50_<seg_index>"),
    ("geometry_wkt", "the segment's map-matched path, WKT LINESTRING in "
     "lon/lat (WGS84)"),
    ("seg_index", "segment number within the piece (in travel order)"),
    ("length_m", "segment length along the matched path (50 m)"),
    ("lat0, lon0, lat1, lon1", "segment start and end (WGS84)"),
    ("t_start", "start time, Unix seconds (UTC)"),
    ("elapsed_s", "clock time to cover the segment, stops included"),
    ("moving_s", "elapsed_s minus stops (stop rule window60_10: steps "
     "inside any 60 s window that moved < 10 m)"),
    ("speed_kmh", "length_m / moving_s, in km/h: the target"),
    ("stopped_frac", "share of elapsed_s removed as stops"),
    ("way_index", "matched OSM way, index into the region's way list "
     "(-1 = none)"),
    ("way_dir", "+1 / -1 = travel along / against the way's drawing "
     "direction"),
    ("osm_way_id", "matched OSM way id"),
    ("way_class", "trail (path, footway, bridleway, cycleway, steps ...), "
     "track, road, other, lift, rail, piste"),
    ("permission", "who may use the way, from OSM access tags: foot-only, "
     "bicycle-permitted, horse-permitted, bike+horse, unclear"),
    ("tag_*", "raw OSM tags of the matched way: highway, surface, "
     "sac_scale, width, trail_visibility, smoothness, mtb_scale, incline, "
     "name (missing = not tagged)"),
    ("match_err_m", "median distance from the GPS points to the matched "
     "way (m)"),
    ("n_points", "GPS points inside the segment"),
    ("native_interval_s", "the trace's median GPS sampling interval (s)"),
    ("local_time", "local start time, YYYY-MM-DD HH:MM, in the region's "
     "time zone"),
    ("day_of_year, doy_sin, doy_cos, year", "season and year (local)"),
    ("date_suspect", "True = date before 2005 (a GPS clock bug); kept"),
    ("z0_m, z1_m", "elevation at the segment ends (m), USGS 3DEP 5 m grid"),
    ("slope", "(z1_m - z0_m) / length_m along travel; + = uphill"),
    ("suspect", "speed > 30 km/h, |slope| > 0.8 or match error > 40 m "
     "(kept, flagged)"),
    ("hiking_trace", "the trace spends >= 5 moving minutes on trails "
     "(always True in this file)"),
    ("outing_id", "one outing = traces starting within 15 min and 1 km "
     "(group hikes, two phones). The unit for resampling and splits"),
    ("mode, mode_conf", "travel mode of the trace (t1_modes.py): walk, "
     "run, bike/ski, unknown; confidence 0.5-1"),
    ("foot_anchor", "True = >= 90% of the trace's trail segments are "
     "foot-only (bikes not allowed): walking anchors"),
    ("trail_network", "connected trail network (t1_finalize.py)"),
    ("block_10km", "10 km UTM block: the unit for geographic hold-out"),
    ("analysis_walk", "True = in the walking analysis set: mode walk, "
     "trail, not suspect, slope known (t1_variants.walker_trail_segments)"),
]


def built_keys():
    return [k for k in regions.CANDIDATES
            if (regions.data_dir(k) / "modes.csv").exists()]


def built_at(d):
    first = (d / "data_card.md").read_text().splitlines()[0]
    m = re.search(r"built (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC", first)
    return m.group(1) if m else ""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    keys = built_keys()
    summ = pd.read_csv("results/t1_summary/regions.csv").set_index("region")
    demq = Path("results/t1_dem_quality.csv")
    demq = (pd.read_csv(demq).set_index("region") if demq.exists()
            else pd.DataFrame())
    segs, traces, rows = [], [], []
    for key in keys:
        d = regions.data_dir(key)
        label, bbox, tz, veg = regions.CANDIDATES[key]
        seg = pd.read_parquet(d / "segments_L50.parquet")
        tr = pd.read_csv(d / "traces.csv")
        modes = pd.read_csv(d / "modes.csv")
        hikers = set(tr.loc[tr.hiking_trace, "trace_id"])
        seg = seg[seg.hiking_trace].copy()
        walk = v.walker_trail_segments(seg, hikers, modes)
        seg["analysis_walk"] = seg.segment_id.isin(set(walk.segment_id))
        seg["foot_anchor"] = seg.foot_anchor.astype("boolean")
        seg.insert(0, "region", key)
        segs.append(seg)
        traces.append(tr.merge(modes, on="trace_id", how="left")
                      .assign(region=key))
        s = summ.loc[key] if key in summ.index else {}
        q = demq.loc[key] if key in demq.index else {}
        excluded = sum(t.startswith(key + "_") for t in regions.EXCLUDE_TILES)
        rows.append({
            "region": key, "label": label, "time_zone": tz,
            "vegetation": veg, "bbox_wsen": " ".join(map(str, bbox)),
            "sources": s.get("sources", ""), "built_utc": built_at(d),
            **{c: s.get(c) for c in (
                "traces", "hiking_traces", "outings", "named_uploaders",
                "walking_traces", "walking_outings", "walking_segments",
                "walking_km", "walking_hours", "bike_ski_traces",
                "match_rate_pct", "sac_scale_pct", "surface_pct",
                "blocks_10km", "v0", "v0_lo", "v0_hi", "k", "k_lo", "k_hi",
                "peak_pct")},
            "dem_1m_pct": q.get("share_1m_pct"),
            "dem_median_res_m": q.get("median_resolution_m"),
            "tiles_excluded": excluded,
            "capped_tiles": depth_capped(regions.region_name(key))})
        print(f"{key}: {len(seg):,} segments ({len(walk):,} walking)",
              flush=True)
    seg = pd.concat(segs, ignore_index=True)
    seg.to_parquet(OUT / "segments_L50.parquet", index=False)
    pd.concat(traces, ignore_index=True).to_csv(OUT / "traces.csv",
                                                 index=False)
    reg = pd.DataFrame(rows)
    reg.to_csv(OUT / "regions.csv", index=False)
    write_card(seg, reg, summ)
    print(f"wrote {OUT}: {len(seg):,} segments from {len(keys)} regions, "
          f"{int(seg.analysis_walk.sum()):,} in the walking analysis set")


def _f(x, fmt="{:,.0f}"):
    return "" if x is None or pd.isna(x) else fmt.format(x)


def write_card(seg, reg, summ):
    a = summ.loc["ALL"] if "ALL" in summ.index else None
    w = seg[seg.analysis_walk]
    full = reg[reg.sources != "lab only"]
    lines = [
        "# T1 dataset: hiking speeds on trails in "
        f"{len(reg)} North American regions",
        "",
        f"*Combined data card, built "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by "
        "`t1_combine.py`. Each region also has its own "
        "card: `data/t1_<region>/data_card.md`.*",
        "",
        "## What it is",
        "",
        "Public GPS traces uploaded to OpenStreetMap (OSM). Each trace is "
        "map-matched to OSM trails, cut into 50 m segments, and joined "
        "with elevation, slope, OSM trail tags, local time, travel mode "
        "and grouping keys. **One row = one traversal of one 50 m segment "
        "by one trace.** The target is `speed_kmh` (moving speed).",
        "",
        f"- Regions: {len(reg)} ({len(full)} from full OSM downloads plus "
        f"the lab crawl, {len(reg) - len(full)} from the lab crawl only "
        "so far)",
        f"- Segments of hiking traces: {len(seg):,} "
        f"({(seg.way_class == 'trail').mean():.0%} on trails)",
        f"- Walking analysis set (`analysis_walk`): {len(w):,} segments, "
        f"{w.trace_id.nunique():,} traces, {w.outing_id.nunique():,} "
        f"outings, {w.moving_s.sum() / 3600:,.0f} moving hours, "
        f"{len(w) * 0.05:,.0f} km",
    ]
    if a is not None:
        lines += [
            f"- Hiking traces: {_f(a.hiking_traces)}; bike/ski traces: "
            f"{_f(a.bike_ski_traces)}",
            f"- Pooled walking curve (ln v = ln v0 - k |s + s0|): v0 "
            f"{a.v0:.2f} [{a.v0_lo:.2f}, {a.v0_hi:.2f}] km/h, k {a.k:.2f} "
            f"[{a.k_lo:.2f}, {a.k_hi:.2f}], fastest at {a.peak_pct:+.1f}% "
            "grade (Tobler 1993: 6.0 km/h, 3.5, -5%)",
        ]
    lines += ["", "## Regions", "",
              "| Region | Data | Hiking traces | Walking outings | Walking "
              "h | v0 km/h [95%] | k | 1 m lidar under trails | Capped "
              "tiles |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in reg.itertuples():
        capped = "none" if r.capped_tiles == "none" else \
            str(r.capped_tiles.count("cut at page"))
        lines.append(
            f"| {r.label} | {r.sources} | {_f(r.hiking_traces)} | "
            f"{_f(r.walking_outings)} | {_f(r.walking_hours)} | "
            f"{_f(r.v0, '{:.2f}')} [{_f(r.v0_lo, '{:.2f}')}, "
            f"{_f(r.v0_hi, '{:.2f}')}] | {_f(r.k, '{:.2f}')} | "
            f"{_f(r.dem_1m_pct, '{:.0f}%')} | {capped} |")
    capped = reg[reg.capped_tiles != "none"]
    if len(capped):
        lines += ["", "Capped tiles (the OSM API times out past ~4.5M "
                  "points of one area, so the oldest uploads there are out "
                  "of reach):", ""]
        lines += [f"- {r.label}: {r.capped_tiles}"
                  for r in capped.itertuples()]
    mc = Path("results/t1_mode_check/summary.json")
    lines += ["", "## How it was built", "",
              "1. **Collect** (`t1_download.py`, `cluster/`): every page of "
              "the OSM trackpoints API over the region's tiles (5,000 "
              "points a page, newest first), the original file of every "
              "named trace, and the lab's crawl of original files "
              "(2016-2022). Duplicates (same trace id, same recording on "
              "two accounts or phones) are removed; car-logger accounts "
              "are dropped.",
              "2. **Clean and match** (`t1_build_dataset.py`): split at "
              "gaps > 300 s or jumps > 60 km/h; stops removed (window "
              "rule); hidden-Markov map-matching to OSM ways "
              "(leuvenmapmatching); 50 m segments along the matched "
              "path.",
              "3. **Attributes**: slope from the USGS 3DEP 5 m grid "
              "(1 m lidar where available underneath), OSM tags, local "
              "time, season, suspect flags.",
              "4. **Group and classify** (`t1_modes.py`, "
              "`t1_finalize.py`): outings, travel mode anchored on "
              "foot-only trails, trail networks, 10 km blocks.",
              "5. **Checks**: map-match QA, 1 m vs 5 m slope, 25 m vs "
              "50 m segments, stop-rule sensitivity, GPS sampling "
              "interval strata, elevation source under the trails "
              "(`t1_dem_quality.py`), mode calls vs the uploaders' own "
              "activity labels (`t1_mode_check.py`)."]
    if mc.exists():
        m = json.loads(mc.read_text())
        lines += ["", "**Mode check against the uploaders' own labels** "
                  f"({m['labeled']} hiking traces whose original file "
                  "names the activity):",
                  f"- labeled hike/walk, called walk: "
                  f"{m['hike_labels_called_walk_pct']}%",
                  f"- labeled bike, called bike/ski: "
                  f"{m['bike_labels_called_bike_ski_pct']}% (called walk: "
                  f"{m['bike_labels_called_walk_pct']}%)",
                  f"- called walk but labeled bike or ski: "
                  f"{m['called_walk_labeled_bike_or_ski_pct']}% of "
                  f"{m['called_walk_n_labeled']}"]
    lines += ["", "## Files", "",
              "- `segments_L50.parquet`: the table described here "
              "(hiking traces only).",
              "- `traces.csv`: one row per processed trace (also "
              "non-hiking ones), with the mode features (v_med, v_p90, "
              "v_up, v_down, asym, foot, walk_z, gravity).",
              "- `regions.csv`: the table above, with more columns.",
              "", "## Columns of segments_L50.parquet", "",
              "| Column | Meaning |", "|---|---|"]
    lines += [f"| `{c}` | {m} |" for c, m in COLUMNS]
    lines += [
        "", "## Known limitations", "",
        "- **Who uploads.** OSM uploaders are mappers and enthusiasts, not "
        "a random sample of hikers. Speeds describe them.",
        "- **Lab-only regions** lack anonymous traces and uploads after "
        "2022 until their full downloads land (rebuilt automatically).",
        "- **Capped tiles** miss their oldest uploads (see above).",
        "- **Elevation quality.** Slopes rest on 1 m lidar under most "
        "trails, but not in Olympic NP or the North Shore (coarser data "
        "flattens slopes and lowers k).",
        "- **Stops.** The window rule is a draft until the hand-labeled "
        "sheet (`stop_check/`) is scored; the curve barely moves across 4 "
        "rules.",
        "- **Mode** is inferred, not reported by the hiker "
        "(`mode_conf`).",
        "- **Map matching.** OSM trails are often traced from these same "
        "uploads, so match errors look smaller than the true trail "
        "position error.",
        "- **Tags** are often missing (`tag_*` empty): sac_scale and "
        "surface coverage differ by region.",
        "", "## Terms of use", "",
        "- Derived from OSM GPS traces and OSM map data (© OpenStreetMap "
        "contributors, ODbL) and USGS 3DEP elevation (public domain).",
        "- `uploader` and `trace_id` identify people. Keep this dataset "
        "private. A public release needs both removed (or hashed) and the "
        "mentors' OK.",
        "",
        "## Load it", "",
        "```python",
        "import pandas as pd",
        "seg = pd.read_parquet('data/t1_all/segments_L50.parquet')",
        "walk = seg[seg.analysis_walk]          # what the T1 fits use",
        "```", ""]
    (OUT / "DATA_CARD.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
