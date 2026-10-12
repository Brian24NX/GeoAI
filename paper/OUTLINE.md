# IGARSS 2027 paper: outline (draft 1, 11 Oct 2026)

*An outline for Brian to write from: bullets, a page budget, the figure
plan and the numbers as of 11 Oct. Numbers marked (*) change when the
city regions finish their full downloads and the 1 m / canopy / embedding
covariates are added. AI assistance (Claude) drafted this outline; the paper
text is Brian's. Disclose AI use as the conference and course require.*

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
| 4 Results | 1.25 | Fig. 2 (skill by model and split), Table 1, Fig. 3 (per region or curve) |
| 5 Discussion + conclusion | 0.5 | what transfers and why; limits; release |
| References | 0.25 | ~12 (2026 kit: references outside the 4 pages; check 2027) |

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
  of 1.5M uploads). 17 regions in the US and Canada; 2,533 hiking traces
  (*), 1,744 walking outings, 4,227 walking hours.
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

**Table 1** (CRPS skill vs the refitted slope curve; final numbers, 12 Oct;
`travel-speed-gate1/results/t3_harness_*`; `docs/NEXT_STEPS.md` §1a):

| Model | New hikers | New 10 km squares | **Unseen region** [95% CI] |
|---|---|---|---|
| Tobler (published) | −12.8 | −12.7 | −12.5 |
| Campbell et al. 2022 (published median) | −0.9 | −0.9 | −0.5 [−1.8, 0.7] |
| STRIDE 2024 (published / refitted) | −17.2 / +0.2 | −17.3 / +0.2 | −16.8 / +0.2 |
| + OSM tags (additive / trees) | +1.3 / +1.5 | +1.1 / +1.5 | +0.9 [0.1, 1.7] / +0.4 |
| + vegetation, 30 m | +0.0 / +0.1 | −0.0 / −0.1 | −0.1 / −0.8 |
| + AlphaEarth embeddings | +1.4 / +2.6 | +1.4 / +1.9 | +1.1 [0.1, 2.6] / +1.1 |
| **+ terrain (1 m + 5 m elevation)** | +2.2 / +3.2 | +2.1 / +2.8 | **+2.1 [1.5, 3.1] / +2.8 [1.8, 4.1]** |
| + terrain + embeddings | +2.9 / +4.3 | +3.0 / +3.6 | +2.6 / +2.8 |
| + terrain + embeddings + tags | +3.7 / +5.1 | +3.8 / +5.1 | +3.0 / +3.9 [2.7, 5.7] |
| terrain-adjusted Tobler formula | +1.0 | +1.0 | +1.0 [0.6, 1.5] |
| + personal pace → + terrain | | | +8.4 → +10.7 / +11.6 |

- **R1. Tobler fails everywhere:** −12.5% CRPS, R² < 0. The peak is 4.31
  km/h at −4.5% grade, not 6. Campbell's published median curve (Utah and
  California) is as good as our refit on average (−0.5% [−1.8, 0.7]) but
  region-dependent: −3.8% in the White Mountains to +5.8% in Shenandoah.
- **R2. Tags don't transfer.** They help a little within a region and
  barely in a new one. Trees on tags overfit regional tagging habits.
- **R3. Terrain transfers.** It beats tags in 16 of 17 held-out regions
  (the exception: Yosemite), and on tagged segments (+2.2% vs +0.9%). 95%
  intervals resampling whole regions: terrain +1.5 to +3.1% (additive),
  tags +0.1 to +1.7%; terrain minus tags +0.7 to +2.2%, above zero in
  every draw.
  Robustness: it adds ~1.9 points on top of region offsets (not a region
  proxy) and ~2.3 on top of personal pace (not a hiker proxy). It holds
  for newer hikes (trained up to 2019, tested on 2020+: +2.2% / +2.9%;
  tags +0.9% / +0.9%) and at every GPS recording rate (unseen regions,
  traces every ≤ 2 s / 2–10 s / > 10 s: +1.7 / +2.4 / +1.9%).
  Vegetation from 30 m maps (NLCD canopy, land cover) adds nothing, alone
  or with terrain: the remote-sensing signal is in the elevation data.
  1 m lidar ≈ 5 m for this profile; STRIDE's roughness adds ~nothing on
  trails (published STRIDE −16.8%).
