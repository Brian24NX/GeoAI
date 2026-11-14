# Implementation details: inventory for the Methods section

*Compiled 13 Nov 2026 from the code and repo docs, read-only. Paths are
relative to `/Users/brian/Desktop/GeoAI/`; `tsg/` = `travel-speed-gate1/`.
Every fact cites `file:line`. When a doc and the code disagree, the code
wins and the disagreement is noted. Counts are T1 v1 (17 regions), the data
behind the current Table I. The v1.1 rerun (16 regions, #136) is still in
progress, so the counts will change.*

---

## 1. "MLP or encoder–decoder?" The plain answer

**Neither architecture describes the paper's models.** Nearly every model is
a classical statistical model: fixed published curves, parametric curves fitted
by robust nonlinear least squares, ridge regression on one-hot bins, and
scikit-learn gradient-boosted trees (`tsg/t3_harness.py:236-297`). **We train
one neural network, the "learned Tobler" row of Table I.** It is a small MLP
(inputs → 32 → 32 → 5, SiLU) that maps a segment's 12 terrain covariates to
that segment's own constants of the fixed slope-curve formula, plus a log-σ
spread. The curve, not the network, turns slope into speed. It is a
hypernetwork-style MLP with about 1.9k weights, trained with Adam
(`tsg/exercises/week10_learned_tobler/learned_tobler.py:97-181`). Nothing is an
encoder–decoder. The pretrained encoders are used only as **frozen feature
extractors**, and none is fine-tuned or given a trained head:

- AlphaEarth: precomputed 64-d embeddings read from a public mirror (`tsg/t2_embed.py:3-17`).
- Clay v1.5: precomputed 1,024-d NAIP embeddings, downloaded (`tsg/t3_naip_clay_download.py:3-12`).
- Satlas Aerial Swin-B: run in `torch.inference_mode()` on the CPU, with no training (`tsg/t3_naip_satlas.py:113-132`).

Their outputs go into the trees or the learned Tobler, after a per-fold PCA to
16 dimensions for the imagery (`tsg/exercises/week12_imagery/track_a_trees.py:50,69-76`). The
only other `torch` code is the loss and CRPS helpers (`tsg/t3_scoring.py:80-90`).
A search of `tsg/` for `torch|nn.Module|MLPRegressor|keras` finds nothing else.

---

## 2. Data pipeline (T1)

| Step | Rule / value | Source |
|---|---|---|
| Trace sources | OSM trackpoints API (5,000 pts/page, boxes ≤ 0.25°); original GPX of identifiable uploads; lab crawl of 2016–22 original files | `tsg/gate1_audit.py:79,85-86`; `tsg/t1_build_dataset.py:5-16` |
| Dropped uploads | car loggers {sunnypilot, dragonpilot, openpilot, frogpilot}; near-duplicates (≥ 50% of the shorter trace's points share second + ~10 m) | `tsg/t1_build_dataset.py:85,97,369-395` |
| Anonymous pieces | stitched across tile edges if ≤ 10 min and ≤ 1 km apart | `tsg/t1_build_dataset.py:71-72` |
| Cleaning | sort by time, keep first point per timestamp | `tsg/gate1_audit.py:521-536` |
| Run splitting | cut at a step > 300 s **or** > 60 km/h; runs need ≥ 3 points | `tsg/gate1_audit.py:92,94`; `tsg/t1_build_dataset.py:515-528` |
| Thinning | keep points ≥ 5 s apart (before matching) | `tsg/t1_build_dataset.py:69,641` |
| Stop rule (default `window60_10`) | a step is stopped if the point ≥ 60 s later is < 10 m away; stopped steps add 0 distance and 0 moving time | `tsg/t1_build_dataset.py:75-81,561-579,587-590` |
| Map matching | HMM, `leuvenmapmatching` DistanceMatcher: obs_noise 15 m, obs_noise_ne 30 m, dist_noise 15 m, max_dist 60 m, max_dist_init 60 m, non-emitting states, lattice width 8, only_edges; restarts after breaks | `tsg/t1_build_dataset.py:88-90,531-558` |
| Network | OSM ways of class trail / track / road, both directions | `tsg/t1_build_dataset.py:86,434-459`; classes `tsg/gate1_audit.py:112-117,709-731` |
| Segments | matched path cut into fixed **50 m** pieces (25 m also built), distance = haversine between matched points | `tsg/t1_build_dataset.py:68,582-632` |
| Speed | `speed_kmh = 3.6 · length / moving_s` | `tsg/t1_build_dataset.py:698` |
| Slope | (z_end − z_start)/length, bilinear sampling of the 5 m USGS 3DEP grid (ImageServer `exportImage`, 5 m pixels, bilinear resample, EPSG:4326), + = uphill, sign unit test | `tsg/t1_build_dataset.py:495-507,724-748`; `tsg/first_look_slope.py:40-43,83-87,138-149` |
| Suspect flag (dropped from analysis) | speed > 30 km/h, \|slope\| > 0.8, or match error > 40 m | `tsg/t1_build_dataset.py:83-84,509-510` |
| Date flag | year < 2005 = clock bug (kept, flagged) | `tsg/t1_build_dataset.py:96,719` |
| Hiking trace | ≥ 5 moving min on trail segments | `tsg/gate1_audit.py:98`; `tsg/t1_build_dataset.py:804-805` |
| Outing | traces starting ≤ 15 min and ≤ 1 km apart (union-find) | `tsg/t1_build_dataset.py:99,398-420` |
| 10 km block | 10 km UTM (NAD83) cell of the segment midpoint | `tsg/t1_finalize.py:32,60-69`; `tsg/regions.py:117-120` |
| Recording interval | median Δt of the raw run (`native_interval_s`) | `tsg/t1_build_dataset.py:645` |

**Travel mode** (`tsg/t1_modes.py`). Each trace's features come from its
non-suspect trail segments: median speed, 90th-percentile speed, the
down/up speed ratio at 6–20% grade, and the share of foot-only segments
(`:42-69`). Traces with ≥ 90% foot-only segments and ≥ 10 segments are the
walking anchors. A robust normal (median, 1.4826·MAD) is fitted to the anchors'
ln(median speed) (`:45,72-77,100-102`). A trace is **walk** if its
`walk_z ≤ 3` (`:46,110`). It is **bike/ski** if its (down/up ≥ 1.7 and
downhill median ≥ 6 km/h) or its p90 ≥ 20 km/h (`:47-49,107-109`). The
confidence is Φ(3 − walk_z) (`:116-117`).

**Walking analysis set** = hiking trace ∧ trail ∧ ¬suspect ∧ slope known ∧
mode = walk (`tsg/t1_variants.py:52-60`; `tsg/t1_combine.py:92-93,122-125`).
The harness also requires speed > 0 and |slope| ≤ 0.6, with target
**y = ln(speed km/h)** (`tsg/t3_harness.py:587-589`). That leaves 289,679
segments in v1 (`tsg/results/t3_harness/summary.json`). Regions:
`tsg/regions.py:21-85`, with the Bay Area in `DROPPED` (`:86`).

---

## 3. Covariates (T2)

All terrain measures use the segment's **matched-path polyline**, projected to
NAD83/UTM and resampled every **1 m** (`tsg/t2_terrain1m.py:104-116`). A segment
needs a path ≥ 5 m long and DEM values at ≥ 90% of its points, and gaps are
filled by linear interpolation (`:113,163-165`; 5 m version `tsg/t2_terrain5m.py:119-120`).

| Covariate | Definition | Source |
|---|---|---|
| `pitch_max` | max \|z(i+5) − z(i)\|/5 over overlapping 5 m pitches | `tsg/t2_terrain1m.py:126-127` |
| `pitch_sd` ("steppiness") | SD of the same 5 m pitches | `:128` |
| `relief_sd` | SD of z minus its 11 m (11-point) centred moving average | `:129-130` |
| `hidden_grade` | mean over the ten non-overlapping 5 m pieces of Tobler pace, ÷ Tobler pace at the segment's mean grade, − 1 (fixed Tobler, nothing fitted) | `:119-120,131-138` |
| `cross_slope` | mean \|∇z_smoothed · unit normal to path\|; Gaussian σ = 2 m (1 m DEM) or σ = 2 px ≈ 10 m (5 m DEM) | `:78-80,170-176`; `tsg/t2_terrain5m.py:68-71,124-130` |
| `rough_mad` (1 m only) | mean \|z − Gaussian(σ = 2 m)\| on the path | `tsg/t2_terrain1m.py:50,166-167` |
| `rough_stride` (1 m only) | STRIDE's roughness: mean \|z − 2 m-radius disk mean (13 px)\| | `:53-55,168-169` |

- **DEMs.** The 5 m grid is the same one used for slope, sampled bilinearly
  (`tsg/t2_terrain5m.py:77-89`), and gives the `_5m` suffixes. The 1 m grid is
  USGS 3DEP 1 m in 500 m UTM cells, also through the ImageServer with bilinear
  resampling (`tsg/t2_dem1m.py:9-11,40-42,92-94`). The North Shore (Canada) is
  skipped (`:45`). The docstring says HRDEM is used there (`:14-15`), but **no
  code does this**, so the 1 m covariates are missing on 5.1% of the rows
  (computed from `tsg/cache/exercise/t3_table.parquet`). Where 3DEP lacks
  1 m data, the service mosaics coarser sources (`tsg/t2_dem1m.py:15-17`).
  "Terrain" in Table I = 5 m (5 columns) + 1 m (7 columns) = **12 covariates**
  (`tsg/cluster/refresh_harness.sh:29`; `tsg/t3_harness.py:254-255,687-691`).
  `slope_1m` and `dem1m_cover` are excluded.
- **Land cover / canopy.** NLCD 2021 Tree Canopy Cover and NLCD 2021 Land
  Cover at 30 m via MRLC WCS (`tsg/t2_landcover.py:6-7,36-38`). They are read
  every 10 m along the path with nearest pixel (`:43,82-102`) and give
  `tcc_mean`, `tcc_max`, and the shares of forest, shrub, open, developed and
  wet (`:45-47,115-128`). US only.
- **AlphaEarth.** 64-d annual embeddings for **2022** at 10 m, from the
  Source Cooperative mirror, int8 dequantized as (q/127.5)²·sign(q). One
  pixel (nearest) is read at the segment midpoint, taken as the mean of the
  endpoints, with no aggregation along the segment (`tsg/t2_embed.py:7-16,51-58,89-94,110`).
  They are precomputed by Google, so no model is run by us.
- **Lidar vegetation** (15 regions). It comes from USGS 3DEP point clouds (EPT
  on AWS) within **3 m** of the path (`tsg/t2_lidarveg.py:10-22,67`). Height
  above ground is IDW from the 6 nearest ground returns within 2 m (`:29-32,70`).
  `nrd` = returns at 0.85–1.20 m ÷ returns ≤ 1.20 m. Also `nrd_center` (≤ 1 m
  from the centreline), `cover2m` (share of first returns > 2 m) and `hag_p95`
  (`:196-229`). `n_pts` is excluded from the models (`tsg/t3_harness.py:254`).
- **Tags** (the "tags" arms). sac_scale, trail_visibility and smoothness are
  ordinal codes; mtb_scale and width are numeric (width capped at 10 m);
  surface, highway and permission are categorical. Values with < 200
  segments are pooled into "other" (`tsg/t3_harness.py:143-185`).
- **Imagery (not in Table I, one sentence).** Track A uses Clay v1.5 1,024-d
  embeddings of the ~155 m NAIP chip nearest the midpoint
  (`tsg/t3_naip_clay_join.py:2-16`). Track B uses midpoints snapped to a 25 m
  grid and the newest NAIP photo from 2019 on (`tsg/t3_naip_spots.py:6-8,32-33`).
  Each chip is 96 m × 96 m at 160 × 160 px RGB, divided by 255, and run
  through the frozen Satlas `Aerial_SwinB_SI` backbone. The embedding is the
  mean of the last feature map (1,024 × 5 × 5 → 1,024), batch 32
  (`tsg/t3_naip_satlas.py:43,99-132`). Both tracks then take a per-fold PCA
  to 16, fitted on ≤ 60,000 training rows (seed 0) (`tsg/exercises/week12_imagery/track_a_trees.py:50,69-76`).

---

## 4. Models

Every arm is fitted per outer fold on training outings only. **fit** = 70%
of the training outings and **stop** = 15%. **cal** = the last 15%, used only for
the spread (§5).

| Arm (Table I name) | Form / features | Fitting | Hyper-params, how chosen | Source |
|---|---|---|---|---|
| Tobler (published) | ln v = ln 6 − 3.5\|s + 0.05\| | none | — | `tsg/t3_harness.py:260-261` |
| Campbell 2022 | Lorentz in degrees, 50th-pct constants a −1.4579, b 22.0787, c 76.3271, d 0.0525, e −3.2002e-4 | none | — | `:264-272` |
| STRIDE (published / refit) | Lorentz(slope)/(1 + d·dns + e·rgh); a,b,c,e = −2.320, 26.315, 147.362, 16.505; d = 15.265, dns = 0 unless lidar | refit: `scipy.optimize.least_squares`, soft_l1, f_scale 0.3, bounds [−15,5,1,0]–[15,80,2000,200] | — | `:276-290,343-359` |
| Slope curve (**reference**) | ln v = a − k±(√((s+s0)² + e²) − e), k₊ if s+s0 ≥ 0 else k₋ (5 params) | `least_squares` soft_l1, f_scale 0.3 on fit ∪ stop; x0 = [1.45, 2.5, 2.5, 0.05, 0.05] | — | `tsg/t1_findings.py:90-94,106,111-115`; `tsg/t3_harness.py:316-318` |
| tobler_refit / lorentz_refit | a − k\|s+s0\| / a − log1p(((s+s0)/w)²) | same solver | — | `tsg/t1_findings.py:73-75,97-99,103,107` |
| Eq. (1), terrain-adjusted Tobler | ln v = a0 + a1 z − (k0 + k1 z)\|s + s0\|, z = pitch_sd_5m/0.10 (missing z → median) | `least_squares` soft_l1, f_scale 0.3, x0 [1.45, −0.1, 1.8, 0.2, 0.05], per fold | — | `tsg/t3_harness.py:280-281,360-366,718-721` |
| Additive ("a" in a / b) | slope curve + ridge on the curve's residuals; one-hot of tag values + "missing"; continuous covariates → **decile** bins + "missing"; width in 4 bins | closed-form ridge, unpenalised intercept, refit on fit ∪ stop | λ·n with λ ∈ {1e-4, 1e-3, 1e-2, 1e-1, 1}, picked by MSE on stop (median chosen 0.01) | `:188-226,257,319-332`; `tsg/results/t3_harness_terrain15m/summary.json` |
| Trees ("b") | `HistGradientBoostingRegressor` on slope + raw features (NaN kept; tags as pandas categoricals) | lr 0.05, max_iter 1000, max_leaf_nodes 31, min_samples_leaf 200, l2 1.0, early stopping on the **stop** outings (`X_val`), n_iter_no_change 30, random_state 0; other settings scikit-learn defaults | fixed, not tuned | `:293-297,367-375` |
| Place memory (reference) | slope curve + shrunk mean residual of other hikers per 100 m UTM cell, outing-demeaned | — | κ ∈ {2, 5, 10, 20, 50, 100} by MSE on stop | `:122-123,333-342,389-400` |
| Personal pace (reference) | + a + β·(median residual of the trace's first 20 segments = 1 km); traces ≥ 40 segments | `np.polyfit` on cal outings (needs ≥ 1,000 rows) | median β = 0.61 | `:121,451-478,614-626` |

**Learned Tobler (the only neural network)**
(`tsg/exercises/week10_learned_tobler/learned_tobler.py`, run by `run_all.py`)

| Item | Value | Source |
|---|---|---|
| Output formula | slope-curve form with per-segment a(x), k₊(x), k₋(x), s0(x); e fixed at the fold's reference fit | `learned_tobler.py:97-133` |
| Network | MLP: Linear(n_in, 32) → SiLU → Linear(32, 32) → SiLU → Linear(32, 5); outputs a, k₊ and k₋ (via softplus), s0, log σ | `:105-125` |
| Inputs | the 12 terrain covariates, clipped to the training rows' 0.1–99.9th percentiles and z-scored with training mean/SD; missing → 0 + one 0/1 flag per covariate with gaps (n_in = 19 when the 7 1 m columns have gaps → **1,861 weights**, counted from the local table). Slope enters only through the curve; σ depends on x only | `:77-93`; `run_all.py:91` |
| Initialisation | PyTorch default for the hidden layers; last layer weights = 0 and biases = the reference constants (softplus⁻¹ for k), log σ = log SD of the cal residuals, so the untrained model = the reference curve | `:110-120,212-214` |
| Loss | mean Student-t NLL, ν = 5 (fixed) | `:137-147`; `tsg/t3_scoring.py:88-90` |
| Optimiser | Adam, lr 1e-3, other settings PyTorch defaults (no weight decay); mini-batches of 2,048 shuffled **fit** rows | `:151-169` |
| Early stopping | after each epoch, stop-row loss; keep best weights; patience 5, min Δ 1e-5, max 60 epochs | `:151-181` |
| Seeds | `torch.manual_seed(seed)` before building and before training; seeds 0, 1, 2; per-row CRPS averaged over seeds | `run_all.py:55-63,121`; `gate2_summary.py:46-47` |
| Scored two ways | (a) the harness's way: μ + cal-residual quantiles (Table I number); (b) its own Student-t(μ, σ(x), ν = 5), closed-form CRPS (number in brackets) | `run_all.py:64-73`; `tsg/t3_scoring.py:56-62` |
| Data / folds | the harness's exact folds and fit/stop/cal outings, exported to `tsg/cache/exercise/` | `tsg/t3_export_table.py:1-24`; `learned_tobler.py:46-64` |
| Runtime | ~6 min for 5 splits × 3 seeds on the laptop CPU | `tsg/exercises/week10_learned_tobler/README.md:96-99`; `DECISIONS_LOG.md:177` |

The design doc proposed σ(x, s) and possibly a learned e
(`tsg/docs/T3_learned_tobler_design.md:33-38`). The code learns σ(x) only and
keeps e fixed.

---

## 5. Predictive distribution, splits, scoring

- **Inner split.** The training **outings** are shuffled and split
  14/20 : 3/20 : 3/20 = 70/15/15 into fit / stop / cal (`tsg/t3_harness.py:569-574`).
- **Predictive distribution.** Point prediction + the 100 quantiles of the cal
  residuals at levels (j − 0.5)/100 (`:119,376`). For the **published** curves
  (Tobler, Campbell, STRIDE published), the residual quantiles are
  re-centred to median 0, so the curve keeps its own level (`:377-380`).
- **Outer splits** (never by segment, `:50-65,550-566`):

| Split (paper name) | Unit | Folds |
|---|---|---|
| outing5 (new hikes) | outing | 5 |
| hiker5 (new hikers) | uploader (anonymous trace = own uploader) | 5 |
| block5 (new 10 km squares) | 10 km UTM block | 5 |
| loro (unseen region, headline) | region | 17 in v1 → 16 in v1.1 |
| loro_hiker | region, and every training outing by an uploader seen in it is dropped | 17 / 16 (`:767-769`) |
| time | train ≤ 2019, test > 2019; suspect dates excluded | 1 (`:125,558-562`) |
| macro / eastwest | 5 zones / East vs West | 5 / 2 (`:126-133,553-557`) |

  The fold assignment is a random permutation of the units, then i mod 5, with
  `default_rng(0)` (`:118,565-566,708`).
- **CRPS.** For the M = 100 samples z_j = pred + r_j:
  CRPS = (1/M)Σ|z_j − y| − (1/M²)Σ_j (2j − M − 1) r_(j), which equals
  ½E|Z − Z′| for sorted r (`:482-498`; `tsg/t3_scoring.py:36-47`). It is in
  ln km/h, and a km/h version also exists (`:499-502`).
- **Skill.** 100·(1 − ΣCRPS_arm / ΣCRPS_slope-curve) over all test segments of
  a split (`:850-853`; `tsg/t3_scoring.py:76-77`).
- **Bootstrap CIs.** B = 2,000 draws with replacement of whole units: outings
  (outing5, block5, time), uploaders (hiker5) or regions (region splits). The
  per-unit CRPS sums are resampled, and the 2.5/97.5 percentiles give the
  interval. Paired differences (e.g. RS − tags) use the same draws; seed 0
  (`:947-983`). The learned Tobler uses the same scheme (`gate2_summary.py:30-32,48-65,72`).
- **Other metrics.** RMSE, MAE, bias and R² of ln v; coverage of the central
  50/90% (from the r quantiles) (`:505-509,513-524`); PIT (`:503,881-888`).
  Moving-time error per 1 km stretch (20 segments) and per whole hike
  (≥ 2 km) uses predicted time = 3.6·L·e^(−pred)·mean(e^(−r)) (`:120-121,526-545`).

---

## 6. Software and compute

| Item | Value | Source |
|---|---|---|
| Cluster env | Python 3.12; numpy 2.5.3, pandas 3.0.6, scipy 1.18.1, scikit-learn 1.9.1, pyproj 3.8.0, leuvenmapmatching 1.1.4, rasterio 1.5.2, laspy 2.7.0, pyarrow 25.0.1 (pinned) | `tsg/requirements-pipeline.txt:1-18`; `tsg/cluster/make_env.sh:2-3,21-24` |
| Laptop (learned Tobler) | Python 3.12.12, torch 2.14.1, scikit-learn 1.9.1 (as on the cluster) | `tsg/requirements.txt:9-10`; `.venv/pyvenv.cfg` |
| Satlas embedding | cluster torch 2.15.0+cpu, torchvision 0.29.2+cpu, satlaspretrain-models (version **not found in repo**) | `DECISIONS_LOG.md:182` |
| `environment.yml` | Python 3.11 + lightgbm: **stale**, not the env used | `tsg/environment.yml:15,34` |
| Hardware | WashU ENGR Slurm (`engr-class-any`, `linuxlab-project`), ≤ 8 CPUs/job, **CPU only, no GPU**; CPU model not found in repo | `tsg/PIPELINE.md:51-53`; `tsg/cluster/*.sh` `#SBATCH` lines |
| Region build | 8 CPUs, 32 GB, 13–26 min/region | `tsg/cluster/rebuild_job.sh:5-6`; `tsg/PIPELINE.md:93` |
| Harness run | 8 CPUs, 48 GB; 4–19 min per run (e.g. terrain 13.2 min) | `tsg/PIPELINE.md:138`; `tsg/results/t3_harness*/summary.json` (`minutes`) |
| Satlas | 16-task array, 8 CPUs, 16 GB each; 6.6 chips/s; longest region 75 min | `tsg/cluster/t3_naip_satlas_job.sh:5-8`; `DECISIONS_LOG.md:182-183` |
| Laptop CPU model | not found in repo | — |

---

## 7. Suggested to mention in the paper (~0.3–0.4 page)

1. There is no deep end-to-end model. The arms are parametric curves (robust
   least squares, soft-L1 loss, scale 0.3), ridge on one-hot / decile-binned
   features, and gradient-boosted trees.
2. The learned Tobler is a 2-hidden-layer MLP (32 units, SiLU, ~1.9k weights).
   It maps 12 terrain covariates to per-segment curve constants (a, k₊, k₋,
   s0) and log σ. It is initialised to the reference curve and trained with
   Adam (lr 10⁻³, batch 2,048), a Student-t NLL (ν = 5), and early stopping
   (patience 5). Inputs are clipped to the 0.1–99.9th percentiles and
   standardised; 3 seeds are averaged.
3. Pretrained encoders (AlphaEarth, Clay, Satlas Swin-B) are frozen feature
   extractors, not fine-tuned. Imagery is reduced by a per-fold PCA to 16.
4. Trees: HistGradientBoosting, learning rate 0.05, ≤ 1,000 iterations, 31
   leaves, ≥ 200 samples/leaf, L2 1.0, early stopping (30 rounds) on held-out
   training outings.
5. Additive model: ridge penalty from {10⁻⁴…1}·n, chosen on held-out training
   outings.
6. Training outings are split 70/15/15 (fit / early stopping / calibration).
   The predictive distribution = point + 100 calibration-residual quantiles.
7. Target = ln moving speed of 50 m map-matched segments. Slope = endpoint
   elevations from the 5 m 3DEP grid.
8. Map matching: HMM (leuvenmapmatching), 15 m observation noise, 60 m search
   radius. Points are thinned to ≥ 5 s, and runs are split at > 5 min gaps.
9. Stop rule: < 10 m moved in 60 s. Suspect segments (> 30 km/h,
   |slope| > 80%, match error > 40 m) are excluded. Walking mode is anchored
   on foot-only trails.
10. Terrain is read every 1 m along the matched path: 5 m pitches (max, SD),
    relief around an 11 m moving average, and side slope after 2 m / 10 m
    Gaussian smoothing.
11. The CRPS is the exact sample formula over the 100 quantiles. Skill is
    relative to the refitted slope curve.
12. 95% CIs come from 2,000 bootstrap draws of whole outings, uploaders or
    regions.
13. Seeds: 0 for the folds, trees and bootstrap; torch seeds 0–2.
14. Software: Python 3.12, scikit-learn 1.9.1, SciPy 1.18, PyTorch 2.14
    (CPU). Everything ran on CPUs (≤ 8 cores); no GPU was used.
