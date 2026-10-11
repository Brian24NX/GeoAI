# Next steps: from T1 to the IGARSS 2027 paper

*Written 11 Oct 2026 (Sunday, week 7), after a literature and data-source
survey; **updated the same day (10:00 CDT) with the first evaluation
results** (§1b). Plain-English summary first; details below. Citations with
links are in "What the literature says". Items marked (verify) come from
search snippets and need checking when you read the paper.*

---

## The short version

1. **Where we are:** T1 (the dataset) is done in 17 regions, far more than
   the plan's single region. 5 city regions are being upgraded from lab-only
   to full downloads. The T3 evaluation harness runs on it (§1b).
2. **What we learned from the literature:** our first results replicate
   Campbell et al. (2019, 2022). With Strava and AllTrails data from Utah and
   California, they also found hikers peak around 4.1 km/h (we get 4.25), with
   a rounded, Lorentz-shaped curve. Wood et al. (2023) already combined OSM
   terrain classes with lidar for 7,600 UK hikes. So "Tobler is wrong" alone
   is **not a new paper**.
3. **What nobody has done** (the agent found no prior work on any of these;
   this is our paper):
   - predict hiking speed in a **region the model has never seen**, using
     remote sensing instead of map tags (17 regions make this testable);
   - give **calibrated uncertainty**;
   - measure the **up/down asymmetry on same-hiker pairs** at scale.
4. **First evaluation results (§1b)** sharpen this. Map tags improve
   predictions by only ~1% within a region and ~0.2% in a new region, while
   a hiker's own pace matters ~10× more. So the remote-sensing question is
   about **transfer**: do physical covariates keep their value in new
   regions, where tag effects don't?
5. **The plan:**
   - finish T1 this week;
   - T2 covariates in weeks 9–10, reusing STRIDE's lidar definitions plus
     free foundation-model embeddings;
   - T3 four-arm comparison under leave-one-region-out testing, with
     Campbell, Wood and STRIDE as baselines next to Tobler;
   - full draft by about 27 Nov; submit by about 8 Jan (deadline 11 Jan).

---

## 1. Where we are (11 Oct)

**T1 status (updated 11 Oct, 10:00).** All 17 planned regions are built.
- 12 are built from full downloads plus lab traces: White Mountains,
  Cascades, Front Range, Tahoe, Olympic, Smokies, Adirondacks, Catskills,
  Yosemite, Green Mountains, Shenandoah, Pisgah.
- 5 city regions are built from lab traces only: North Shore, San Gabriels,
  Columbia Gorge, Wasatch, Bay Area. Their full downloads run one at a time.
- Combined, the dataset has 2,533 hiking traces, 1,745 walking outings and
  4,227 walking hours, in one table with one data card
  (`travel-speed-gate1/results/t1_all/DATA_CARD.md`; the data itself stays
  on the cluster).
- Mode calls were checked against the uploaders' own activity labels: 3% of
  "walk" traces are labeled bike or ski (`PROGRESS.md`).

**What the data say so far** (all 17 regions, 260k walking segments, 1,744
walking outings; re-run 11 Oct, `travel-speed-gate1/results/t1_findings/`;
the 12-region numbers were the same within rounding):

| Finding | Number | Compared with |
|---|---|---|
| Peak walking speed | 4.0–4.4 km/h in every region | Tobler 6.0; Campbell 2022 ≈ 4.1 (verify) |
| Curve shape | a rounded top (±11% grade) beats Tobler's sharp tent in cross-validation; Lorentz is close behind | Campbell uses Lorentz |
| Slope sensitivity | ≈ 1.8 overall (tent fit); ≈ 2.5 beyond the rounded top; by region 1.1–2.4 | Tobler 3.5 |
| Down/up speed ratio (same hiker, same trail; 2,413 pairs) | 1.07 (3–10% grade) → 1.24 (> 30%) | Tobler 1.42 at every grade |
| Variance after slope | 26% between outings (hiker, day), 74% within an outing (along the trail), 2.4% between regions | sets the ceiling for terrain models |
| Fatigue | none detectable (−0.2% per hour) | |

