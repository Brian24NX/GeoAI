# Data card: front_range (T1, built 2026-10-09 21:50 UTC)

One row per (trace x fixed-length segment) traversal; see t1_build_dataset.py for every step.

## Counts

- traces processed: 121 (named = identifiable or public 94, anonymous 27)
- by source: {'tile pieces': 121}
- hiking traces (>= 5 moving min on trails): 82
- independent outings among hiking traces (group hikes and multi-phone recordings merged): 82
- named uploaders among hiking traces: 19
- 50 m trail segments from hiking traces: 12,903
- median share of each trace matched: 100.0%
- time removed as stops (all traces): 12.1% median per trace

## Collection

- car_logger_pieces: 900
- identifiable_tile_pieces: 99
- duplicates_dropped: 6
- near_duplicates_dropped: 0
- named: 94
- anonymous: 27

## Settings

- segment lengths: (50.0, 25.0) m
- thinning for matching: >= 5.0 s
- split at gaps > 300 s or steps > 60 km/h
- stop rule: window60_10 ('window', 60, 10) (draft; see the stop-rule sensitivity check)
- map-matching: leuvenmapmatching DistanceMatcher {'obs_noise': 15, 'obs_noise_ne': 30, 'dist_noise': 15, 'max_dist': 60, 'max_dist_init': 60, 'non_emitting_states': True, 'max_lattice_width': 8, 'only_edges': True}
- slope: (z_end - z_start) / length along travel, 5 m USGS 3DEP DEM; + = uphill (tested)
- suspect flag (kept, not dropped): speed > 30 km/h, abs(slope) > 0.8, or match error > 40 m
- suspect share of hiking trail segments: 1.54%
- car-logger accounts dropped: ['dragonpilot', 'frogpilot', 'openpilot', 'sunnypilot']
- local time zone: America/Denver
- OSM ways (trails, tags) from Overpass, downloaded 2026-10-02
- traces with impossible dates (before 2005, flagged date_suspect): ['anon2878216717']
- lab traces: original files of public + identifiable OSM traces uploaded 2016-2022 (lab crawl on ENGRFS), added unless the API gave the same trace id

## Known limitations

- The stop rule is a draft until the hand-labeled sheet is scored.
- OSM trails are often traced from these same uploads, so match errors look smaller than true trail-position errors.
- Uploaders are mappers and enthusiasts, not a random sample of hikers (plan sec. 8).
