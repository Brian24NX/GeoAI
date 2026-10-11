# Data card: t1_white_mountains (T1, built 2026-10-09 05:00 UTC)

One row per (trace x fixed-length segment) traversal; see t1_build_dataset.py for every step.

## Counts

- traces processed: 294 (identifiable 142, anonymous 152)
- hiking traces (>= 5 moving min on trails): 192
- named uploaders among hiking traces: 40
- 50 m trail segments from hiking traces: 34,652
- median share of each trace matched: 100.0%
- time removed as stops (all traces): 24.8% median per trace

## Collection

- car_logger_pieces: 378
- identifiable_full_gpx: 145
- anonymous_pieces_stitched: 34
- duplicates_dropped: 11
- identifiable: 142
- anonymous: 152

## Settings

- segment lengths: (50.0, 25.0) m
- thinning for matching: >= 5.0 s
- split at gaps > 300 s or steps > 60 km/h
- stop rule: window60_10 ('window', 60, 10) (draft; see the stop-rule sensitivity check)
- map-matching: leuvenmapmatching DistanceMatcher {'obs_noise': 15, 'obs_noise_ne': 30, 'dist_noise': 15, 'max_dist': 60, 'max_dist_init': 60, 'non_emitting_states': True, 'max_lattice_width': 8, 'only_edges': True}
- slope: (z_end - z_start) / length along travel, 5 m USGS 3DEP DEM; + = uphill (tested)
- suspect flag (kept, not dropped): speed > 30 km/h, abs(slope) > 0.8, or match error > 40 m
- suspect share of hiking trail segments: 0.83%
- car-logger accounts dropped: ['dragonpilot', 'frogpilot', 'openpilot', 'sunnypilot']

## Known limitations

- The stop rule is a draft until the hand-labeled sheet is scored.
- OSM trails are often traced from these same uploads, so match errors look smaller than true trail-position errors.
- Uploaders are mappers and enthusiasts, not a random sample of hikers (plan sec. 8).