**Two cautions already known.**
- Olympic and the North Shore sit mostly on ~10 m elevation, not 1 m lidar.
  Their curves are flatter partly for that reason (decision #73).
- The lab-only regions lack anonymous traces.

---

## 1b. First evaluation results (11 Oct; `t3_harness.py`, decision #82)

Each model predicts a speed *distribution* for every 50 m walking trail
segment (260k segments, 17 regions). It is scored on held-out outings,
held-out 10 km blocks and **held-out regions**. CRPS skill is measured
against our refitted slope-only curve:

| Model | Within a region (outing folds) | Unseen region (leave one out) |
|---|---|---|
| Tobler as published | −13.8% | −13.2% |
| Slope curve (tent, rounded or Lorentz) | 0 (baseline) | 0 (baseline) |
| + OSM tags, additive (Wood-style) | +1.1% | +0.2% |
| + OSM tags, boosted trees | +1.0% | −0.9% |
| Place memory: other hikers in the same 100 m cell (a reference) | +1.3% | n/a |
| Slope curve fitted on the region's own other hikers | n/a | +1.7% |
| **Personal pace** (hiker's first km) | +7.9% | **+8.5%** |
| Personal pace + tags | +9.1% | +9.1% |

In travel time (median error, unseen regions):
- whole hikes: 13.7% (slope curve) → 9.9% (with personal pace);
- 1 km stretches: 17.2% → 13.9%.

90% intervals cover 88% of held-out speeds. Tag effects (fitted on all
data):
- easy trails (sac_scale T1) ~7% faster than untagged, T4 alpine ~4%
  slower;
- worse trail visibility up to ~10% slower;
- trails ≥ 2 m wide ~5% faster.

**What this means:**
- Terrain beyond slope is a small signal next to who is hiking.
- The place-memory row is a reference for place-based information: what
  other hikers' speeds at the same spot tell you. It is limited by how
  many hikers passed each 100 m cell, so it is not a hard ceiling (§1c:
  lidar beat it).
- Tags reach ~75% of it within a region, but only ~20% of their gain
  survives in a new region (tagging conventions differ).
- That transfer gap is the remote-sensing opportunity: lidar roughness,
  canopy and embeddings mean the same thing everywhere. The paper tests
  exactly that, reporting gains next to tags and place memory, not as
  big-sounding raw numbers.
- With personal pace known, tags add more (+0.6–1.2%). Terrain effects
  show more clearly once the hiker is accounted for, so T3 should report
  both.

## 1c. First remote-sensing result: 1 m lidar terrain, White Mountains (11 Oct, decision #83)

**What was measured.** Along each walking segment's matched path, every
1 m, from the 1 m lidar DEM:
- roughness as STRIDE defines it;
- relief along the line of travel;
- the steepest 5 m pitch and the spread of 5 m pitches;
- side slope.

**Raw pattern.** After the slope curve, the smoothest fifth of segments
is ~14% faster and the "steppiest" fifth ~11% slower.

**CRPS skill vs the slope curve:**

| | New hikers (outing folds) | New 10 km squares (block folds) |
|---|---|---|
| OSM tags (additive) | +1.7% | +0.7% |
| Place memory | +1.5% | n/a |
| **1 m lidar terrain (additive)** | **+3.8%** | **+3.1%** |
| Lidar + tags (trees) | +3.9% | +4.2% |

**What it shows (one region so far):**
- Lidar beats tags 2–4×, and keeps most of its value in map squares it
  never saw, where tags keep little.
- It also beats place memory, because it measures every spot, including
  ones few hikers walked.

**All 17 regions, leave one region out (decision #85).** The same profile
from the 5 m elevation T1 already had (in the White Mountains, 5 m ≈ 1 m):

| | New hikers | New 10 km squares | **Unseen region** |
|---|---|---|---|
| OSM tags (additive / trees) | +1.1 / +1.0 | +0.9 / +0.6 | **+0.2 / −0.9** |
| DEM terrain (additive / trees) | +2.0 / +2.7 | +2.1 / +2.6 | **+1.6 / +2.2** |
| "Hidden climbing" alone (control) | +1.2 / +1.5 | +1.2 / +1.5 | +1.0 / +1.2 |
| Personal pace, then + terrain | +7.9 → +9.8 | | +8.5 → +10.3 / +11.0 |

- Terrain beats tags in **15 of 17** held-out regions (the other two tie),
  and on tagged segments (+1.8% vs +0.5%).
- ~60% of the gain is uneven grade inside the segment ("hidden climbing":
  a DEM sees it, an average slope or a tag can't); ~40% is difficulty
  beyond grade.

**Next:**
- The 1 m elevation for all 16 US regions is downloading (decision #84,
  ~12.5 GB, ~9 h). Then `t2_terrain1m.py --all` adds STRIDE roughness.
- Canopy height and embeddings follow.
- Re-run once the city regions are rebuilt.

## 2. What the literature says (and how we differ)

| Work | What they did | How we differ |
|---|---|---|
| Irmischer & Clarke 2018, CaGIS ([doi](https://doi.org/10.1080/15230406.2017.1292150)) | ~200 cadets; speed vs slope and land cover | crowdsourced, 17 regions |
| Campbell et al. 2019, Applied Geography ([doi](https://doi.org/10.1016/j.apgeog.2019.03.008)) | ~30k Strava users near Salt Lake City, lidar slope; Lorentz percentile curves with an asymmetry term | many regions; covariates beyond slope; same-hiker asymmetry |
| Campbell, Dennison & Thompson 2022, CEUS ([pdf](https://www.fs.usda.gov/rm/pubs_journals/2022/rmrs_2022_campbell_m001.pdf)) | ~2,000 AllTrails hikes (UT, CA); 39 percentile Lorentz models; median flat ≈ 4.13 km/h (verify) | covariates; transfer to new regions; calibrated distributions |
| **STRIDE**: Campbell, Cutler & Dennison 2024, Sci Rep ([doi](https://doi.org/10.1038/s41598-024-71359-6), [R](https://github.com/mickeycampbell/stride)) | Lorentz in slope ÷ (1 + d·vegetation density + e·roughness); density = lidar return share at 0.85–1.20 m; roughness = DTM − 2 m smoothed DTM; timed field walks | crowdsourced hikes, held-out regions. **Our lidar baseline** |
| Cutler et al. 2026, GIScience & RS ([doi](https://doi.org/10.1080/15481603.2026.2626632)) | random forest, lidar slope, density, roughness, off-trail; R² 0.78 | on-trail, multi-region, probabilistic |
| **Wood et al. 2023**, PLOS ONE ([doi](https://doi.org/10.1371/journal.pone.0295848)) | 7,636 Hikr + OSM GPS tracks, England and Wales; linear model with walking slope, hill slope, OSM terrain class, lidar obstruction (DSM − DTM) | the closest analog: North America, sac_scale and surface tags vs remote sensing head to head, embeddings, held-out regions (they report none) |
| HikingTTE, Asako et al. 2024, CIT ([doi](https://doi.org/10.2478/cait-2024-0033)) | deep model of whole-hike time (hikr.org), hiker ability from the hike's first part | segment level, remote-sensing covariates |
| Šerić et al. 2022, JOSIS ([link](https://josis.org/index.php/josis/article/view/204)) | latent walking speed from GPS trails, predicted from Sentinel-2, one Croatian range | multi-region, lidar |
| Huang et al. 2026, Applied Geography (verify) | interpretable ML, ~7.9k tracks, 16 factors incl. weather, Hong Kong | |
| Pagneux et al. 2023, Applied Geography ([doi](https://doi.org/10.1016/j.apgeog.2023.103112)) | DEM resolution vs hiking speed functions (findings not checked) | we tested 1 m vs 5 m: no difference on trails |
| RasterNet (Hadzic et al. 2020; our lab) | road free-flow speed from lidar + overhead imagery | the trail analog |

**The gap** (the agent found no work that combines all three):
crowdsourced on-trail speeds; lidar or embedding covariates; testing on
held-out regions.

**What this means for the paper.**
- "Tobler overestimates speed" is a **replication** of Campbell. We report
  it, across 17 regions, as context.
- The headline has to be **Claim 3 of the plan, made stronger by our data:**
  can remote sensing replace map tags *in a region the model has never seen*?

---

## 3. The paper (IGARSS 2027, 4 pages)

**Confirmed:**
- deadline **11 Jan 2027** (also for the Student Paper Competition);
- portal opens **10 Nov 2026**; notification 12 Mar 2027;
- 4 pages, IEEE two-column. The 2026 kit allowed 4 pages *excluding
  references*; the 2027 kit isn't posted yet.
- Student papers needed an advisor attestation in 2026.

**Best-fit themes:** SP.6 "Datasets, Benchmarks, and Evaluation
Methodologies" or SP.5 "Foundation Models and Embeddings for EO"
([topics](https://2027.ieeeigarss.org/topics.php)).

**Working title:** *Do we need a trail map? Predicting hiking speed in
unseen regions from airborne lidar and Earth-observation embeddings.*

**Claims, in priority order:**
1. **(Lead) Transfer.** Leave one region out across 17 regions:
   - tag effects barely transfer (+1.1% → +0.2%);
   - terrain from elevation data does (+2.0% → +1.6%; trees +2.2%), and
     beats tags in 15 of 17 regions (§1c).
   Report it with calibrated uncertainty (CRPS, PIT), with and without
   personal pace, and with the hidden-climbing control.
2. **Dataset.** N traversals from ~1,600+ walking outings in 17 regions:
   - how it was built;
   - what share of OSM traces is usable;
   - what's wrong with it (selection bias, OSM API depth limit, DEM quality).
3. **Shape.** Tobler fails everywhere; a rounded (Lorentz-like) top fits
   better. This replicates Campbell, now across regions, and the curve
   parameters vary by region with terrain roughness (from T2).
4. **Asymmetry.** On 2,400+ same-hiker pairs, the downhill advantage grows
   from 7% to 24% with grade, never Tobler's constant 42%.
5. **(Stretch) Mode.** Bikes vs walkers: ~300 bike/ski traces, mostly in the
   Front Range, Tahoe and the Cascades.

**Figures (4 pages fit two or three):**
- (a) the four-arm comparison under leave-one-region-out (the lead);
- (b) multi-region slope-speed curves vs Tobler and Campbell;
- (c) asymmetry by grade, if space allows.

---

## 4. T2: remote-sensing covariates (weeks 9–10, after Danni's OK)

Every covariate is computed per 50 m segment, **along its actual path**
(`geometry_wkt`, added 9 Oct). Prioritized by value ÷ cost:

**Tier 1: all regions, cheap.**

| Covariate | Source | Notes |
|---|---|---|
| 1 m slope, max slope, **roughness = DTM − 2 m smoothed DTM** (STRIDE definition), terrain ruggedness | USGS 3DEP 1 m (pipeline exists: `t2_prefetch_dem1m.py`); BC: NRCan HRDEM ([AWS](https://registry.opendata.aws/canelevation-dem/)) | needs the per-region UTM zone (`regions.utm_epsg`) |
| Canopy height (mean / max in a 10 m buffer) | Meta/WRI 1 m CHM v1, `s3://dataforgood-fb-data/forests/v1/...` (no account; [AWS](https://registry.opendata.aws/dataforgood-fb-forests/)); CHMv2 (2026) also available | the same product in the US and Canada |
| Canopy cover, land cover | NLCD 2021 (30 m, MRLC; we already use it) | US only |
| **AlphaEarth embeddings** (64-d, 10 m, matched to the hike year) | free mirror `source.coop/tge-labs/aef` ([link](https://source.coop/tge-labs/aef)) or Earth Engine `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` (CC-BY) | a frozen pretrained encoder, exactly what plan §9 recommends at our sample size |

**Tier 2: more work.**

| Covariate | Source | Notes |
|---|---|---|
| **Vegetation density at 0.85–1.20 m** (STRIDE's definition) | 3DEP point clouds via PDAL (`readers.ept → filters.smrf → filters.hag_nn`) on the cluster; shortcut: Planetary Computer `3dep-lidar-hag` 2 m rasters (2012–2022) | the understory term (Campbell 2018) |
| **Snow on the hike date** | MODIS MOD10A1 (500 m, daily), SNODAS (1 km, lower 48), Daymet SWE (covers Canada) | a remote-sensing variable that maps can't have. Tests "winter hikes aren't slower" properly |
| TESSERA embeddings (128-d) | `geotessera` point lookup | a second embedding, as a robustness check |

**Tier 3: stretch / follow-on.** NAIP patch embeddings (Clay), or a frozen
image encoder in the RasterNet style. Better suited to EARTHVISION or the
journal version.

**Rule for the held-out-region test:** never use location encoders
(SatCLIP, GeoCLIP) or raw coordinates as features. They tell the model
which region it's in.

---

## 5. T3: models and evaluation (weeks 11–12; Gate 2 ≈ 13 Nov)

**Arms.** Each predicts the speed distribution of a segment.

| Arm | Sees |
|---|---|
| Tobler | slope, published 1993 constants |
| Slope-only (refit) | slope, our rounded-top curve fitted on training regions |
| Campbell | slope, published median Lorentz (and refit) |
| Wood-style | slope + OSM terrain class + lidar obstruction (linear) |
| STRIDE | slope + lidar density + roughness, published form |
| **Tags** | slope + OSM tags (sac_scale, surface, visibility, highway type, with missing-value indicators) |
| **Remote sensing** | slope + T2 covariates (+ embeddings), **no tags** |
| **Both** | everything |

**Models.**
- Gradient-boosted trees on log speed, a serious baseline (plan §9), with a
  monotone constraint in uphill grade.
- The plan's structured model: v0(x)·exp(−k(x)·smooth|s + s0(x)|), whose
  parameters can be read as covariate effects ("k ≈ 2.4 on rough trails,
  1.7 on smooth").
- Distributional output: quantiles or a heavy-tailed log-space likelihood.

**Splits.** Never split by segment (plan §10):
- (a) 5-fold by outing, within each region;
- (b) 10 km blocks (`block_10km`);
- (c) **leave one region out** (17 folds), the headline.

**Metrics.**
- Segment MAE and RMSE (log and km/h).
- Whole-hike moving-time error, which is what users care about.
- **CRPS** (`scoringrules`) and pinball loss at Campbell's percentiles.
- **PIT histograms** for calibration.
- Report on all segments **and** on the tagged subset, where the Tags arm is
  at its best.

---

## 6. What to do **now**, while the downloads finish

| # | Task | Who | Status |
|---|---|---|---|
| 1 | GitHub repo + daily progress log | Claude | ✅ |
| 2 | First multi-region findings (shape, variance, fatigue, asymmetry) | Claude | ✅ |
| 3 | **T1 close-out:** combined all-region dataset + one data card; elevation-quality check for every region; mode calls checked against the uploaders' own activity labels | Claude | ✅ 11 Oct (re-run as the city regions upgrade) |
| 4 | **Evaluation harness on T1 data**: Tobler / slope-only / Lorentz / Tags arms (+ place memory, personal pace); outing, block and leave-one-region-out splits; CRPS, coverage, stretch and hike time errors | Claude | ✅ 11 Oct (§1b). Next: Campbell's published constants, once read |
| 5 | **Paper skeleton**: storyline, figure slots, related-work list, 4-page budget | Claude drafts, Brian writes | outline ✅ 11 Oct (`paper/OUTLINE.md`); LaTeX once the 2027 kit is out |
| 6 | T2 pilot on the White Mountains: 1 m lidar terrain | Claude | ✅ 11 Oct (§1c). Scaling: 1 m elevation for all US regions downloading (#84); Meta canopy and AlphaEarth next |
| 7 | Stop-rule hand check: 20 cards in `stop_check/stop_check.html`, ~15 min | **Brian** | open |
| 8 | Read: Campbell 2019 & 2022, **Wood 2023**, **STRIDE 2024**, HikingTTE, RasterNet | **Brian** | open |

## 7. Timeline to 11 Jan 2027

| Week | Dates | Goal |
|---|---|---|
| 8 | 12–16 Oct | T1 closed (17 regions); evaluation harness; paper skeleton. **16 Oct meeting:** results + this plan |
| 9–10 | 19–30 Oct | T2 tier 1 for all regions; tier 2 started (vegetation density, snow) |
| 11–12 | 2–13 Nov | T3 four arms, all splits. **Gate 2 (~13 Nov):** does remote sensing approach tags? Portal opens 10 Nov |
| 13–14 | 16–27 Nov | **Full draft** (plan: week 13). Thanksgiving 26 Nov |
| 15–16 | 30 Nov–18 Dec | Mentor + Prof. Jacobs review, polish; final exams |
| — | 21 Dec–8 Jan | Buffer; **submit by ~8 Jan** with the Student Paper Competition attestation |

## 8. Risks and how we handle them

| Risk | Handling |
|---|---|
| Novelty overlap with Campbell / Wood | Lead with transfer + remote sensing vs tags + calibration; cite and beat their models as baselines |
| Lab-only regions lack anonymous traces | Full downloads are running; report data source per region; region weighting |
| Coarse DEM regions (Olympic, North Shore) | NRCan HRDEM for BC; flag or drop Olympic in lidar arms |
| Effective sample ≈ 2,000 outings | Trees + structured models, frozen embeddings, no big networks (plan §9) |
| Selection bias (OSM uploaders are enthusiasts) | State it plainly (plan §8) |
| Data release (OSM usernames, licenses) | Release derived segment tables without usernames, if Danni agrees |

## 9. Questions for Danni and Tianyi (16 Oct)

1. T1 is done once the last regions land. **OK to start T2** next week?
2. **Paper framing:** lead with leave-one-region-out "remote sensing vs map
   tags", with Campbell / Wood / STRIDE as baselines next to Tobler. Agree?
3. **Earth Engine / Google Cloud project** for AlphaEarth, or use the free
   mirror? Any lab-preferred embedding model?
4. **Slurm account:** stay on `engr-class-any` (≤ 8 CPUs/job) or the lab's?
5. **Data release:** can we publish a derived dataset (no usernames) with the
   paper?
