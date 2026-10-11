# Gate 1 kit — travel speed project

This folder answers the first big question of the project:
**are the GPS hiking tracks on OpenStreetMap actually usable?**

> **Version 2 (2 Oct 2026).** Version 1 was built and tested on fake data only.
> On real data it had three bugs that would have made the headline number
> wrong (see "What version 1 got wrong" below). Version 1 is kept in
> `archive/` and in `../travel-speed-gate1.zip`.

## What's in here

| File | What it is |
|---|---|
| `gate1_audit.py` | The Gate 1 checker. Downloads GPS tracks and OSM trails for a region and tells you how many are usable and how fast people move. |
| `region_layers.py` | The non-trace columns of the region table: 1 m LiDAR coverage, relief, tree canopy. |
| `first_look_slope.py` | A first, unvalidated look at slope vs. speed against Tobler (plan §9 diagnostic preview). Downloads a 5 m USGS DEM per box once. |
| `selftest.py` | Tests the checker on fake data (29 checks). No internet needed. |
| `requirements.txt` | The packages Gate 1 needs. |
| `environment.yml` | The full toolset for later (T1–T3). **Not needed yet.** |
| `cache/` | Every download (GPS pages, OSM trails, USGS layers and DEMs), saved once. **Don't delete** — it's ~0.6 GB of polite downloading. |
| `results/` | Outputs from the real runs (one folder per region, plus the comparison files). |
| `example_output/` | Version 1's outputs on **fake** data, kept for reference. |
| `archive/` | Version 1 of the scripts. |

---

## How to run it

A Python environment already exists in `../.venv` (made on 2 Oct). From this
folder:

```
../.venv/bin/python selftest.py                        # 1 min, no internet: should end ALL CHECKS PASSED
../.venv/bin/python gate1_audit.py --region all        # uses cache/, so it's fast now
../.venv/bin/python region_layers.py                   # LiDAR / relief / canopy columns
../.venv/bin/python first_look_slope.py                # slope vs speed vs Tobler (first look)
```

To start from scratch on a new machine: `pip install -r requirements.txt` first.

Add `--offline` to re-run from `cache/` only, with no downloading at all. If a
download stops halfway, run the same command again: it picks up where it
left off and never downloads the same page twice.

---

## What the script does, in plain English

**1. Download GPS points.** For 4 small boxes per region it asks OpenStreetMap
for every GPS point inside the box, 5,000 points per page. Every page is saved
to `cache/`.

**2. Count usable vs. unusable.** When people upload a GPS track to OSM, they
choose a privacy level:

- **identifiable**: points in time order, with the uploader's name → ✅ usable
- **trackable**: points in time order, anonymous → ✅ usable
- **public** / **private**: no timestamps, points sorted by latitude → ❌ no speed possible

The API sends **all the usable points first**, then all the unusable ones. So
the script reads pages until the unusable points start, then jumps ahead
(+1, +2, +4, … pages) to find the last page. That gives an exact count without
downloading every unusable page.

**3. Download the trails and roads** in each box from OSM (Overpass API), and
match every GPS point to the nearest one (within 25 m). That separates hikers
from cars, ski lifts and the Mt Washington Cog Railway. It also tells us which
modes each trail allows, using its `bicycle=` and `horse=` tags. The public
Overpass servers are often "too busy" at night. The script retries, tries
backup servers, and finally asks for the box in 16 smaller pieces (busy
servers still answer small questions).

**4. Compute speed** between points at least 10 seconds apart:
speed = distance ÷ time.

> Worked example: two points 25 m apart, recorded 30 s apart →
> 25 ÷ 30 = 0.83 m/s → × 3.6 = **3.0 km/h**

**5. Remove stops, two ways**, so they can be compared:

- the crude rule from plan §6: anything under 0.5 km/h is a stop
- a draft rule for plan §8 ("speed + minimum duration"): any stretch of at
  least 60 s that ends less than 10 m from where it started is a stop

