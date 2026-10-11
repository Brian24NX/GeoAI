# Progress log

One entry per working day: what was done, the numbers, decisions, what's
next. Details and reasons for every decision: `DECISIONS_LOG.md`.

## Status (11 Oct 2026)

**Stage: finishing T1** (the trajectory dataset), multi-region, on the lab
cluster. T2 (remote-sensing covariates) is next, per Danni (9 Oct: "finish
T1 completely, then T2 per the timeline").

| Region | Data | Hiking traces | Walking hikes | Peak speed v0 (km/h) | Slope sensitivity k |
|---|---|---|---|---|---|
| White Mountains, NH | API + lab | 235 | 188 | 4.22 | 2.10 |
| Cascades I-90 + Alpine Lakes, WA | API + lab | 684 | 528 | 4.37 | 1.72 |
| Front Range (Boulder–Golden), CO | API + lab | 206 | 96 | 4.36 | 1.87 |
| Lake Tahoe, CA/NV | API + lab | 230 | 94 | 4.17 | 1.67 |
| Olympic NP, WA | API + lab | 175 | 163 | 4.08 | 1.10 (coarse DEM) |
| Great Smoky Mountains, TN/NC | API + lab | 69 | 58 | 3.95 | 1.06 |
| Adirondack High Peaks, NY | API + lab | 103 | 73 | 4.05 | 2.20 |
| Catskills, NY | API + lab | 73 | 60 | 4.19 | 1.91 |
| Yosemite, CA | API + lab | 92 | 86 | 4.17 | 1.88 |
| Green Mountains, VT | API + lab | 56 | 24 | 4.43 | 2.39 |
| North Shore, Vancouver BC | lab only (full download queued) | 91 | 65 | | |
| San Gabriels, Columbia Gorge, Wasatch, Bay Area | lab-only builds running; full downloads queued | | | | |
| Shenandoah, Pisgah | full downloads running | | | | |
| **All built regions pooled (first 10)** | | **1,923** | **1,369** | **4.25** | **1.80** |

Tobler (1993): v0 = 6.0 km/h, k = 3.5, fastest slope −5%.

---

## Sun 11 Oct 2026

- Shenandoah and Pisgah: left out 5 tiles with highway traffic and no
  hiking signal in the lab crawl (decision #75). Saves ~5–7 h of OSM API time.
- **Two paths in parallel** (Brian's idea): fast *lab-only* builds for the 5
  city regions now (trail maps + elevation + lab traces; ~15–30 min each),
  while their full OSM downloads continue; a finished full download rebuilds
  the region with everything. North Shore built (lab-only): 91 hiking
  traces, 65 walking hikes.
- The size probe now counts tiles that hit the API's depth limit as capped
  instead of skipping the whole region.
- GitHub repo created (private) with this daily log.

## Sat 10 Oct 2026

- **Moved the whole T1 pipeline to the lab cluster** (03:30): project copy
  `/engrfs/project/jacobsn/zhou.n/travel-speed/`, Python 3.12 env, Slurm
  jobs: one polite OSM download queue; each finished region submits its own
  elevation + build jobs. Limits found: ≤ 8 CPUs/job, ≤ 4 running jobs.
- Robustness after a 5-hour network outage on the laptop (decision #67):
  download passes retry stopped tiles; builds require complete downloads;
  USGS elevation fallbacks (direct image, then 4 stitched quarters).
- **OSM API depth limit** (decision #70): the trackpoints API times out
  past ~page 906 of one area; such tiles count as complete up to that limit
  (Cascades Issaquah tile reaches back to Oct 2009; Boulder tile to Aug 2009).
- Fixed: builder read only 600 cached pages per tile; corrupt GPX points
  (NMEA text as coordinates) crashed 5 builds.
- **10 regions built**: 1,923 hiking traces (1,857 independent outings),
  1,369 walking hikes, 3,608 walking hours, 294 bike/ski traces. Pooled
  walking curve: v0 4.25 [4.16, 4.33] km/h, k 1.80 [1.72, 1.87], fastest
  slope −4.5%.
- Elevation source under walked trails (decision #73): 1 m lidar for
  87–100% of segments, except Olympic (29%). Olympic's low k is partly a
  coarse-DEM artifact; the Smokies' isn't.

## Fri 9 Oct 2026

- Morning: weekly meeting with Danni and Tianyi (T1 v0 results).
  **Decisions:** finish T1 completely, then T2; do as many regions as
  possible across the US / North America; lab storage access requested via
  Mark Bober (EIT).
- 1 m elevation downloaded overnight for every walked White Mountains trail.
- Lab storage access works. `OSM_data` = the lab's crawl of the original
  files of ~1.5M public + identifiable OSM traces (2016–2022). Indexed on the
  cluster; 23 candidate regions scouted; traces extracted per region.
- T1 pipeline generalized to any region (`regions.py`, `--region`).
- White Mountains T1 v1: + lab traces, near-duplicate removal, outings →
  235 hiking traces (218 outings); curve unchanged.
- T1 checks done: 50 m segments kept (25 m gives the same curve); 1 m vs 5 m
  slope: no difference (the curve's rounded top is real); map-match rate 97%,
  failures are correct non-matches; travel mode anchored on foot-only
  trails (walk / run / bike-or-ski); 10 km blocks for geographic hold-out;
  sampling-interval stratification.

## Thu 8 Oct 2026

- T1 started for the White Mountains (agreed with Danni 2 Oct): full tile
  download + original GPX files; HMM map-matching test (median 100% matched,
  2.2 m); blind stop-labeling sheet.
- T1 v0 built overnight: 192 hiking traces, 34,652 trail segments; walking
  curve v0 4.25 km/h, k 2.08, fastest slope −5%; robust across 4 stop
  rules; out-and-back pairs: downhill only ~15% faster (Tobler: 42%).

## Fri 2 Oct 2026

- Gate 1 run on real OSM data for 3 candidate regions (v2 of the audit
  script after real data exposed 3 bugs). Usable on-trail share 44–54%.
- Meeting with Danni: **region = White Mountains**. Progress Report #1
  submitted.

---

## Next (as of 11 Oct)

See `docs/NEXT_STEPS.md` (written 11 Oct) for the plan from here to the
IGARSS paper.
