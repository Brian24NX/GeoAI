# How to re-run the pipeline

This guide takes you from raw downloads to every number, figure and PDF in
the project, in order, with the exact commands. Most of it runs on the lab
cluster; the figures and PDFs are built on the laptop. Every script also
has a description at its top (inputs, outputs, how to run it).

Last checked: 12 Oct 2026, on the complete 17-region T1.

## The pipeline at a glance

```
 OSM API pages + original GPX ──┐
 lab crawl of OSM traces ───────┼─> T1, one region at a time ──> t1_combine ──> data/t1_all/
 USGS 5 m elevation ────────────┘   (build, modes, finalize)                         │
                                                                                     ├─> checks, findings, T4 curves
                                                                                     ├─> T2 covariates (data/t2/):
                                                                                     │     terrain 5 m + 1 m, land cover,
                                                                                     │     satellite embeddings
                                                                                     └─> T3 harness runs ──> results/
 results/  ── copy to laptop ──>  paper figures, explainer page, paper and slide PDFs
```

Time from nothing: the OSM downloads take days (the API is volunteer-run
and we fetch one region at a time). After that, cluster time is:
- region builds: 15–25 min each, about 5 h for all 17 one after another;
- the downstream refresh: ~2 h;
- all harness runs: ~1 h.

## Where things live

| What | Where | Note |
|---|---|---|
| Code | `travel-speed-gate1/` in this repo; a copy runs on the cluster in `/engrfs/project/jacobsn/zhou.n/travel-speed/` | Edit on the laptop, then copy up (below) |
| Python env | cluster: `/engrfs/project/jacobsn/zhou.n/envs/t1` (Python 3.12); laptop: `../.venv` | Packages: `requirements-pipeline.txt`; rebuild the cluster env with `cluster/make_env.sh` |
| Raw downloads | `cache/` on the cluster (~27 GB: 1 m elevation 14 GB, 5 m grids and map layers 9 GB, original GPX 3.5 GB) | Never delete: re-downloading takes days and loads volunteer servers |
| Lab crawl | `cache/lab_index` → `/engrfs/project/jacobsn/zhou.n/osm_lab_index`, `cache/lab_traces` → `.../lab_extracts` (symlinks) | Built once from `/engrfs/project/jacobsn/OSM_data` |
| Datasets | `data/t1_<region>/`, `data/t1_all/`, `data/t2/` on the cluster | **Stay on the cluster**: they hold OSM user names |
| Results | `results/` (51 MB) on the cluster, copied to the laptop and GitHub | The repo must stay private |
| Logs | `logs/` on the cluster | One log per step or job |
| Secret | `cache/release_salt.txt` | Keys of the de-identified copy. Never publish |

## Working on the cluster

```bash
ssh zhou.n@shell3.engr.wustl.edu         # key login; VPN when off campus
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
```

- Never compute on the login node. Submit a job:
  `sbatch -A engr-class-any -p linuxlab-project -c 8 --mem 48G -t 2:00:00 -o logs/<name>_%j.out --wrap "$PY -u <script>.py <args>"`
- Limits: at most 8 CPUs per job and 4 running jobs.
- Watch jobs with `squeue -u zhou.n`, and read the log in `logs/`.
- The message `spank-auks: cred forwarding failed` is harmless.

Code up, results down (from the repo folder on the laptop):

```bash
scp travel-speed-gate1/*.py zhou.n@shell3.engr.wustl.edu:/engrfs/project/jacobsn/zhou.n/travel-speed/
scp travel-speed-gate1/cluster/*.sh zhou.n@shell3.engr.wustl.edu:/engrfs/project/jacobsn/zhou.n/travel-speed/cluster/
rsync -a zhou.n@shell3.engr.wustl.edu:/engrfs/project/jacobsn/zhou.n/travel-speed/results/ travel-speed-gate1/results/
```

## Step by step

### 0. Once: index the lab crawl (cluster)

The lab folder holds the original files of ~1.5M public and identifiable
OSM traces (2016–2022), with timestamps the API no longer gives.

1. Index it: `cluster/build_lab_index.py`, via `cluster/index_job.sh`
   (a few minutes). Output: `osm_lab_index/` (index and uploader names).
2. Pull each region's traces: `cluster/extract_lab_traces.py`, via
   `cluster/extract_job.sh`, which lists all 23 candidate boxes
   (~15–30 min). Output: `lab_extracts/<key>.parquet`.
