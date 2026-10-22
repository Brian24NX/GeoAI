# IGARSS 2027 paper: outline (draft 1, 11 Oct 2026)

*An outline for Brian to write from: bullets, a page budget, the figure
plan and the numbers as of 11 Oct. Numbers marked (*) change when the
city regions finish their full downloads and the 1 m / canopy / embedding
covariates are added. AI assistance (Claude) drafted this outline, and
every section of the paper and the abstract for Brian to rewrite; the final paper text is
Brian's. Disclose AI use as the conference and course require.*

**Venue.** IGARSS 2027, Reykjavík. 4 pages, IEEE two-column. Deadline 11
Jan 2027; the portal opens 10 Nov. Student Paper Competition: needs an
advisor attestation. Best-fit themes: SP.6 (Datasets, Benchmarks and
Evaluation Methodologies) or SP.5 (Foundation Models and Embeddings for
EO).

**Working title.** *Does remote sensing beat the trail map? Predicting
hiking speed in unseen regions from lidar terrain and OpenStreetMap tags.*

**The one-sentence story.** Across 17 North American regions, terrain
measured from airborne-lidar elevation predicts hiking speed in regions a
model has never seen, where crowd-sourced map tags lose almost all their
value. A hiker's own pace still matters most.

---

## Page budget (4 pages)

