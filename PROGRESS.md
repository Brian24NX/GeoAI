# Progress log

One entry per working day: what was done, the numbers, decisions, what's
next. Details and reasons for every decision: `DECISIONS_LOG.md`.

## Status (12 Oct 2026, 03:00 CDT)

**Stage: T1 complete; T2 tier 1 done; T3 harness running on everything.**
- **T1:** 17 regions, 16 from full OSM downloads plus the lab crawl, and the
  Bay Area from the lab crawl only.
- **T2:** elevation terrain at 5 m and 1 m, vegetation, satellite
  embeddings.
- **Lead result:** terrain from elevation data beats OSM tags in unseen
  regions (`docs/NEXT_STEPS.md` §1a).

| Region | Data | Hiking traces | Walking outings | Peak speed v0 (km/h) | Slope sensitivity k | 1 m lidar under trails |
|---|---|---|---|---|---|---|
| White Mountains, NH | API + lab | 235 | 189 | 4.23 | 2.10 | 100% |
| Adirondack High Peaks, NY | API + lab | 103 | 74 | 4.06 | 2.21 | 99% |
| Catskills, NY | API + lab | 73 | 60 | 4.19 | 1.91 | 100% |
| Green Mountains, VT | API + lab | 56 | 25 | 4.52 | 2.46 | 100% |
| Shenandoah, VA | API + lab | 83 | 41 | 4.57 | 1.14 | 100% |
| Great Smoky Mountains, TN/NC | API + lab | 69 | 58 | 3.95 | 1.06 | 88% |
| Asheville / Pisgah, NC | API + lab | 75 | 38 | 4.02 | 1.21 | 90% |
| Colorado Front Range (Boulder–Golden) | API + lab | 206 | 97 | 4.46 | 1.94 | 96% |
| Wasatch Front (Salt Lake City), UT | API + lab | 131 | 91 | 4.80 | 2.06 | 92% |
| Cascades I-90 + Alpine Lakes, WA | API + lab | 684 | 528 | 4.37 | 1.72 | 83% |
| Columbia River Gorge, OR/WA | API + lab | 104 | 67 | 4.63 | 1.55 | 27% (mostly 3 m) |
| Olympic NP (north), WA | API + lab | 175 | 163 | 4.08 | 1.10 (coarse DEM) | 34% |
| Bay Area hills, CA | lab only | 177 | 102 | 4.42 | 1.37 | 98% |
| San Gabriel Mountains (LA), CA | API + lab | 141 | 116 | 4.08 | 1.93 | 100% |
| Yosemite Valley + High Sierra, CA | API + lab | 92 | 86 | 4.17 | 1.88 | 70% |
| Lake Tahoe, CA/NV | API + lab | 230 | 94 | 4.17 | 1.67 | 95% |
| North Shore Mountains (Vancouver), BC | API + lab | 242 | 165 | 4.38 | 1.64 (coarse DEM) | 0% |
| **All 17 pooled** | | **2,876** | **1,994** | **4.31** | **1.80** | |

Tobler (1993): v0 = 6.0 km/h, k = 3.5, fastest slope −5%. Walking analysis
set: 290,640 segments of 50 m, 1,992 outings, 4,702 moving hours, 14,532
km.

---

## Mon 12 Oct 2026