3. `scout_regions.py` ranks candidate regions by hike-like traces
   (`results/region_scout.csv`).

### 1. T1, region by region (cluster, unattended)

Regions are boxes in `regions.py`. One job runs the whole queue:

```bash
sbatch cluster/t1_osm_job.sh
```

- It downloads OSM data (`t1_download.py`) one region at a time: trace
  pages, the original GPX of identifiable traces, and the trail network.
  Huge city boxes are probed first and skipped (`--probe`).
- After each region it submits `cluster/t1_region_job.sh`:
  - `dem <key>`: 5 m USGS elevation (`t1_prefetch_dem.py`);
  - `build <key>` (8 CPUs, 13–26 min):
    1. `t1_build_dataset.py`: clean, flag stops, map-match, cut into 50 m
       and 25 m segments;
    2. `t1_modes.py` on all built regions (walk, run or bike/ski);
    3. `t1_variants.py`: the 4 stop rules;
    4. `t1_finalize.py`: `block_10km` and trail networks for the splits;
    5. `t1_summary.py`.
  - Lab-only regions use `prep <key>` (trail network from `t1_ways.py`
    plus elevation) instead of the OSM download.
- Follow it in `logs/t1_queue.log`; per-region logs are `logs/t1_build_<key>.log`.
- To add a region: add its box to `regions.py`, extract its lab traces
  (step 0.2), and add the key to `cluster/t1_osm_job.sh`.

### 2. Everything downstream of the builds (cluster, one job, ~2 h)

```bash
sbatch -A engr-class-any -p linuxlab-project -c 2 --mem 32G -t 12:00:00 cluster/refresh_all.sh
```

Steps, with times from the 12 Oct run (progress: `logs/refresh.log`):