**6. Report.** It prints a summary and saves, in `results/<region>/`:

- `summary.json`: the key numbers, plus every threshold used (feeds the decisions log)
- `traces.csv`: one row per trace
- `speed_histograms.png`: speeds on trails, the plot for the weekly meeting
- `trace_map.png`: where the usable points are, colored by trail / road / other

With `--region all` it also writes `results/region_comparison.csv` and
`results/region_comparison.png`.

---

## How to read the results

The two most important lines (White Mountains, 2 Oct 2026):

```
Usable points: 310,645 of 536,431 (58%)   <- write this down (plan sec. 6)
On trails only: ~46% of GPS points are usable (...)
```

The plan says this fraction goes in the paper, and nobody knew it before.
**Report both.** The first counts every point, including car loggers on
highways. In some boxes (Boulder, Snoqualmie) most usable points are car
logs from *sunnypilot*/*dragonpilot* driver-assist software. The second
counts only points within 25 m of an OSM trail, which is what matters for
hiking. Its unusable side is estimated from a sample of pages spread across
each box.

Then the three Gate 1 checks from plan §6:

1. **Enough usable traces?** The plan gives no number, so decide with Danni
   and Tianyi. Look at **trail traces** and **outings**, not raw traces. Raw
   traces include cars, duplicates and group hikes.
2. **Median on-trail speed between 1.5 and 5 km/h?** That's normal walking.
3. **A second, faster bump?** That's cyclists. If it's there, Question 4
   (bikes vs. walkers) might be possible. The "permitted mode" line tells you
   whether the trails even allow bikes.

---

## What version 1 got wrong (found on real data)

1. **Paging bias.** Version 1 read at most 10 pages. Because the API sends
   every usable point first, a busy box looked ~100% usable. The Mt Washington
   box has 22 full pages of usable points before the first unusable one. Its
   true value is 60%.
2. **Multi-hike uploads thrown away.** One upload can hold several recordings
   stored out of date order (one hiker's whole winter in one file). Version 1
   saw time "going backwards" and called it shuffled. Version 2 checks each
   recording segment separately.
3. **Car loggers read at walking pace.** Some loggers record 10 points per
   second but store whole seconds only. Version 1 skipped the zero-time pairs
   and read a 40 km/h car at ~7 km/h. Version 2 keeps the first point of each
   second.

## The two lessons from the fake-data test, revisited on real data

**Lesson 1: the 0.5 km/h stop filter misses stops.** On fake data it caught
1% of a 20% stop. On real data it does better, because many phones freeze the
position while you stand still. It still disagrees with the minimum-duration
rule. See `summary.json` → `trail_time_removed_pct`.

**Lesson 2: frequent recording inflates speed.** The fake 1-second walker was
+168%. On real walkers recorded every 1–2 s it's much smaller: about +2% for
12 White Mountains walkers. Real GPS errors drift slowly, so neighboring
points are wrong together, just as the version 1 notes predicted. Version 2
measures over steps of 10 s or more either way.

---

## Known limitations (say these out loud if asked)

- Nearest-way matching is not real map-matching: near junctions and where a
  trail runs beside a road, a point can pick the wrong way. Real HMM
  map-matching is a T1 job. Sidewalks and crosswalks (`footway=sidewalk`,
  `crossing`, ...) are NOT counted as trails. Before that rule, car points in
  Boulder snapped onto them.
- Car-logging software (sunnypilot, dragonpilot) uploads lots of
  "identifiable" traces. They stay out of trail numbers, but they swell the
  "all points" usable % and fill the newest pages (Boulder: ~500 pages of
  them, so that box is cut at `--max-pages`).
- The draft stop rule is not tuned.
- A trackable trace that a page break splits exactly between two recording
  segments is counted twice.
- A hike crossing two boxes is counted in both.
- "Walking-like" and "cycling-like" are just speed ranges, not mode inference.
- The boxes are a sample of popular areas, not whole regions. Edit them in
  `REGIONS` at the top of `gate1_audit.py`.
- Page order shifts whenever someone uploads a new trace, so pages cached on
  different days may not line up exactly.

## T1: building the dataset (from 8 Oct 2026)

Region: the White Mountains (agreed with Danni, 2 Oct). Run these in order;
everything is cached, so re-runs are cheap.

| Script | What it does |
|---|---|
| `t1_download.py` | Downloads every GPS trace in the White Mountain National Forest (12 tiles), plus the **original full GPX** of each identifiable trace. ~3.3M points. (Its quick Gate 1 count says 212 hiking traces; the T1 build, after map-matching and de-duplication, keeps 192 = 235 hiking days.) |
| `t1_prefetch_dem.py` | Downloads a 5 m USGS elevation grid for every tile, in quarters (USGS times out on bigger images). |
| `t1_mapmatch_test.py` | The map-matching test on 17 hikes (HMM matcher `leuvenmapmatching`): median 100% matched, 2.2 m from the trail. |
| `t1_build_dataset.py` | **The T1 dataset.** Cleans every hike, flags stops, map-matches it, and cuts it into 50 m and 25 m trail segments with speed, signed slope, direction, trail tags, permitted modes, date and uploader. Writes `data/t1_white_mountains/` (segment tables, matched points, `traces.csv`, `data_card.md`). Runs a sign test first, so uphill is always positive. |
| `t1_variants.py` | Stop-rule sensitivity check: rebuilds the segments under 4 stop rules (from the saved points, no re-matching) and fits the slope–speed curve under each, with 95% intervals from resampling whole hikes. |
| `t1_meeting_figures.py` | The figures and numbers for the weekly meeting (`../meeting_plots/oct9/`), plus the extra checks quoted in the 9 Oct notes: Tobler's error in hours, out-and-back ratios by grade, `sac_scale` vs speed, winter vs the rest, and bad dates. |
| `make_stop_sheet.py`, `score_stop_labels.py` | The hand-check of stops: a blind sheet of 20 moments, and a scorer that compares 36 stop rules with the answers. **Still to do**: a careful labeling pass. |

| `regions.py`, `scout_regions.py` | The 23 candidate regions (US + Vancouver) and a scout that counts hike-like traces per region in the lab index (`results/region_scout.csv`). |
| `t1_queue.py` | Downloads many regions unattended: OSM one region at a time (`--probe` skips huge, city-dominated regions); 5 m elevation in a parallel queue. |
| `t1_slope_check.py` | Segment length (25 vs 50 m) and 1 m vs 5 m slope, using the 1 m elevation. |
| `t1_match_qa.py` | Map-matching rate and pictures of the worst-matched hikes. |
| `t1_modes.py` | Travel mode per trace (walk / run / bike) with a confidence, anchored on foot-only trails (draft). |
| `cluster/` | Scripts that run on the lab cluster: `build_lab_index.py` (index of the lab's 1.5M-trace crawl) and `extract_lab_traces.py` (full traces for each region). |

Every T1 script takes `--region <key>` (default `wm`, the White Mountains).
Add `--sample [white_mountains|cascades|front_range]` to the build to run on
a Gate 1 region's 4 small boxes instead (about a minute).

**Lab data (from 9 Oct).** `/engrfs/project/jacobsn/OSM_data` on the cluster
holds the original files of ~1.5M public + identifiable OSM traces uploaded
2016–2022, with timestamps. The API strips the timestamps from "public"
traces, so these are extra hikes. The builder adds them from
`cache/lab_traces/<key>.parquet`.

## T1 for many regions (from 9 Oct 2026)

Danni (9 Oct): finish T1 first, over as many US / North American regions as
possible. The order for one region (`t1_queue.py` does all of it
unattended, region after region):

1. `t1_download.py --region <key>`: OSM trace pages + original GPX files
   (one region at a time: the OSM API is volunteer-run).
2. `t1_prefetch_dem.py --region <key>`: 5 m elevation grids (USGS).
3. `t1_build_dataset.py --region <key>`: matching, segments (with
   `segment_id` and the matched path as `geometry_wkt`), outings, flags.
   Adds the lab crawl's traces from `cache/lab_traces/<key>.parquet`.
4. `t1_modes.py data/t1_*`: travel mode for **all** built regions (anchors
   are pooled).
5. `t1_variants.py --region <key>`: the curve under 4 stop rules.
6. `t1_finalize.py --region <key>`: `trail_network`, `block_10km` (for
   geographic hold-out), and the final data-card section.
7. `t1_summary.py`: one table and two figures across all built regions
   (`results/t1_summary/`).

**Where it runs (from 10 Oct): the lab cluster.** Project copy at
`/engrfs/project/jacobsn/zhou.n/travel-speed/`, Python env at
`/engrfs/project/jacobsn/zhou.n/envs/t1`. Submit with
`sbatch cluster/t1_osm_job.sh`; it downloads one region at a time and submits
each region's elevation and build jobs (`cluster/t1_region_job.sh`). Progress:
`logs/t1_queue.log` on the cluster; `squeue -u zhou.n` for jobs. To bring
results to the laptop: `rsync -a zhou.n@shell3.engr.wustl.edu:/engrfs/project/jacobsn/zhou.n/travel-speed/{data,results,logs} .`

**Close-out and checks (11 Oct).** Run these on the cluster after the
builds:

| Script | What it does |
|---|---|
| `t1_findings.py` | Curve shape (cross-validated forms), who vs where (variance between and within outings), fatigue, up/down asymmetry, over all regions (`results/t1_findings/`) |
| `t1_dem_quality.py` | Which elevation source (1 m lidar or coarser) sits under each region's walked trails (`results/t1_dem_quality.csv`) |
| `t1_mode_check.py` | Mode calls vs the activity the uploader's own app wrote into the GPX file ("hiking", "Afternoon Ride" ...) (`results/t1_mode_check/`) |
| `t1_combine.py` | One dataset for all regions: `data/t1_all/` (segments, traces, regions, `DATA_CARD.md`). It stays on the cluster (user names, size); the card and region table are copied to `results/t1_all/` |

## T3: the evaluation harness (from 11 Oct 2026)

`t3_harness.py` scores every model the same way.
- **What each model predicts:** a speed distribution for each 50 m walking
  trail segment.
- **How it is tested:** never on the outings it was fitted on. Three splits:
  5 folds of outings, 5 folds of 10 km blocks, and leave one region out.
- **Models:**
  - Tobler as published;
  - refitted slope curves;
  - OSM tags (additive and boosted trees);
  - place memory (the ceiling for anything place-based);
  - personal pace (the hiker's first km).
- **Scores:** CRPS, interval coverage, and moving-time errors over 1 km
  stretches and whole hikes.

Run it on the cluster (8 CPUs, ~4 min) with `python t3_harness.py`. Two
options:
- `--quick`: a 15% smoke test;
- `--figure`: only redraw the figure.

Results go to `results/t3_harness/`. The remote-sensing arms plug into
`ARMS` once T2's covariates exist.

## T2: remote-sensing covariates (from 9 Oct 2026)

| Script | What it does |
|---|---|
| `t2_prefetch_dem1m.py` | Downloads the **1 m USGS 3DEP elevation** for every 500 m × 500 m cell the T1 hikes walked through (1,832 cells, ~1.8 GB, ~1.5 h), into `cache/dem1m/`. Grid: UTM zone 19N, 1 m pixels, cells aligned to multiples of 500 m. Resumes where it stopped. `--dry-run` just counts the cells. |

## Be polite to OpenStreetMap

OSM runs on volunteers' servers. The script waits 1 second between downloads,
identifies itself, and never downloads the same page twice. Don't remove the
wait, and don't delete `cache/` unless you really mean to re-download.