- **Overnight refresh on the complete T1** (00:00–02:34, decision #95):
  rebuilt the combined dataset, checks, all covariates and all 8 harness
  runs.
- **Final unseen-region scores** (CRPS skill vs our refitted slope curve):
  - Tobler −12.5%; Campbell −0.5%; STRIDE −16.8%.
  - Tags +0.9% / +0.4%.
  - **Terrain +2.1% / +2.8%**, beating tags in 16 of 17 regions.
  - Embeddings +1.1%; terrain + embeddings +2.6% / +2.8%; with tags too,
    up to +3.9%.
  - Personal pace + terrain +10.7% / +11.6%.
- **Whole-hike time** (median error): 13.6% (slope) → 13.2% (+ terrain) →
  9.5% (+ personal pace + terrain).
- **Terrain formula:** smooth trails 4.60 km/h, steppy ones 3.84 km/h;
  +1.0% in unseen regions with 5 numbers.
- Paper figures, explainer, outline and the 16 Oct brief now use these
  numbers.
- **Speed by travel mode** (T4, decision #96):
  - walking 4.31 km/h, running 10.8, bike/ski 18.0 (peak speeds);
  - bikes are much more slope-sensitive (k 4.6 vs 1.8);
  - the bike-to-walk ratio falls from ~4× on descents to ~1.6× on climbs,
    so a constant mode multiplier (Tobler's approach) fails for bikes;
    runners stay ~2.5×.
- **Uncertainty that depends on terrain** (decision #98): no gain over a
  fixed spread in log speed; ranges are already honest (~89% in 90%
  ranges).
- **Lidar understory pilot sized, not run** (decision #97): reader built
  for USGS point clouds on AWS. The White Mountains alone needs ~12 GB,
  and a small pilot has too few hikes. Question for Danni on 16 Oct.
- **Pace on every trail** (decision #99,
  `results/t4_trail_map/fig_wm_pace.png`):
  - The terrain function, trained on the other 16 regions, predicts pace on
    all 3,369 km of White Mountains trail, 77% of which nobody in our data
    walked.
  - Median 15.2 min/km vs Tobler's 12.8.
  - Tobler is too fast on gentle trails and too slow on steep ones.
- **Paper skeleton** (`paper/main.tex`, compiles to 4 pages): IEEE two-column
  stand-in template, section files with the points to make (TODO notes),
  Table I with the final numbers, the figures, checked references. The
  prose is Brian's.
- **De-identified copy of the dataset** ready on the cluster (decision #100;
  not published; needs the mentors' license decision).

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
- GitHub repo created (private): the whole GeoAI folder except `.venv/` and
  the 12 GB download cache; renamed to **GeoAI** to match the folder.
- **First multi-region findings** (12 regions, 237k walking segments, 1,503
  outings; `results/t1_findings/`):
  - a rounded-top curve beats Tobler's sharp peak;
  - downhill advantage grows 1.08 → 1.24 with grade (Tobler: 1.42);
  - variance after slope: 26% hiker/day, 74% along the trail, 2% region;
  - no fatigue effect.
- **Literature + data survey** (research agent). Our peak speed and rounded
  curve replicate Campbell et al. 2019/2022; Wood et al. 2023 (UK, OSM +
  lidar) is the closest analog; STRIDE (2024) is the lidar baseline. No
  prior work tests transfer to unseen regions, so the paper should lead
  with that: remote sensing vs map tags under leave-one-region-out. Free
  data: AlphaEarth embeddings (Source Cooperative mirror), Meta 1 m canopy
  height (AWS), 3DEP point clouds (AWS), MODIS/SNODAS snow. IGARSS: deadline
  11 Jan 2027 confirmed, portal opens 10 Nov.
- Plan to the paper written: **`docs/NEXT_STEPS.md`**.
- **`Project_Explainer.html`**: one visual page explaining the whole project
  (basics, design, plan, story, pipeline, dataset map, findings, literature,
  next steps, glossary), drawn from the real numbers. Rebuild with
  `make_explainer_data.py` (cluster) + `make_explainer.py`.
- All 5 lab-only builds finished (North Shore, San Gabriels, Columbia Gorge,
  Wasatch, Bay Area): **15 regions built**, 2,375 hiking traces, 1,666
  walking outings, ~4,100 walking hours, 387 bike/ski traces; pooled walking
  curve v0 4.27 km/h, k 1.78. Full downloads continue.
- **Shenandoah built** (full download, 05:50): 83 hiking traces, 41 walking
  outings; one tile capped by the API's time limit (reaches back only to May
  2023; decision #77). **16 regions built**: 2,458 hiking traces, 1,707
  walking outings, 4,172 h; pooled v0 4.28 km/h, k 1.78.
- **Pisgah built** (08:50): 75 hiking traces, 38 walking outings, 32
  bike/ski. **All 17 planned regions are built** (12 full + 5 lab-only):
  2,533 hiking traces, 1,745 walking outings, 4,227 walking hours, 446
  bike/ski traces; pooled v0 4.27 [4.21, 4.33] km/h, k 1.78. Left for T1:
  upgrading the 5 lab-only city regions with their full downloads (North
  Shore running), plus the optional stop-rule hand check.
- **T1 close-out** (morning):
  - Elevation source under the trails, all 17 regions (decision #78): 1 m
    lidar under ≥ 83% of walked trail in 13 regions; weak in Yosemite
    (70%), Olympic (29%), the Columbia Gorge (21%, mostly 3 m) and the North
    Shore (0%: USGS has only ~10 m in Canada).
  - **Mode check** (decision #79): 246 hiking traces whose own GPS app
    named the activity (Garmin "hiking", Strava "Afternoon Ride", ...). 93%
    of labeled hikes were called walking; only 3% of the traces we call
    walking were labeled bike or ski.
  - **One combined dataset** (decision #80): `data/t1_all/` on the cluster.
    It holds 627k segments of hiking traces, with the walking analysis set
    flagged: 261k segments, 1,744 outings, 4,227 h, 13,054 km. One data
    card explains every column (`results/t1_all/DATA_CARD.md`).
- **T3 evaluation harness, first results** (`t3_harness.py`, decisions #81,
  #82). Each model predicts a speed distribution for every 50 m walking
  segment; scored on held-out outings, held-out 10 km blocks, and **held-out
  regions** (leave one of 17 out):
  - **Tobler as published is 13% worse** (CRPS) than a slope-only curve
    refitted to our data, and explains none of the variance (R² −0.07 vs
    0.17).
  - Curve shape barely matters once refitted (tent, rounded, Lorentz:
    within 0.5%).
  - **OSM tags help little:**
    - within a region: +1%;
    - in an unseen region: +0.2% (additive model);
    - boosted trees on tags get worse in unseen regions (−0.9%).
  - **The hiker matters more than the map.** Knowing a hiker's pace from
    their first km cuts whole-hike moving-time error from 13.7% to 9.9%
    (median) in unseen regions. 1 km stretch error drops from 17% to 14%.
  - **Place memory** (how fast *other* hikers went in the same 100 m
    cell) adds +1.3% within a region. Tags reach ~75% of that there, but
    keep little of it in new regions. That gap is what remote sensing has
    to close.
  - Calibrated: 90% intervals cover 88% of held-out speeds.
- **First remote-sensing result** (White Mountains pilot, decision #83):
  - Terrain from the 1 m lidar DEM along each segment's path: roughness,
    "steppiness" of the profile, side slope.
  - Raw pattern: the smoothest fifth of segments is ~14% faster than the
    slope curve says; the steppiest fifth ~11% slower.
  - CRPS skill, new hikers: **lidar +3.8%**, tags +1.7%, place memory
    +1.5%.
  - New 10 km squares: **lidar +3.1%**, tags +0.7%.
  - So lidar beats tags 2–4× in this region and holds up in unseen map
    squares.
- **1 m elevation for all 16 US regions downloading** on the cluster
  (decision #84): ~12.5 GB from USGS 3DEP, ~9 h, in parallel with the OSM
  queue. It feeds the leave-one-region-out test of lidar vs tags, the
  paper's lead.
- **The lead result, all 17 regions** (decision #85):
  - The same terrain profile, read from the 5 m elevation T1 already had (in
    the White Mountains 5 m ≈ 1 m).
  - **In regions the model never saw:** terrain +1.6% (additive) / +2.2%
    (trees) CRPS skill; tags +0.2% / −0.9%.
  - **Terrain beats tags in 15 of 17 held-out regions**; the other two are
    ties.
  - Control: ~60% of the gain is uneven grade *inside* the 50 m segment,
    which a DEM sees and an average slope or a tag can't; ~40% is
    difficulty beyond grade.
  - With the hiker's own pace: +10.3–11.0%, and whole-hike time error
    13.7% → 9.4%.
- **North Shore rebuilt from its full download** (10:53): 242 hiking traces
  (was 91 lab-only), 165 walking outings, v0 4.38 km/h. All 17 pooled:
  2,684 hiking traces, 1,848 walking outings, 4,374 h, v0 4.27 km/h. San
  Gabriels downloading next (≤ 2,307 pages).
- Paper outline: `paper/OUTLINE.md` (4-page budget, Table 1, figures).
- 95% bootstrap intervals (resampling whole regions): terrain minus tags in
  unseen regions +0.7 to +2.4 points, above zero in every draw.
- What "terrain" means in speed, all 17 regions (`t2_terrain_effects.py`):
  - the smoothest fifth of trail profiles is ~9% faster than slope alone
    predicts; the steppiest fifth ~8% slower;
  - every region shows the same direction;
  - side slope doesn't matter.
- Draft paper figures: `paper/figures/fig_skill.png` (skill by model with
  CIs) and `fig_regions.png` (terrain vs tags per held-out region).
- **San Gabriels rebuilt from its full download** (13:55): 141 hiking traces
  (was 81 lab-only), 116 walking outings, v0 4.08 km/h. One LA-side tile is
  capped by the API's time limit and reaches back only to July 2023 (like
  Shenandoah, decision #77). All 17 pooled: 2,744 hiking traces, 1,892
  walking outings, 4,481 h, v0 4.28 [4.21, 4.36] km/h. Columbia Gorge
  downloading next (≤ 3,076 pages).
- The 1 m elevation download is slower than estimated: the Cascades alone
  have 2,766 cells (~3.5 h). ETA for all regions ~21:00 CDT.
- Robustness (decision #86): terrain is not a proxy for "which region". It
  adds ~1.8 points on top of each region's own speed offset.
- **Vegetation from 30 m national maps adds nothing** (decision #87): tree
  canopy cover and land cover (NLCD 2021) give +0.0% in unseen regions,
  alone or with terrain. The remote-sensing signal is in the elevation
  data; fine-scale understory from lidar points is the last vegetation test.
- **Published baselines added** (decision #88):
  - Campbell et al. 2022's median curve (Utah and California AllTrails
    hikes, nothing fitted on our data) ties our refitted slope curve in
    unseen regions (−0.6%, interval includes 0), against Tobler's −13%.
  - It is region-dependent: −10% in the Adirondacks, +4% on the North Shore.
  - STRIDE (lidar model, coefficients from its R package) enters with the
    1 m roughness run tonight.
- **Columbia Gorge rebuilt from its full download** (20:23): 104 hiking
  traces (was 43 lab-only), 67 walking outings, v0 4.63 km/h. All 17
  pooled: 2,805 hiking traces, 1,935 walking outings, 4,597 h, v0 4.29
  km/h. Wasatch downloading (≤ 2,436 pages), then the Bay Area.
- The 1 m elevation download finished (~20:20, 12,499 cells); 1 m terrain
  and STRIDE roughness are being computed for all regions.
- **1 m lidar results** (decision #89):
  - 1 m terrain ≈ 5 m terrain in unseen regions (+1.5–2.4%); terrain beats
    tags in 16 of 17 regions.
  - STRIDE as published −17.7% (worse than Tobler: its roughness term
    over-penalizes trails); refitted +0.1%.
  - The trail's elevation profile carries the signal, not micro-roughness.
- **Satellite embeddings pilot** (decision #90; AlphaEarth 2022 from the
  free Source Cooperative mirror, CC-BY):
  - White Mountains: +2.6–3.3% alone, +4.6–4.9% with terrain
    (complementary).
  - Running for all 17 regions overnight (~10–15 GB) for the unseen-region
    test.
- Draft meeting brief for 16 Oct: `Meeting_Prep_Oct16.md`.
- **A terrain-adjusted hiking function** (T4, decision #91): Tobler's
  formula with peak speed and slope sensitivity depending on trail
  steppiness, one number from any DEM.
  - Smooth trails peak at 4.56 km/h, steppy ones at 3.82.
  - +0.65% in unseen regions; beats tags in 11 of 17 regions.
- **Whole-hike times** (decision #92, 1,199 hikes in unseen regions): median
  error Tobler 14.0%, slope curve 13.7%, + terrain 13.0%, + personal pace
  + terrain 9.5% (52% of hikes within ±10%).
- **Satellite embeddings, all 17 regions** (decision #93):
  - Within regions they're strong (+2.9% with trees; +4.5% with terrain).
  - In unseen regions they're unreliable: +0.7% / −0.1%, ranging from +5%
    to −5% by region.
  - Terrain from elevation data is what transfers.
  - Paper angle: "embeddings help locally, lidar terrain transfers".
- **T1 complete** (23:59):
  - Wasatch rebuilt from its full download: 131 hiking traces (was 60
    lab-only), 91 walking outings, v0 4.80 km/h.
  - The Bay Area stays lab-only: the API times out on its freeway-dense
    tiles (decision #94).
  - Final T1: 17 regions (16 full + 1 lab-only), 2,876 hiking traces,
    1,994 walking outings, 4,702 walking hours, 490 bike/ski traces; pooled
    v0 4.31 [4.23, 4.37] km/h, k 1.80.
  - An overnight refresh (`cluster/refresh_all.sh`) rebuilds the combined
    dataset, checks, covariates and every harness run on the final T1.

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