- **R3c. Foundation-model embeddings** (AlphaEarth) are strong within
  regions (+1.4% / +2.6%) but transfer less reliably (+1.1% / +1.1% in
  unseen regions; −5.6% to +8.3% by region). Physical terrain transfers;
  embeddings know places. Terrain + embeddings: +2.6% / +2.8%. About 60%
  of the terrain gain is uneven grade inside the 50 m segment ("hidden
  climbing"); the rest is difficulty beyond grade.
- **R3b. A terrain-adjusted Tobler function** (T4): v0 and k as linear
  functions of one DEM measure (steppiness). Steppy trails peak at 3.84
  km/h vs 4.60 on smooth ones; +1.0% in unseen regions with 5 numbers.
  Fig. candidate: `results/t4_terrain_curve/fig_curves.png`.
- **R4. The hiker dominates.** Personal pace from the first km cuts
  whole-hike moving-time error from 13.6% to 10.0%; terrain on top takes it
  to 9.6% (terrain alone: 13.0%).
- **Fig. 2:** grouped bars, skill by model × split (the explainer's
  scoreboard).
- **Fig. 3 (if space):** per-region skill of terrain vs tags (dot plot,
  17 rows), or speed vs "steppiness" quintile.

## 5. Discussion and conclusion (~0.5 page)

- **Why tags don't transfer:** OSM tagging conventions differ by region
  and mapper community; the same sac_scale value means different things.
  Lidar-derived terrain measures the same physical thing everywhere.
- **What the terrain captures:** grade variability within the segment
  (rock steps, short pitches) that a single average slope hides. The
  control separates "uneven grade" from "difficulty beyond grade" (*).
- **Limits:**
  - OSM uploaders aren't a random sample of hikers;
  - lab-only regions (*);
  - API depth limit;
  - coarse DEM in Olympic and BC;
  - segment noise (GPS);
  - sparse traces (> 10 s between points) read ~10% slow on flat ground,
    probably because short stops hide between points: a per-trace offset
    (personal pace absorbs it);
    terrain's gain is the same at every recording rate.
- **Release:** the derived segment table without user names, if mentors
  agree.
- **Conclusion:** a 3-sentence restatement plus one line of future work
  (canopy, embeddings, imagery).

---

**Mode (stretch, T4):** bike/ski-to-walk ratio ~4× on descents → ~1.6× on
climbs (constant multipliers fail); runners ~2.5× throughout
(`travel-speed-gate1/results/t4_mode_curves/fig_modes.png`).

## Figures and tables to make (Claude can produce drafts)

- [x] Fig. 1: `paper/figures/fig_map.png` (17 regions, circle area = walking hours, White Mountains inset).
- [x] Fig. 2 draft: `paper/figures/fig_skill.png` (skill by model, new hikers vs unseen region, 95% CIs), from `travel-speed-gate1/make_paper_figures.py`.
- [ ] Table 1 as above, final numbers.
- [x] Fig. 3 draft: `paper/figures/fig_regions.png` (terrain vs tags per held-out region; 15 of 17).
- [x] Fig. 4 candidate: `paper/figures/fig_hike_time.png` (whole-hike moving-time error by model, 1,199 hikes in held-out regions).
- [x] Fig. 5 candidate: `travel-speed-gate1/results/t4_terrain_curve/fig_curves.png` (speed vs slope by steppiness, with Tobler).
- [x] Fig. 6 candidate (application, strong for IGARSS): `travel-speed-gate1/results/t4_trail_map/fig_wm_pace.png`. Pace on every White Mountains trail from the function fitted on the other 16 regions, vs Tobler. 77% of the trail km have no traces.

## References to verify before citing (from `docs/NEXT_STEPS.md` §2)

Tobler 1993; Irmischer & Clarke 2018; Campbell et al. 2019, 2022; STRIDE
(Campbell, Cutler & Dennison 2024); Cutler et al. 2026; Wood et al. 2023;
HikingTTE (Asako et al. 2024); Šerić et al. 2022; Pagneux et al. 2023;
RasterNet (Hadzic et al. 2020); Newson & Krumm 2009 (HMM map-matching);
Gneiting & Raftery 2007 (CRPS); OSM (ODbL); USGS 3DEP. Check every author
list, year and venue in the papers themselves. Several entries came from
search snippets.
