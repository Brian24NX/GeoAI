# Decisions log

Plan §15: *"Keep a decisions log. Every threshold, filter, and split boundary.
You will need it for the data card and the paper's methods section, and you
will not remember it in week 13."*

**Status key:** **draft** = picked by us to get Gate 1 running; not yet
discussed. **agreed** = confirmed with Danni / Tianyi (write the date).
Every run also saves the numbers it used in `results/<region>/summary.json`
under `"settings"`.

## Gate 1 (from 2 Oct 2026, `gate1_audit.py` v2)

| # | Decision | Value | Why | Status |
|---|---|---|---|---|
| 1 | What counts as usable | Points with timestamps (*identifiable* + *trackable* uploads). Untimed points (*public* + *private*) are unusable. | No timestamps means no speed. The API sends public/private points sorted by latitude, with no time. | draft |
| 2 | How the usable fraction is measured | **By points**, not by traces | The API puts all untimed points on a page into one nameless track, so untimed *traces* can't be counted. | draft |
| 3 | Sample boxes | 4 boxes per region, 0.1° × 0.1°, over popular trail areas (listed in `REGIONS`) | Picked by the previous Claude chat, not by the lab. The Franconia and Lincoln Woods boxes overlap a little. | draft |
| 4 | Pages used for speeds | Up to 150 pages (750k points) of usable points per box; exact counts come from searching for the last page | At first this was 40. That cut off older hiking traces, because the newest uploads are car loggers. Only Boulder (≈500 usable pages, almost all car logs) still hits the cap. | draft |
| 4b | "Usable on trails" estimate | Usable trail points ÷ (usable + unusable trail points). The unusable side comes from 6 evenly spaced untimed pages per box, plus the pages read while searching. | Car loggers inflate the plain usable %. Hikers are what we need. | draft |
| 5 | Speed step | Speed measured between points **≥ 10 s apart** | GPS wobble inflates point-to-point speed when recording every 1–2 s. Fake data: +168% at 1 s. Real data: about +14% (n=3 walkers). | draft |
| 6 | Repeated timestamps | Keep the first point of each second | Some loggers (e.g. car loggers at 10 Hz) store whole seconds only. | draft |
| 7 | Gaps | Steps longer than **300 s** are dropped (neither moving nor stopped) | Signal loss, or the trace left the box and came back. | draft |
| 8 | Too fast | Steps over **60 km/h** are dropped | Vehicle or GPS glitch. | draft |
| 9 | Crude stop rule | Step speed **< 0.5 km/h** = stopped | Plan §6, "start with ~0.5 km/h; tune later". | from plan |
| 10 | Draft stop rule | A stretch of **≥ 60 s** that ends **< 10 m** from where it started = stopped | Plan §8 asks for "speed threshold plus minimum duration". Wobble jiggles points but doesn't carry a standing person 10 m. **Not tuned.** | draft |
| 11 | Matching points to trails (Gate 1 only) | Nearest OSM way within **25 m**; ways cut into points every 5 m | A crude stand-in for HMM map-matching (T1). | draft |
| 12 | What counts as a trail | `highway` = path, footway, bridleway, steps, cycleway, via_ferrata, **but not** sidewalks, crossings, traffic islands or access aisles (`footway=` / `cycleway=` sidewalk etc.). `track` kept separate. Roads, lifts, railways and ski runs excluded. | Keeps cars, the Cog Railway and ski lifts out of walking speeds. Sidewalks were added after Boulder (~3,500 sidewalks/crosswalks) pulled car points onto "trails". | draft |
| 13 | Trail trace | ≥ **5 moving minutes** on trails | Drops drive-through and parking-lot clips. | draft |
| 14 | Permitted mode | Explicit `bicycle=` / `horse=` tags win. Otherwise cycleway or `mtb:scale` → bikes allowed; bridleway → horses allowed; footway/steps → neither. A plain path with no tag = "unclear". | US defaults for `highway=path` are disputed, so we don't guess. | draft |
| 15 | Duplicate uploads | Identical point sets: keep one | Found real duplicates on Mt Washington. | draft |
| 16 | Group hikes ("outings") | Traces starting within **15 min and 1 km** of each other in the same box = one outing | Two phones on one hike aren't independent samples. | draft |
| 17 | Joining a trackable trace split by a page break | Join if the next piece starts within **10 min** | Trackable traces have no ID to join on. | draft |
| 18 | Hike days | Counted in local solar time (UTC + longitude/15 h) | So an evening hike isn't split across two UTC dates. | draft |

