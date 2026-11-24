# T1 dataset: hiking speeds on trails in 16 North American regions

*Combined data card, built 2026-11-14 01:40 UTC by `t1_combine.py`. Each region also has its own card: `data/t1_<region>/data_card.md`.*

## What it is

Public GPS traces uploaded to OpenStreetMap (OSM). Each trace is map-matched to OSM trails, cut into 50 m segments, and joined with elevation, slope, OSM trail tags, local time, travel mode and grouping keys. **One row = one traversal of one 50 m segment by one trace.** The target is `speed_kmh` (moving speed).

- Regions: 16 (16 from full OSM downloads plus the lab crawl, 0 from the lab crawl only so far)
- Segments of hiking traces: 654,390 (64% on trails)
- Walking analysis set (`analysis_walk`): 284,711 segments, 1,904 traces, 1,861 outings, 4,623 moving hours, 14,236 km
- Hiking traces: 2,654; bike/ski traces: 431
- Pooled walking curve (ln v = ln v0 - k |s + s0|): v0 4.30 [4.23, 4.39] km/h, k 1.80 [1.74, 1.86], fastest at -4.5% grade (Tobler 1993: 6.0 km/h, 3.5, -5%)

## Regions

| Region | Data | Hiking traces | Walking outings | Walking h | v0 km/h [95%] | k | 1 m lidar under trails | Capped tiles |
|---|---|---|---|---|---|---|---|---|
| White Mountains, NH | API + lab | 226 | 182 | 625 | 4.23 [4.03, 4.44] | 2.10 | 100% | none |
| Adirondack High Peaks, NY | API + lab | 96 | 67 | 261 | 4.08 [3.91, 4.24] | 2.23 | 99% | none |
| Catskills, NY | API + lab | 69 | 57 | 151 | 4.19 [3.96, 4.40] | 1.91 | 100% | none |
| Green Mountains, VT | API + lab | 55 | 24 | 77 | 4.38 [3.58, 4.90] | 2.37 | 100% | none |
| Shenandoah, VA | API + lab | 87 | 45 | 71 | 4.51 [4.04, 4.97] | 1.26 | 100% | none |
| Great Smoky Mountains, TN/NC | API + lab | 68 | 57 | 130 | 3.95 [3.75, 4.18] | 1.05 | 88% | none |
| Asheville / Pisgah, NC | API + lab | 75 | 38 | 55 | 4.03 [3.69, 4.30] | 1.22 | 90% | none |
| Colorado Front Range (Boulder-Golden) | API + lab | 192 | 95 | 204 | 4.44 [4.24, 4.71] | 1.91 | 96% | none |
| Wasatch Front (Salt Lake City), UT | API + lab | 128 | 90 | 153 | 4.81 [4.54, 5.04] | 2.08 | 92% | none |
| Cascades I-90 + Alpine Lakes, WA | API + lab | 665 | 516 | 1,295 | 4.36 [4.19, 4.52] | 1.72 | 83% | none |
| Columbia River Gorge, OR/WA | API + lab | 104 | 67 | 156 | 4.62 [4.16, 5.13] | 1.54 | 27% | none |
| Olympic NP (north), WA | API + lab | 172 | 160 | 376 | 4.08 [3.95, 4.25] | 1.09 | 34% | none |
| San Gabriel Mountains (LA), CA | API + lab | 157 | 127 | 324 | 4.16 [3.80, 4.60] | 1.97 | 100% | none |
| Yosemite Valley + High Sierra, CA | API + lab | 88 | 82 | 238 | 4.18 [3.98, 4.40] | 1.88 | 70% | none |
| Lake Tahoe, CA/NV | API + lab | 230 | 95 | 262 | 4.22 [3.81, 4.68] | 1.72 | 95% | none |
| North Shore Mountains (Vancouver), BC | API + lab | 242 | 165 | 244 | 4.38 [4.10, 4.67] | 1.62 | 0% | none |

## How it was built

1. **Collect** (`t1_download.py`, `cluster/`): every page of the OSM trackpoints API over the region's tiles (5,000 points a page, newest first), the original file of every named trace, and the lab's crawl of original files (2016-2022). Duplicates (same trace id, same recording on two accounts or phones) are removed; car-logger accounts are dropped.
2. **Clean and match** (`t1_build_dataset.py`): split at gaps > 300 s or jumps > 60 km/h; stops removed (window rule); hidden-Markov map-matching to OSM ways (leuvenmapmatching); 50 m segments along the matched path.
3. **Attributes**: slope from the USGS 3DEP 5 m grid (1 m lidar where available underneath), OSM tags, local time, season, suspect flags.
4. **Group and classify** (`t1_modes.py`, `t1_finalize.py`): outings, travel mode anchored on foot-only trails, trail networks, 10 km blocks.
5. **Checks**: map-match QA, 1 m vs 5 m slope, 25 m vs 50 m segments, stop-rule sensitivity, GPS sampling interval strata, elevation source under the trails (`t1_dem_quality.py`), mode calls vs the uploaders' own activity labels (`t1_mode_check.py`).

**Mode check against the uploaders' own labels** (334 hiking traces whose original file names the activity):
- labeled hike/walk, called walk: 92.1%
- labeled bike, called bike/ski: 78.1% (called walk: 9.4%)
- called walk but labeled bike or ski: 5.5% of 183

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
- **Stops.** The window rule misses stops under 60 s: in a hand check of 20 moments (`stop_check/`, decision #123) it caught 1 of 7 stops, a speed rule (< 0.5 km/h) 6 of 7. The curve barely moves across 4 rules (White Mountains peak 4.23 km/h, 4.13 with the speed rule). A v2 release will use the speed rule.
- **Recording interval.** Speeds of traces logged every > 10 s read low: straight lines between sparse points cut corners, and short stops between points count as moving. Thinning dense walks shows -3% at 10 s, -7.5% at 20 s, -11% at 30 s (`t1_sampling_check.py`). Filter or correct with `native_interval_s`; the walking curve without > 10 s traces peaks 3% higher.
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
