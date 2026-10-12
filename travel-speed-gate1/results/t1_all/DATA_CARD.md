# T1 dataset: hiking speeds on trails in 17 North American regions

*Combined data card, built 2026-10-12 05:24 UTC by `t1_combine.py`. Each region also has its own card: `data/t1_<region>/data_card.md`.*

## What it is

Public GPS traces uploaded to OpenStreetMap (OSM). Each trace is map-matched to OSM trails, cut into 50 m segments, and joined with elevation, slope, OSM trail tags, local time, travel mode and grouping keys. **One row = one traversal of one 50 m segment by one trace.** The target is `speed_kmh` (moving speed).

- Regions: 17 (16 from full OSM downloads plus the lab crawl, 1 from the lab crawl only so far)
- Segments of hiking traces: 709,935 (62% on trails)
- Walking analysis set (`analysis_walk`): 290,640 segments, 2,046 traces, 1,992 outings, 4,702 moving hours, 14,532 km
- Hiking traces: 2,876; bike/ski traces: 490
- Pooled walking curve (ln v = ln v0 - k |s + s0|): v0 4.31 [4.23, 4.37] km/h, k 1.80 [1.74, 1.86], fastest at -4.5% grade (Tobler 1993: 6.0 km/h, 3.5, -5%)

## Regions

| Region | Data | Hiking traces | Walking outings | Walking h | v0 km/h [95%] | k | 1 m lidar under trails | Capped tiles |
|---|---|---|---|---|---|---|---|---|
| White Mountains, NH | API + lab | 235 | 189 | 624 | 4.23 [4.01, 4.46] | 2.10 | 100% | none |
| Adirondack High Peaks, NY | API + lab | 103 | 74 | 258 | 4.06 [3.85, 4.24] | 2.21 | 99% | none |
| Catskills, NY | API + lab | 73 | 60 | 151 | 4.19 [3.97, 4.47] | 1.91 | 100% | none |
| Green Mountains, VT | API + lab | 56 | 25 | 78 | 4.52 [3.72, 5.02] | 2.46 | 100% | none |
| Shenandoah, VA | API + lab | 83 | 41 | 63 | 4.57 [4.05, 5.06] | 1.14 | 100% | 1 |
| Great Smoky Mountains, TN/NC | API + lab | 69 | 58 | 130 | 3.95 [3.76, 4.17] | 1.06 | 88% | none |
| Asheville / Pisgah, NC | API + lab | 75 | 38 | 55 | 4.02 [3.68, 4.33] | 1.21 | 90% | none |
| Colorado Front Range (Boulder-Golden) | API + lab | 206 | 97 | 203 | 4.46 [4.26, 4.76] | 1.94 | 96% | 1 |
| Wasatch Front (Salt Lake City), UT | API + lab | 131 | 91 | 153 | 4.80 [4.55, 5.08] | 2.06 | 92% | none |
| Cascades I-90 + Alpine Lakes, WA | API + lab | 684 | 528 | 1,295 | 4.37 [4.22, 4.50] | 1.72 | 83% | 1 |
| Columbia River Gorge, OR/WA | API + lab | 104 | 67 | 156 | 4.63 [4.13, 5.15] | 1.55 | 27% | none |
| Olympic NP (north), WA | API + lab | 175 | 163 | 376 | 4.08 [3.94, 4.24] | 1.10 | 34% | none |
| Bay Area hills (Marin, East Bay, Peninsula), CA | lab only | 177 | 102 | 117 | 4.42 [4.18, 4.59] | 1.37 | 98% | none |
| San Gabriel Mountains (LA), CA | API + lab | 141 | 116 | 302 | 4.08 [3.75, 4.44] | 1.93 | 100% | 1 |
| Yosemite Valley + High Sierra, CA | API + lab | 92 | 86 | 238 | 4.17 [4.00, 4.38] | 1.88 | 70% | none |
| Lake Tahoe, CA/NV | API + lab | 230 | 94 | 260 | 4.17 [3.84, 4.60] | 1.67 | 95% | none |
| North Shore Mountains (Vancouver), BC | API + lab | 242 | 165 | 244 | 4.38 [4.12, 4.68] | 1.64 | 0% | none |

Capped tiles (the OSM API times out past ~4.5M points of one area, so the oldest uploads there are out of reach):

- Shenandoah, VA: shenandoah_r1_c1 (cut at page 523; reaches uploads back to ~2023-05)
- Colorado Front Range (Boulder-Golden): frontrange_r2_c2 (cut at page 931; reaches uploads back to ~2009-08)
- Cascades I-90 + Alpine Lakes, WA: cascades_r1_c0 (cut at page 907; reaches uploads back to ~2009-10)
- San Gabriel Mountains (LA), CA: sangabriel_r0_c0 (cut at page 533; reaches uploads back to ~2023-07)

## How it was built

1. **Collect** (`t1_download.py`, `cluster/`): every page of the OSM trackpoints API over the region's tiles (5,000 points a page, newest first), the original file of every named trace, and the lab's crawl of original files (2016-2022). Duplicates (same trace id, same recording on two accounts or phones) are removed; car-logger accounts are dropped.
2. **Clean and match** (`t1_build_dataset.py`): split at gaps > 300 s or jumps > 60 km/h; stops removed (window rule); hidden-Markov map-matching to OSM ways (leuvenmapmatching); 50 m segments along the matched path.
3. **Attributes**: slope from the USGS 3DEP 5 m grid (1 m lidar where available underneath), OSM tags, local time, season, suspect flags.
4. **Group and classify** (`t1_modes.py`, `t1_finalize.py`): outings, travel mode anchored on foot-only trails, trail networks, 10 km blocks.
5. **Checks**: map-match QA, 1 m vs 5 m slope, 25 m vs 50 m segments, stop-rule sensitivity, GPS sampling interval strata, elevation source under the trails (`t1_dem_quality.py`), mode calls vs the uploaders' own activity labels (`t1_mode_check.py`).