## Region layers (`region_layers.py`)

| # | Decision | Value | Status |
|---|---|---|---|
| 19 | 1 m coverage test | Share of a 30 × 30 sample grid where USGS says the best DEM is 1 m | draft |
| 20 | Relief | Highest minus lowest of those 900 samples (misses exact summits by up to ~50 m) | draft |
| 21 | Canopy | NLCD 2021 Tree Canopy Cover (30 m), averaged over the box and along OSM trails | draft |

## First look at slope vs speed (`first_look_slope.py`) — preview only

| # | Decision | Value | Status |
|---|---|---|---|
| 22 | Unit of measurement | ~50 m chunks of continuous, moving, on-trail travel (both stop rules applied; any gap ends a chunk) | draft |
| 23 | Elevation | 5 m USGS 3DEP DEM (bilinear), chunk ends snapped to the nearest trail point | draft |
| 24 | Slope sign | rise / distance in the direction of travel, + = uphill; automatic sign test on a synthetic tilted DEM | agreed with plan §8 ("write a test for the sign convention") |
| 25 | Walkers only | Drop traces whose median chunk speed is > 7 km/h, or that have < 6 chunks | draft (crude stand-in for mode inference) |
| 26 | Outliers | Drop chunks with abs(slope) > 60% | draft |
| 27 | Fit | Least squares in log space, `ln v = ln v0 − k·abs(s + s0)`, s0 by grid search | draft |

## T1 (from 8 Oct 2026)

| # | Decision | Value | Status |
|---|---|---|---|
| 28 | Region | **White Mountains** (White Mountain National Forest) | **agreed** with Danni, 2 Oct 2026 meeting |
| 29 | Region box and tiles | 43.80–44.50 N, 71.95–70.95 W, as 12 tiles of 0.25° × 0.233° (`t1_download.py`) | draft |
| 30 | Pages per tile | All usable pages (cap 600) | draft |
| 31 | Whole hikes | Original GPX of every identifiable trace from `openstreetmap.org/trace/<id>/data`; car-logger accounts (sunnypilot, dragonpilot, openpilot, frogpilot) skipped | draft |
| 32 | Map-matching | `leuvenmapmatching` DistanceMatcher (HMM). Graph = OSM trails + tracks + roads (no sidewalks); ways joined where they share a node (same coordinates to 7 decimals). Settings: obs_noise 15 m, obs_noise_ne 30 m, dist_noise 15 m, max_dist 60 m, lattice width 8, non-emitting states on. Restarts after a break; points with no way within 60 m stay unmatched. | draft. First test on 17 hikes: median 100% matched, 2.2 m from the way, 97% agreement with the Gate 1 nearest-way rule |

## T1 dataset v0 (`t1_build_dataset.py`, 8–9 Oct 2026)