| Section | Pages | Holds |
|---|---|---|
| 1 Introduction | 0.5 | problem, gap, 3 contributions |
| 2 Data | 0.75 | Fig. 1 (map + dataset numbers), the pipeline in one paragraph |
| 3 Methods | 0.75 | covariates, models, splits, scoring |
| 4 Results | 1.25 | Table I, Fig. 2 (speed vs slope, down/up), Fig. 3 (full width: skill by model, each region held out) |
| 5 Discussion + conclusion | 0.5 | what transfers and why; limits; release |
| References | 0.6 | 22; IGARSS kits of 2013–2017 count references inside the 4 pages (an earlier note that the 2026 kit doesn't could not be re-checked); check the 2027 kit |

---

## 1. Introduction (~0.5 page)

- Travel time on foot drives search and rescue, wildfire escape routes,
  trail apps and accessibility maps. GIS still uses Tobler's 1993 hiking
  function.
- Crowd-sourced GPS shows Tobler is too fast: Campbell et al. 2019 and 2022
  (Strava, AllTrails; Utah, California); Wood et al. 2023 (England and
  Wales, OSM + lidar). STRIDE (2024) models lidar terrain from timed field
  walks.
- **Gap:** no one has tested whether terrain covariates **transfer to
  regions the model has never seen**, against the map tags people use
  today, with calibrated uncertainty.
- **Contributions:**
  1. a 17-region dataset of 260k (*) walking traversals of 50 m trail
     segments, from public OSM traces;
  2. an evaluation protocol (leave one region out, CRPS, calibration) with
     baselines;
  3. the finding that DEM/lidar terrain transfers and map tags don't.

## 2. Data (~0.75 page)

- **Source:** OSM GPS traces (API pages + original files + the lab's crawl
  of 1.5M uploads). 17 regions in the US and Canada; 2,876 hiking traces;
  the walking analysis set has 2,046 traces in 1,992 outings, 4,702 moving
  hours, 290,640 segments of 50 m.
- **Pipeline (one paragraph):**
  - deduplicate (same recording, group hikes → outings);
  - stop removal;
  - HMM map-matching to OSM trails (97% of points);
  - 50 m segments along the matched path;
  - slope from USGS 3DEP;
  - travel mode anchored on foot-only trails.
- **Mode check:** against 246 traces whose own app recorded the activity,
  3% of "walking" traces are labeled bike or ski.
- **Data quality:** 1 m lidar under ≥ 83% of walked trail in 13 regions;
  capped API tiles noted.
- **Fig. 1:** map of the 17 regions (circle = walking hours) plus an inset
  of one region's segments colored by speed.

## 3. Methods (~0.75 page)

- **Target:** the distribution of ln(speed) for a walking trail segment.
- **Covariates:**
  - (a) slope;
  - (b) OSM tags: sac_scale, trail_visibility, surface, width, smoothness,
    mtb_scale, highway, access;
  - (c) remote sensing: along-path terrain profile from the DEM, read
    every 1 m along the matched path (spread and maximum of 5 m pitches,
    relief along the line of travel, side slope; 1 m roughness as in
    STRIDE), then canopy height and EO embeddings (*);
  - control: "hidden climbing", the extra time a fixed curve predicts
    from uneven grade within the segment.
- **Models:**
  - Tobler as published;
  - a refitted slope curve (rounded, asymmetric);
  - additive offsets (ridge on binned features);
  - gradient-boosted trees.
- **Predictive distribution:** prediction + residual quantiles from
  held-out training outings.
- **Splits:** 5 folds of outings, 5 folds of 10 km blocks, leave one region
  out (17 folds).
- **Scores:** CRPS (skill vs the slope curve), 90% interval coverage, and
  moving-time error over 1 km stretches and whole hikes. Two references:
  "place memory" (other hikers at the same 100 m cell) and personal pace
  (the hiker's first km).

## 4. Results (~1.25 pages)

**Table 1** (CRPS skill vs the refitted slope curve; final numbers, 12 Oct,
frozen on T1 v1 by decision #113; lidar vegetation row 21 Oct;
`travel-speed-gate1/results/t3_harness_*`; `docs/NEXT_STEPS.md` §1a):

| Model | New hikers | New 10 km squares | **Unseen region** [95% CI] |
|---|---|---|---|
| Tobler (published) | −12.8 | −12.7 | −12.5 |
| Campbell et al. 2022 (published median) | −0.9 | −0.9 | −0.5 [−1.8, 0.7] |
| STRIDE 2024 (published / refitted) | −17.2 / +0.2 | −17.3 / +0.2 | −16.8 / +0.2 |
| + OSM tags (additive / trees) | +1.3 / +1.5 | +1.1 / +1.5 | +0.9 [0.1, 1.7] / +0.4 |
| + vegetation, 30 m | +0.0 / +0.1 | −0.0 / −0.1 | −0.1 / −0.8 |
| + AlphaEarth embeddings | +1.4 / +2.6 | +1.4 / +1.9 | +1.1 [0.1, 2.6] / +1.1 |
| + lidar vegetation (15 regions with point clouds) | +0.4 / +0.5 | +0.4 / +0.4 | +0.3 [−0.3, 1.1] / +0.2 |
| **+ terrain (1 m + 5 m elevation)** | +2.2 / +3.2 | +2.1 / +2.8 | **+2.1 [1.5, 3.1] / +2.8 [1.8, 4.1]** |
| + terrain + embeddings | +2.9 / +4.3 | +3.0 / +3.6 | +2.6 / +2.8 |
| + terrain + embeddings + tags | +3.7 / +5.1 | +3.8 / +5.1 | +3.0 / +3.9 [2.7, 5.7] |
| terrain-adjusted Tobler formula | +1.0 | +1.0 | +1.0 [0.6, 1.5] |
| + personal pace → + terrain | | | +8.4 → +10.7 / +11.6 |

- **R1. Tobler fails everywhere** (`paper/figures/fig_curve.png` a):
  −12.5% CRPS, R² < 0. Speed peaks near 4.2 km/h on level to gently
  descending trail, not 6. Against the median per 2% bin, Tobler is ~20%
  too fast within ±10% grade (up to 37% near its peak) and ~18% too slow
  on climbs > 25%. Campbell's published median curve (Utah and California)
  matches near level but is ~20% too fast on climbs > 25% (~10% on
  descents < −25%); as good as our refit on average (−0.5% [−1.8, 0.7]),
  but region-dependent: −3.8% in the White Mountains to +5.8% in
  Shenandoah.
- **R1b. Asymmetry, same hiker, same trail** (plan claim 4;
  `fig_curve.png` b): 2,763 out-and-back pairs from 1,145 outings. Down /
  up speed ratio 1.08 at 3–10% grade, 1.17 at 10–20%, 1.22 at 20–30%, 1.23
  above 30%; Tobler implies 1.42 at every grade above 5%. Our pooled curve
  implies nearly the same ratios, so its asymmetry is not a sampling
  artifact; Campbell's implies 1.02–1.16.
- **R2. Tags don't transfer.** They help a little within a region and
  barely in a new one. Not because tag values change meaning (within a
  hike they act the same in every region): tags are missing on much of
  the trail, unevenly by region, and trees on tags lose most in transfer
  (+1.5% → +0.4%), as if fitting region-specific combinations (decision
  #105).
- **R3. Terrain transfers.** It beats tags in 16 of 17 held-out regions
  (the exception: Yosemite), and on tagged segments (+2.2% vs +0.9%). 95%
  intervals resampling whole regions: terrain +1.5 to +3.1% (additive),
  tags +0.1 to +1.7%; terrain minus tags +0.7 to +2.2%, above zero in
  every draw.
  Robustness: it adds ~1.9 points on top of region offsets (not a region
  proxy) and ~2.3 on top of personal pace (not a hiker proxy). It holds
  for newer hikes (trained up to 2019, tested on 2020+: +2.2% / +2.9%;
  tags +0.9% / +0.9%) and at every GPS recording rate (unseen regions,
  traces every ≤ 2 s / 2–10 s / > 10 s: +1.7 / +2.4 / +1.9%). With no
  neighbouring region in training (decision #107): a whole zone held out
  +1.9% / +2.7%, East ↔ West +2.6% / +3.3% (tags +0.7% / −0.1% and +1.5% /
  −0.3%), terrain − tags > 0 in every draw. By slope,
  it is largest on descents and level trail (+2.3 to +2.8%, additive) and
  smallest on steep climbs (+0.8%): footing limits descents, effort limits
  climbs.
  Vegetation from 30 m maps (NLCD canopy, land cover) adds nothing, alone
  or with terrain: the remote-sensing signal is in the elevation data.
  1 m lidar ≈ 5 m for this profile; STRIDE's roughness adds ~nothing on
  trails (published STRIDE −16.8%).
- **R3d. Point-cloud vegetation (White Mountains, decision #111):**
  understory density from the lidar points (STRIDE's 0.85–1.2 m band) is
  7.5% slower in its densest fifth, within the same hike; with terrain it
  lifts skill in new 10 km squares from +3.6% to +5.0% (about +1 point
  beyond terrain and elevation). STRIDE's published density term
  over-penalises trails (−37%). **It does not transfer** (decision #112,
  15 regions with point clouds, 72 GB): in unseen regions vegetation alone
  +0.3% / +0.2% (n.s.), and added to terrain +0.2 [−0.2, 0.5] / +0.0
  points; it helps in 9 of 15 regions (Green Mtns +2.6, Adirondacks +2.0)
  and hurts in others (Front Range −1.4). Even among the 7 eastern forest
  regions: +0.4 [−0.4, 1.5] / −0.1. Like the embeddings, it knows places;
  only terrain transfers.
- **R3c. Foundation-model embeddings** (AlphaEarth) are strong within
  regions (+1.4% / +2.6%) but transfer less reliably (+1.1% / +1.1% in
  unseen regions; −5.6% to +8.3% by region). Physical terrain transfers;
  embeddings know places. Terrain + embeddings: +2.6% / +2.8%. About 60%
  of the terrain gain is uneven grade inside the 50 m segment ("hidden
  climbing"); the rest is difficulty beyond grade.
- **R3b. A terrain-adjusted Tobler function** (T4): v0 and k as linear
  functions of one DEM measure (steppiness). Steppy trails peak at 3.84
  km/h vs 4.60 on smooth ones; +1.0% in unseen regions with 5 numbers,
  but less portable than the full terrain models: +0.6% [0.1, 1.3] with a
  whole zone held out, −0.3% [−1.5, 1.0] East ↔ West (fitted on the East
  it misses the West, −0.8%).
  Fig. candidate: `results/t4_terrain_curve/fig_curves.png`.
- **R4. The hiker dominates.** Personal pace from the first km cuts
  whole-hike moving-time error from 13.6% to 10.0%; terrain on top takes it
  to 9.6% (terrain alone: 13.0%).
- **Fig. 2:** grouped bars, skill by model × split (the explainer's
  scoreboard).
- **Fig. 3 (if space):** per-region skill of terrain vs tags (dot plot,
  17 rows), or speed vs "steppiness" quintile.

## 5. Discussion and conclusion (~0.5 page)

- **Why tags don't transfer** (tested, decision #105,
  `results/t3_tag_transfer/`): within the same hike, tag values act the
  same everywhere (harder sac_scale slower in 10/10 regions, paved faster
  in 10/10). What doesn't carry over is presence: sac_scale is on 1–96% of
  walked trail by region, and an untagged trail is faster than a tagged
  one in some regions, slower in others (−3.5% to +5.1%). In unseen
  regions the additive tag model does about as well on untagged as on
  tagged trail (+0.8% / +0.9%), so missing tags are not where it loses on
  average. Terrain is on every trail, with the same sign in 17/17 regions
  (−12%, steppiest vs smoothest fifth). Candidate figure:
  `fig_tag_vs_terrain.png`.
- **What the terrain captures:** grade variability within the segment
  (rock steps, short pitches) that a single average slope hides. The
  control separates "uneven grade" from "difficulty beyond grade" (*).
- **Limits:**
  - OSM uploaders aren't a random sample of hikers;
  - lab-only regions (*);
  - API depth limit;
  - coarse DEM in Olympic and BC;
  - segment noise (GPS);
  - sparse traces read slow, a measurement effect (decision #104):
    thinning dense walks to 30 s between points lowers measured speed by
    11% (straight lines cut corners; short stops count as moving). The
    curve without traces logged every > 10 s peaks at 4.28 km/h vs 4.17;
    terrain's gain is the same at every recording rate;
  - weather (Daymet, decision #108): hot days (> 25 °C) −3% and snow on
    the ground −4% vs the region's average hike, but weather adds nothing
    in new regions (−0.0% additive, −1.9% trees) and lowers terrain's gain
    when added (+2.1 → +1.9%, trees +2.8 → +1.4%); date and time of day
    likewise (−0.3%, decision #106). The hiker's day-level pace already
    holds it.
- **Release:** the derived segment table without user names, if mentors
  agree.
- **Conclusion:** a 3-sentence restatement plus one line of future work
  (canopy, embeddings, imagery).

---

**Mode (stretch, T4):** bike/ski-to-walk ratio ~4× on descents → ~1.6× on
climbs (constant multipliers fail); runners ~2.5× throughout
(`travel-speed-gate1/results/t4_mode_curves/fig_modes.png`). The plan's
test (decision #103; claim 5): one shared curve times a per-mode
multiplier vs a curve per mode, on held-out outings. Runners: ×2.48 is
enough (own curve +0.1% [−0.5, 0.5]). Bikes/skis: own curve +3.8% [2.9,
4.8]; the ×3.16 multiplier is 15% too slow downhill and 35% too fast
uphill.

## Figures and tables to make (Claude can produce drafts)

**Budget (21 Oct, all sections drafted).** The paper fills exactly 4
pages, references included, with ~5 lines to spare: Table I, Fig. 1 (map),
Fig. 2 (speed vs slope and down/up, claims 2 and 4; 3.1 in tall) and Fig. 3
across both columns (a: skill by model, claim 3; b: each region held out;
2.4 in tall). The hike-time result (R4) and the trail map (Discussion) are
one sentence each; both figures are kept and commented out at the end of
`results.tex`, so one can return if the 2027 kit puts references outside
the 4 pages. If the final text runs long, cut first: the travel-mode
paragraph (R5), the robustness tag numbers, the STRIDE details.

- [x] Fig. 1: `paper/figures/fig_map.png` (17 regions, circle area = walking hours, White Mountains inset).
- [x] Fig. 2 (T4, plan claims 2 and 4): `paper/figures/fig_curve.png`: speed vs slope (medians, middle 50%, our curve, Campbell, Tobler) and the same-hiker down/up ratio.
- [x] Fig. 3 (both columns): `paper/figures/fig_skill_regions.png`: (a) skill by model, new hikers vs unseen region, 95% CIs; (b) terrain vs tags per held-out region, 16 of 17. From `travel-speed-gate1/make_paper_figures.py`, which also writes the panels on their own (`fig_skill.png`, `fig_regions.png`) for slides.
- [x] Table I (`results.tex`), final numbers on T1 v1 (decision #113), with the lidar vegetation row.
- [x] Out for space, one sentence each: `paper/figures/fig_hike_time.png` (R4, whole-hike moving-time error by model, 1,354 hikes in held-out regions) and `travel-speed-gate1/results/t4_trail_map/fig_wm_pace.png` (pace on every White Mountains trail from the function fitted on the other 16 regions, vs Tobler; 77% of the trail km have no traces).
- [x] Not used: `travel-speed-gate1/results/t4_terrain_curve/fig_curves.png` (speed vs slope by steppiness, with Tobler).

## References (checked 12 Oct 2026)

All entries in `refs.bib` were checked against Crossref or arXiv (authors,
venue, volume, pages, DOI). `RELATED_WORK.md` says what each paper did and
how we differ, for the Introduction. New since the skeleton: Huang et al.
2026 (Hong Kong, 16 factors incl. weather, random split), Šerić et al.
2022 (Sentinel-2, one range), Higgins 2021, Goodwin et al. 2025 (sampling
resolution), and the AlphaEarth paper (Brown et al. 2025). Pagneux et al.
2023 is in `refs.bib`, but its findings are paywalled and not yet read.