**Mode check against the uploaders' own labels** (327 hiking traces whose original file names the activity):
- labeled hike/walk, called walk: 92.6%
- labeled bike, called bike/ski: 77.7% (called walk: 8.5%)
- called walk but labeled bike or ski: 5.1% of 177

## Files

- `segments_L50.parquet`: the table described here (hiking traces only).
- `traces.csv`: one row per processed trace (also non-hiking ones), with the mode features (v_med, v_p90, v_up, v_down, asym, foot, walk_z, gravity).
- `regions.csv`: the table above, with more columns.

## Columns of segments_L50.parquet

| Column | Meaning |
|---|---|
| `region` | region key (regions.py), e.g. wm = White Mountains |
| `trace_id` | osm<id> = OSM GPS trace id (named uploads); anon<n> = anonymous points stitched from the API's tile pages |
| `uploader` | OSM user name (named traces only). Personal data: never publish |
| `identifiable` | True = the upload is identifiable or public on OSM |
| `source` | original GPX (uploader's file, via the API) / tile pieces (stitched from API pages) / lab original file (lab crawl, uploads 2016-2022) |
| `piece` | continuous piece of the trace (split at gaps > 300 s or steps > 60 km/h) |
| `segment_id` | unique id <trace>_p<piece>_L50_<seg_index> |
| `geometry_wkt` | the segment's map-matched path, WKT LINESTRING in lon/lat (WGS84) |
| `seg_index` | segment number within the piece (in travel order) |
| `length_m` | segment length along the matched path (50 m) |
| `lat0, lon0, lat1, lon1` | segment start and end (WGS84) |
| `t_start` | start time, Unix seconds (UTC) |
| `elapsed_s` | clock time to cover the segment, stops included |
| `moving_s` | elapsed_s minus stops (stop rule window60_10: steps inside any 60 s window that moved < 10 m) |
| `speed_kmh` | length_m / moving_s, in km/h: the target |
| `stopped_frac` | share of elapsed_s removed as stops |
| `way_index` | matched OSM way, index into the region's way list (-1 = none) |
| `way_dir` | +1 / -1 = travel along / against the way's drawing direction |
| `osm_way_id` | matched OSM way id |
| `way_class` | trail (path, footway, bridleway, cycleway, steps ...), track, road, other, lift, rail, piste |
| `permission` | who may use the way, from OSM access tags: foot-only, bicycle-permitted, horse-permitted, bike+horse, unclear |
| `tag_*` | raw OSM tags of the matched way: highway, surface, sac_scale, width, trail_visibility, smoothness, mtb_scale, incline, name (missing = not tagged) |
| `match_err_m` | median distance from the GPS points to the matched way (m) |
| `n_points` | GPS points inside the segment |
| `native_interval_s` | the trace's median GPS sampling interval (s) |
| `local_time` | local start time, YYYY-MM-DD HH:MM, in the region's time zone |
| `day_of_year, doy_sin, doy_cos, year` | season and year (local) |
| `date_suspect` | True = date before 2005 (a GPS clock bug); kept |
| `z0_m, z1_m` | elevation at the segment ends (m), USGS 3DEP 5 m grid |
| `slope` | (z1_m - z0_m) / length_m along travel; + = uphill |
| `suspect` | speed > 30 km/h, |slope| > 0.8 or match error > 40 m (kept, flagged) |
| `hiking_trace` | the trace spends >= 5 moving minutes on trails (always True in this file) |
| `outing_id` | one outing = traces starting within 15 min and 1 km (group hikes, two phones). The unit for resampling and splits |
| `mode, mode_conf` | travel mode of the trace (t1_modes.py): walk, run, bike/ski, unknown; confidence 0.5-1 |
| `foot_anchor` | True = >= 90% of the trace's trail segments are foot-only (bikes not allowed): walking anchors |
| `trail_network` | connected trail network (t1_finalize.py) |
| `block_10km` | 10 km UTM block: the unit for geographic hold-out |
| `analysis_walk` | True = in the walking analysis set: mode walk, trail, not suspect, slope known (t1_variants.walker_trail_segments) |

## Known limitations

- **Who uploads.** OSM uploaders are mappers and enthusiasts, not a random sample of hikers. Speeds describe them.
- **Lab-only regions** lack anonymous traces and uploads after 2022 until their full downloads land (rebuilt automatically).
- **Capped tiles** miss their oldest uploads (see above).
- **Elevation quality.** Slopes rest on 1 m lidar under most trails, but not in Olympic NP or the North Shore (coarser data flattens slopes and lowers k).
- **Stops.** The window rule is a draft until the hand-labeled sheet (`stop_check/`) is scored; the curve barely moves across 4 rules.
- **Mode** is inferred, not reported by the hiker (`mode_conf`).
- **Map matching.** OSM trails are often traced from these same uploads, so match errors look smaller than the true trail position error.
- **Tags** are often missing (`tag_*` empty): sac_scale and surface coverage differ by region.

## Terms of use

- Derived from OSM GPS traces and OSM map data (© OpenStreetMap contributors, ODbL) and USGS 3DEP elevation (public domain).
- `uploader` and `trace_id` identify people. Keep this dataset private. A public release needs both removed (or hashed) and the mentors' OK.

## Load it

```python
import pandas as pd
seg = pd.read_parquet('data/t1_all/segments_L50.parquet')
walk = seg[seg.analysis_walk]          # what the T1 fits use
```