| # | Decision | Value | Status |
|---|---|---|---|
| 33 | Thinning before matching | Points ≥ 5 s apart | draft |
| 34 | Splitting recordings | At gaps > 5 min and at steps > 60 km/h | draft |
| 35 | Segment length | 50 m (main) and 25 m (kept for comparison), cut along the **matched** path; standing still adds no distance | draft |
| 36 | Segment speed | Length ÷ *moving* time (stopped time removed); wall-clock time and stopped fraction kept as columns | draft |
| 37 | Slope | (elevation at end − at start) ÷ length, along the direction of travel, from a 5 m USGS 3DEP grid (in quarter-tile pieces). + = uphill, checked by an automatic test | draft. T2 will switch to the 1 m DEM |
| 38 | Stop rule for v0 | Draft window rule (60 s ending < 10 m away). **Not hand-validated yet.** Instead, every headline result is reported under 4 rules (`t1_variants.py`) | **decided 8 Oct** (Claude, on Brian's request); hand-check still open |
| 39 | Suspect segments | Flagged, not dropped: speed > 30 km/h, abs(slope) > 80%, or match error > 40 m | draft |
| 40 | Hiking trace | ≥ 5 moving minutes on OSM trails (sidewalks excluded) | draft |
| 41 | Walkers only (for slope–speed fits) | Traces whose median segment speed ≤ 7 km/h; ≥ 6 chunks (first look) | draft (crude stand-in for mode inference, plan §8) |
| 42 | Uncertainty | 95% intervals by resampling **whole hikes** (200 bootstrap draws), never single points (plan §10) | draft |
| 43 | Anonymous trace IDs | Hash of the point set (stable across runs); identifiable traces use their OSM trace ID | draft |
| 44 | Counting unit | "Hiking traces" are **uploads**. Also report **hiking days** (a trace's trail time split by local date, ≥ 5 moving min): 192 traces = 235 days; 13 uploads span several days (one spans 16). Intervals still resample whole traces, which keeps one person's days together. | draft, 9 Oct |
| 45 | Impossible dates | Flag traces dated before 2005 (before OSM took GPS uploads); don't trust their season columns. One so far: `osm2731854` (1987, probably a GPS week-rollover bug). | to implement in v1 |
| 46 | Tobler error in hours (Q1 first look) | Per trace with ≥ 15 moving min on trails: predicted ÷ actual moving time, summed over its walker trail segments. The refit curve is cross-validated 5-fold by trace. | draft, 9 Oct (`t1_meeting_figures.py`, `extra_numbers`) |
| 47 | Out-and-back pairs (Q3 first look) | Same trace, same OSM way, ≥ 2 segments each way, mean grade ≥ 3%, up side uphill and down side downhill. Ratio = moving speed down ÷ up; median with a trace-resampled interval. | draft, 9 Oct |

## T2 (from 9 Oct 2026)

| # | Decision | Value | Status |
|---|---|---|---|
| 48 | 1 m elevation: where and on what grid | USGS 3DEP 1 m via the elevation ImageServer, only for 500 m × 500 m cells within 25 m of a walked trail point of a T1 hiking trace (1,832 cells). Grid: NAD83 / UTM 19N (EPSG:26919), cells aligned to multiples of 500 m, 1 m pixels, bilinear. Spot check: within 1 m of the 5 m grid; the Mt Washington cell's maximum is 1,915.8 m (summit 1,917 m). | draft, 9 Oct (`t2_prefetch_dem1m.py`). **Downloaded 9 Oct 02:53:** 1,832 of 1,832 cells, 0 failures, no gaps, 100% of walked trail points covered, 1.9 GB. Matches the 5 m grid at 3,000 trail points (median abs difference 0.18 m, 95th percentile 0.64 m). |

## Still to decide (T1, plan §8)

- Final stop rule (tune #10 using hand-checked stops)
- Map-matching method (`leuvenmapmatching` or HMM per Newson & Krumm) and the minimum match confidence
- Segment length: 25 m or 50 m (pick by checking how much slope varies inside a segment)
- Train/test split: by trace **and** by trail system, never by point (plan §10)
- What counts as "enough" traces for Gate 1 (ask Danni and Tianyi)
- Which OSM snapshot to freeze for trail geometry and tags. T1 v0 used Overpass downloads from 8 Oct; Progress Report #1 says Geofabrik extracts. Freeze one dated snapshot before T3.
- One region or two (a second region as a geographic hold-out); asked 9 Oct
