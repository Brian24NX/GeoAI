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

**Table 1** (CRPS skill vs the refitted slope curve; numbers from
`results/t3_harness_terrain5m/`):

| Model | Outing folds | Block folds | **Unseen region** |
|---|---|---|---|
| Tobler (published) | −13.8% | −13.7% | −13.2% |
| Campbell et al. 2022 (published median) | −1.1% | | −0.6% |
| STRIDE 2024 (published / form refitted) | −18.0 / +0.3 | | −17.7 / +0.1 |
| + OSM tags (additive / trees) | +1.1 / +1.0 | +0.9 / +0.6 | **+0.2 / −0.9** |
| + DEM terrain (additive / trees) | +2.0 / +2.7 | +2.1 / +2.6 | **+1.6 / +2.2** |
| control: "hidden climbing" only | +1.2 / +1.5 | +1.2 / +1.5 | +1.0 / +1.2 |
| + both | +2.8 / +3.4 | +2.4 / +2.8 | +1.6 / +1.3 |
| + personal pace (then + terrain) | +7.9 (+9.8) | | +8.5 (+10.3) |

- **R1. Tobler fails everywhere:** −13% CRPS, R² < 0. The peak is 4.27
  km/h at −4.5% grade, not 6. Campbell's published median curve (Utah and
  California) is as good as our refit on average (−0.6%, n.s.) but
  region-dependent: −10% in the Adirondacks, +4% on the North Shore.
- **R2. Tags don't transfer.** They help a little within a region and
  barely in a new one. Trees on tags overfit regional tagging habits.
- **R3. Terrain transfers.** It beats tags in 15 of 17 held-out regions,
  and on tagged segments (+1.8% vs +0.5%). 95% intervals resampling whole
  regions: terrain +0.8 to +2.8% (additive), tags −0.5 to +1.0%;
  terrain minus tags +0.7 to +2.4%.
  Robustness: it adds ~1.8 points on top of region offsets (not a region
  proxy) and on top of personal pace (not a hiker proxy).
  Vegetation from 30 m maps (NLCD canopy, land cover) adds nothing, alone
  or with terrain: the remote-sensing signal is in the elevation data.
  1 m lidar ≈ 5 m for this profile; STRIDE's roughness adds ~nothing on
  trails (published STRIDE −18%). Embeddings (*) pending the all-region
  test. About 60% of the gain is
  uneven grade inside the 50 m segment ("hidden climbing"); the rest is
  difficulty beyond grade. (*) 1 m roughness, canopy and embeddings go
  here.
- **R3b. A terrain-adjusted Tobler function** (T4): v0 and k as linear
  functions of one DEM measure (steppiness). Steppy trails peak at 3.82
  km/h vs 4.56 on smooth ones; +0.65% in unseen regions with 5 numbers.
  Fig. candidate: `results/t4_terrain_curve/fig_curves.png`.
- **R4. The hiker dominates.** Personal pace from the first km cuts
  whole-hike moving-time error from 13.7% to 9.9%; terrain on top takes it
  to ~9.5%.
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
  - segment noise (GPS).
- **Release:** the derived segment table without user names, if mentors
  agree.
- **Conclusion:** a 3-sentence restatement plus one line of future work
  (canopy, embeddings, imagery).

---

## Figures and tables to make (Claude can produce drafts)

- [ ] Fig. 1: region map (from the explainer's map) + one region inset.
- [x] Fig. 2 draft: `paper/figures/fig_skill.png` (skill by model, new hikers vs unseen region, 95% CIs), from `travel-speed-gate1/make_paper_figures.py`.
- [ ] Table 1 as above, final numbers.
- [x] Fig. 3 draft: `paper/figures/fig_regions.png` (terrain vs tags per held-out region; 15 of 17).
- [x] Fig. 4 candidate: `paper/figures/fig_hike_time.png` (whole-hike moving-time error by model, 1,199 hikes in held-out regions).
- [x] Fig. 5 candidate: `travel-speed-gate1/results/t4_terrain_curve/fig_curves.png` (speed vs slope by steppiness, with Tobler).

## References to verify before citing (from `docs/NEXT_STEPS.md` §2)

Tobler 1993; Irmischer & Clarke 2018; Campbell et al. 2019, 2022; STRIDE
(Campbell, Cutler & Dennison 2024); Cutler et al. 2026; Wood et al. 2023;
HikingTTE (Asako et al. 2024); Šerić et al. 2022; Pagneux et al. 2023;
RasterNet (Hadzic et al. 2020); Newson & Krumm 2009 (HMM map-matching);
Gneiting & Raftery 2007 (CRPS); OSM (ODbL); USGS 3DEP. Check every author
list, year and venue in the papers themselves. Several entries came from
search snippets.
