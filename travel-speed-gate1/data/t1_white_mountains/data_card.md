# Data card: t1_white_mountains (T1, built 2026-10-09 22:05 UTC)

One row per (trace x fixed-length segment) traversal; see t1_build_dataset.py for every step.

## Counts

- traces processed: 342 (named = identifiable or public 195, anonymous 147)
- by source: {'tile pieces': 147, 'original GPX': 141, 'lab original file': 54}
- hiking traces (>= 5 moving min on trails): 235
- independent outings among hiking traces (group hikes and multi-phone recordings merged): 218
- named uploaders among hiking traces: 54
- 50 m trail segments from hiking traces: 37,739
- median share of each trace matched: 100.0%
- time removed as stops (all traces): 24.5% median per trace

## Collection

- car_logger_pieces: 378
- identifiable_full_gpx: 145
- anonymous_pieces_stitched: 34
- lab_traces_already_from_api: 37
- lab_traces_added: 60
- lab_car_loggers: 4
- duplicates_dropped: 16
- near_duplicates_dropped: 7
- named: 195
- anonymous: 147

## Settings

- segment lengths: (50.0, 25.0) m
- thinning for matching: >= 5.0 s
- split at gaps > 300 s or steps > 60 km/h
- stop rule: window60_10 ('window', 60, 10) (draft; see the stop-rule sensitivity check)
- map-matching: leuvenmapmatching DistanceMatcher {'obs_noise': 15, 'obs_noise_ne': 30, 'dist_noise': 15, 'max_dist': 60, 'max_dist_init': 60, 'non_emitting_states': True, 'max_lattice_width': 8, 'only_edges': True}
- slope: (z_end - z_start) / length along travel, 5 m USGS 3DEP DEM; + = uphill (tested)
- suspect flag (kept, not dropped): speed > 30 km/h, abs(slope) > 0.8, or match error > 40 m
- suspect share of hiking trail segments: 0.90%
- car-logger accounts dropped: ['dragonpilot', 'frogpilot', 'openpilot', 'sunnypilot']
- local time zone: America/New_York
- OSM ways (trails, tags) from Overpass, downloaded 2026-10-08 to 2026-10-09
- traces with impossible dates (before 2005, flagged date_suspect): ['osm2731854', 'osm4893149']
- lab traces: original files of public + identifiable OSM traces uploaded 2016-2022 (lab crawl on ENGRFS), added unless the API gave the same trace id

## Known limitations

- The stop rule is a draft until the hand-labeled sheet is scored.
- OSM trails are often traced from these same uploads, so match errors look smaller than true trail-position errors.
- Uploaders are mappers and enthusiasts, not a random sample of hikers (plan sec. 8).

## T1 final (t1_finalize.py)

- travel mode of hiking traces (t1_modes.py): {'walk': 201, 'unknown': 21, 'bike/ski': 9, 'fast': 4}
- foot-only anchor traces called walking: 98 of 99
- walking trail segments (50 m, not suspect): 34,535 from 201 traces = 189 outings
- map-match rate: 95.3% of points (hiking traces 95.6%)
- trail networks with walking segments: 80; largest holds 40% of segments
- 10 km blocks with walking segments (unit for geographic hold-out): 51
- curve by GPS sampling interval (walkers): <= 2 s: 39 traces, v0 4.77 [4.30, 5.19], k 2.25; 2-6 s: 59 traces, v0 4.26 [3.75, 4.79], k 1.97; > 6 s: 103 traces, v0 4.09 [3.79, 4.29], k 2.13
- stop-rule sensitivity (walkers): window60_10 removes 29%, v0 4.23 [4.04, 4.44], k 2.10; window30_5 removes 22%, v0 4.15 [3.91, 4.37], k 2.17; window90_15 removes 30%, v0 4.21 [4.00, 4.42], k 2.07; crude05 removes 23%, v0 4.13 [3.93, 4.32], k 2.15