| Step | Script | Output | Time |
|---|---|---|---|
| summary | `t1_summary.py` | `results/t1_summary/` (region table) | 7 min |
| dem_quality | `t1_dem_quality.py --n 300` | `results/t1_dem_quality.csv` (1 m lidar under trails?) | 14 min |
| mode_check | `t1_mode_check.py` | `results/t1_mode_check/` (modes vs the apps' own labels) | 4 min |
| combine | `t1_combine.py` | `data/t1_all/` (one dataset + `DATA_CARD.md`) | 15 s |
| findings | `t1_findings.py` | `results/t1_findings/` (curve shape, variance, fatigue, asymmetry, `slope_bins.csv`) | 2 min |
| terrain5m | `t2_terrain5m.py --all` | `data/t2/terrain5m_<region>.parquet` | 12 min |
| dem1m | `t2_dem1m.py --all` | `cache/dem1m/` (new cells only; the first full download was ~9 h, 12.5 GB) | 54 min |
| terrain1m | `t2_terrain1m.py --all` | `data/t2/terrain1m_<region>.parquet` | 15 min |
| landcover | `t2_landcover.py --all` | `data/t2/landcover_<region>.parquet` | 3 min |
| embeddings | `t2_embed.py --year 2022 --region <keys>` | `data/t2/aef2022_<region>.parquet` | 13 min for 4 regions |
| terrain_curve | `t4_terrain_curve.py` | `results/t4_terrain_curve/` (Eq. 1) | 2 min |
| terrain_eff | `t2_terrain_effects.py` | `results/t2_terrain_effects/` (quintiles figure) | 20 s |

The embeddings step re-runs only the regions listed in `UPGRADED` at the
top of the script. For a fresh start, list all 17 keys. The tile index has
to be downloaded first, once:
`https://data.source.coop/tge-labs/aef/v1/annual/aef_index.parquet` (78 MB),
saved as `cache/aef/aef_index.parquet`.

### 3. The harness runs (cluster, one job per run, 2–20 min each)

```bash
sbatch -A engr-class-any -p linuxlab-project -c 8 --mem 48G -t 2:00:00 cluster/refresh_harness.sh terrain15m
```

| Run | Covariates | Folder `results/...` | Used for |
|---|---|---|---|
| `base` | none | `t3_harness` | Tobler, Campbell, slope curves, tags, place memory, personal pace |
| `terrain15m` | terrain 5 m + 1 m | `t3_harness_terrain15m` | **The headline**: terrain, STRIDE, Eq. 1; Table I, Figs. 3–5 |
| `terrain5m` | terrain 5 m | `t3_harness_terrain5m` | 1 m vs 5 m |
| `hidden5m` | hidden climbing only | `t3_harness_hidden5m` | how much of the gain is uneven grade |
| `landcover` | 30 m vegetation | `t3_harness_landcover` | vegetation adds nothing |
| `aef` | embeddings | `t3_harness_aef` | embeddings alone |
| `aefterrain` | embeddings + terrain 5 m | `t3_harness_aef_terrain` | terrain + embeddings (+ tags) |
| `regionfe` | terrain 5 m + region offsets | `t3_harness_regionfe` | terrain is not a region proxy |
| `hetero` | terrain 5 m + 1 m, terrain-dependent spread | `t3_harness_hetero` | a varying spread doesn't help |
| `robust` | terrain 5 m + 1 m, plus a time split and GPS-rate and slope subsets | `t3_harness_robust` | robustness; then `$PY t3_robust_summary.py` writes `robust_summary.md` |
| `zones` | terrain 5 m + 1 m; splits: leave one zone out, East ↔ West | `t3_harness_zones` | no neighbouring region in training |
| `context` | day of year + local hour (after `t3_season_time.py`) | `t3_harness_context` | season and time of day alone |
| `weather` | Daymet weather on the hike's day (after `t2_weather.py`) | `t3_harness_weather` | weather alone |
| `weatherterrain` | terrain 5 m + 1 m + weather | `t3_harness_weather_terrain` | does weather add to terrain? |
| `wmterrain`, `wmveg`, `wmterrainveg` | White Mountains only (outing and block splits): terrain, lidar vegetation, both | `t3_harness_wm_*` | does point-cloud vegetation add to terrain within a region? |
| `vegterrain`, `vegonly`, `vegboth` | the 15 regions with lidar point clouds: terrain, lidar vegetation, both | `t3_harness_veg15_*` | does it transfer to unseen regions? |
| `contextterrain` | terrain 5 m + 1 m + day of year + hour | `t3_harness_context_terrain` | do they add to terrain? |

The harness is seeded, so a re-run gives identical numbers. The robust
run reproduces `terrain15m` to 1e-16, and `t3_robust_summary.py` checks
this.

### 4. Analyses outside the refresh (cluster, minutes each)

| Script | Output | Time |
|---|---|---|
| `t4_mode_curves.py` | `results/t4_mode_curves/` (speed by mode, ratios, multiplier test) | 4 min |
| `t4_trail_map.py --region wm` | `results/t4_trail_map/` (pace on every trail) | 2 min |
| `t1_sampling_check.py` | `results/t1_sampling_check/` (sparse traces read slow) | 1 min |
| `t3_tag_transfer.py` | `results/t3_tag_transfer/` (why tags don't transfer: within-hike tag and terrain effects by region) | 3 min |
| `t2_weather.py` | `data/t2/weather_<region>.parquet` (Daymet, each hike's day and place; ~1 request/s, cached in `cache/daymet/`) and `results/t2_weather/`; then harness runs `weather` and `weatherterrain` | ~1 h first time |
| `t3_season_time.py` | `results/t3_season_time/` (season and time of day) and `data/t2/context_<region>.parquet`; then harness runs `context` and `contextterrain` | 2 min |
| `make_paper_data.py` | `results/fig1_wm_segments.parquet` (Fig. 1 inset) | 1 min |
| `make_explainer_data.py` | `results/explainer_data.json` (**run last**: it reads the results above) | 1 min |
| `t1_release.py` | `data/t1_release/` (de-identified copy; stays on the cluster) | minutes |
| `t2_lidarveg.py --region <key>` | `data/t2/lidarveg_<key>.parquet`: understory density, canopy cover and height from USGS 3DEP point clouds on AWS (blocks cached in `cache/ept/<project>/`, ~0.25 MB per segment; `--dry-run` sizes it). Not for Yosemite (no point clouds) or the North Shore (Canada) | ~45 min per 25,000 blocks |
| `t2_lidarveg_effects.py --region wm` | `results/t2_lidarveg_effects/` (speed by vegetation quintile, within hikes) | 2 min |
| `t1_route_check.py --region <key>` | `results/t1_route_check/` (distance along the trail vs straight lines; the T1 v2 test) | 2–5 min per region |

### 5. On the laptop: figures, explainer, PDFs

```bash
cd travel-speed-gate1
../.venv/bin/python make_paper_figures.py      # -> ../paper/figures/
../.venv/bin/python make_explainer.py          # -> ../Project_Explainer.html
cd ../paper && tectonic main.tex               # -> paper/main.pdf
cd ../meeting_plots/oct16 && tectonic slides.tex
```

- `make_paper_figures.py` needs the copied `results/` plus the Natural
  Earth outlines in `cache/naturalearth/` for Fig. 1:
  `ne_110m_admin_0_countries.geojson` and
  `ne_110m_admin_1_states_provinces_lines.geojson`, from
  `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/`.
- Then commit and push (the repo stays private).

## After a change: what to re-run

| You changed | Re-run |
|---|---|
| a region (rebuilt or added) | its build job (it re-runs modes and finalize for every region), then steps 2–5 |
| a covariate script | that step of `refresh_all.sh` (or the script with `--region`), the harness runs that use it, then step 5 |
| the harness | the runs in step 3, `make_explainer_data.py`, then step 5 |
| only figures or text | step 5 |

## Where each number in the paper comes from

| In the paper | File | Made by |
|---|---|---|
| Dataset counts (2,876 traces, 1,992 outings, 290,640 segments, 4,702 h) | `results/t1_all/DATA_CARD.md` | `t1_combine.py` |
| Fig. 1, the regions map | `results/t1_summary/regions.csv`, `results/fig1_wm_segments.parquet` | `t1_summary.py`, `make_paper_data.py` |
| Fig. 2, speed vs slope and the down/up ratio | `results/t1_findings/numbers.json`, `slope_bins.csv` | `t1_findings.py` |
| Table I and Fig. 3, skill scores | `metrics.csv`, `skill_ci.csv` in the `t3_harness*` folders | harness runs `base`, `terrain15m`, `landcover`, `aef`, `aefterrain` |
| Fig. 4, per region | `t3_harness_terrain15m/loro_by_region.csv` | `terrain15m` |
| Fig. 5, whole-hike time | `t3_harness_terrain15m/hike_times.csv` | `terrain15m` |
| Eq. 1, the terrain-adjusted formula | `results/t4_terrain_curve/formula.json` | `t4_terrain_curve.py` |
| Fig. 6, pace on every trail | `results/t4_trail_map/` | `t4_trail_map.py` |
| Robustness: time, GPS rate, slope | `results/t3_harness_robust/robust_summary.md` | `robust` run, `t3_robust_summary.py` |
| Travel modes | `results/t4_mode_curves/` | `t4_mode_curves.py` |
| Sparse traces read slow | `results/t1_sampling_check/summary.json` | `t1_sampling_check.py` |
| Why tags don't transfer | `results/t3_tag_transfer/summary.csv`, `coverage.csv` | `t3_tag_transfer.py` |

All of these numbers are collected, with their decision numbers, in
`docs/NEXT_STEPS.md` §1a and `DECISIONS_LOG.md`.

## Built-in checks

- `t1_build_dataset.py` runs a slope sign test before every build and
  stops if it fails (uphill must be positive).
- `selftest.py` tests the Gate 1 counter on fake data, offline.
- The data checks are `t1_match_qa.py` (map matching), `t1_dem_quality.py`
  (elevation source) and `t1_mode_check.py` (travel modes).
- The harness is seeded and its results reproduce exactly.

## Things that bite

- **OSM API.** It is run by volunteers: one region at a time, 1 s between
  requests, and every page is cached. Timestamped ("usable") points come
  first in the pages; see `README.md`.
- **Overpass** is often "too busy". The code retries, tries mirror
  servers, then asks for 16 smaller boxes.
- **USGS elevation** times out on big images, so tiles come in quarters.
  Spells of 504 errors are retried, and stopped runs resume.
- **AlphaEarth.** Use `data.source.coop` (`source.coop` returns a web
  page), and read the `.tiff` files: the `.vrt` files fail over HTTP.
- **Cluster.**
  - The home quota is nearly full, so work in `/engrfs/project/jacobsn/zhou.n`.
  - Move many files as one `tar` stream, not with `rsync`.
  - `pkill -f <pattern>` can kill your own ssh session.
  - There is no PyPI access, so packages are installed from offline
    wheels (`cluster/make_env.sh`).
- **Sparse traces read slow.** Traces with more than 10 s between points
  read up to 11% slow (decision #104). Filter or correct with
  `native_interval_s`.
- **The stop rule is a draft** until the hand-labeled sheet in
  `stop_check/` is scored (`score_stop_labels.py`).

AI assistance: Claude (Anthropic) helped write the code and this guide;
Brian reviews the work and is responsible for it.
