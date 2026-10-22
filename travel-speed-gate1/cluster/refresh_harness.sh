#!/bin/bash
# One harness run of the refresh (see refresh_all.sh). Argument: a name.
#   sbatch ... cluster/refresh_harness.sh terrain5m
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
H="$PY -u -W ignore t3_harness.py"
T5=$(ls data/t2/terrain5m_*.parquet)
T1=$(ls data/t2/terrain1m_*.parquet)
LC=$(ls data/t2/landcover_*.parquet)
AE=$(ls data/t2/aef2022_*.parquet)
CX=$(ls data/t2/context_*.parquet 2>/dev/null)   # t3_season_time.py
WX=$(ls data/t2/weather_*.parquet 2>/dev/null)   # t2_weather.py
LV=$(ls data/t2/lidarveg_*.parquet 2>/dev/null)  # t2_lidarveg.py
LVR="wm adk catskills greenmtn shenandoah smokies pisgah frontrange wasatch cascades gorge olympic bayarea sangabriel tahoe"
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/refresh.log; }
case "$1" in
  base)       $H --out results/t3_harness ;;
  terrain5m)  $H --covariates $T5 --out results/t3_harness_terrain5m ;;
  hidden5m)   $H --covariates $T5 --features hidden_grade_5m \
                 --out results/t3_harness_hidden5m ;;
  terrain15m) $H --covariates $T5 $T1 --out results/t3_harness_terrain15m ;;
  landcover)  $H --covariates $LC --out results/t3_harness_landcover ;;
  aef)        $H --covariates $AE --out results/t3_harness_aef ;;
  aefterrain) $H --covariates $AE $T5 --out results/t3_harness_aef_terrain ;;
  robust)     $H --covariates $T5 $T1 --splits outing5 block5 loro time \
                 --out results/t3_harness_robust ;;
  hetero)     $H --covariates $T5 $T1 --hetero --out results/t3_harness_hetero ;;
  context)    $H --covariates $CX --out results/t3_harness_context ;;
  zones)      $H --covariates $T5 $T1 --splits macro eastwest \
                 --out results/t3_harness_zones ;;
  weather)    $H --covariates $WX --out results/t3_harness_weather ;;
  vegterrain) $H --regions $LVR --covariates $T5 $T1 \
                 --out results/t3_harness_veg15_terrain ;;
  vegonly)    $H --regions $LVR --covariates $LV \
                 --out results/t3_harness_veg15_lidarveg ;;
  vegboth)    $H --regions $LVR --covariates $T5 $T1 $LV \
                 --out results/t3_harness_veg15_terrain_lidarveg ;;
  wmterrain)  $H --regions wm --splits outing5 block5 \
                 --covariates data/t2/terrain5m_wm.parquet \
                 data/t2/terrain1m_wm.parquet --out results/t3_harness_wm_terrain ;;
  wmveg)      $H --regions wm --splits outing5 block5 \
                 --covariates data/t2/lidarveg_wm.parquet \
                 --out results/t3_harness_wm_lidarveg ;;
  wmterrainveg) $H --regions wm --splits outing5 block5 \
                 --covariates data/t2/terrain5m_wm.parquet \
                 data/t2/terrain1m_wm.parquet data/t2/lidarveg_wm.parquet \
                 --out results/t3_harness_wm_terrain_lidarveg ;;
  weatherterrain) $H --covariates $T5 $T1 $WX \
                 --out results/t3_harness_weather_terrain ;;
  contextterrain) $H --covariates $T5 $T1 $CX \
                 --out results/t3_harness_context_terrain ;;
  regionfe)   $H --covariates $T5 --region-fe --splits outing5 block5 \
                 --out results/t3_harness_regionfe ;;
  hikers)     $H --covariates $T5 $T1 --splits hiker5 loro_hiker \
                 --out results/t3_harness_hikers ;;
  folds15m)   $H --covariates $T5 $T1 --save-folds \
                 --out results/t3_harness_terrain15m_folds ;;
  foldshikers) $H --covariates $T5 $T1 --splits hiker5 loro_hiker --save-folds \
                 --out results/t3_harness_hikers_folds ;;
  fixid15m)   $H --covariates $T5 $T1 --out results/t3_harness_terrain15m_fixid ;;
  *) echo "unknown run $1"; exit 2 ;;
esac >> "logs/refresh_harness_$1.log" 2>&1 \
  && say "done  harness $1" || { say "FAILED harness $1"; exit 1; }
