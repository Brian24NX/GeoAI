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
  regionfe)   $H --covariates $T5 --region-fe --splits outing5 block5 \
                 --out results/t3_harness_regionfe ;;
  *) echo "unknown run $1"; exit 2 ;;
esac >> "logs/refresh_harness_$1.log" 2>&1 \
  && say "done  harness $1" || { say "FAILED harness $1"; exit 1; }
