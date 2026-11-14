#!/bin/bash
#SBATCH -J t1_refresh
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH -t 12:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_refresh_v11_%j.log
# T1 v1.1 (13 Nov 2026, #135-136): everything downstream of the 16 rebuilt
# regions that needs NO bulk download, then the size checks for the steps
# that do (1 m DEM cells, lidar blocks, satellite embeddings). The download
# steps run in a second job, after Brian's size budget is checked.
# Segment ids changed in every region, so every covariate is redone.
# October's combined data, covariates and results are archived first.
#   sbatch cluster/refresh_v11_prep.sh
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
ARCH=data/archive/v1_2026-10_downstream
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/refresh.log; }
step() {
  local name=$1; shift
  say "start $name"
  if "$@" >> logs/refresh_steps.log 2>&1; then say "done  $name"
  else say "FAILED $name"; exit 1; fi
}
if [ ! -e "$ARCH/segments_L50.parquet" ]; then
  say "archive: October's combined data, covariates, results -> $ARCH"
  mkdir -p "$ARCH/results"
  cp -a data/t1_all/. "$ARCH/" && cp -a data/t2 "$ARCH/t2" \
    && cp -a results/t1_findings results/t3_* results/t4_* "$ARCH/results/" \
    || { say "FAILED archive"; exit 1; }
fi
KEYS=$($PY -c "import regions; print(' '.join(k for k in regions.CANDIDATES if regions.kept(k)))")
LVR="wm adk catskills greenmtn shenandoah smokies pisgah frontrange wasatch cascades gorge olympic sangabriel tahoe"
# dem_quality is a diagnostic (USGS service; it timed out with a 504 on
# 13 Nov): a failure is logged, not fatal; rerun it on its own later.
say "start dem_quality"
if $PY -u -W ignore t1_dem_quality.py --n 300 >> logs/refresh_steps.log 2>&1; then
  say "done  dem_quality"; else say "SKIPPED dem_quality (failed; rerun later)"; fi
step mode_check     $PY -u -W ignore t1_mode_check.py
step combine        $PY -u -W ignore t1_combine.py
step findings       $PY -u -W ignore t1_findings.py
step terrain5m      $PY -u -W ignore t2_terrain5m.py --all
step landcover      $PY -u -W ignore t2_landcover.py --all
step context        $PY -u -W ignore t3_season_time.py
step terrain_coarse $PY -u -W ignore t2_terrain_coarse.py --all --workers 8
step terrain_cop30  $PY -I -u -W ignore t2_terrain_coarse.py --source cop30 --all --workers 8
step size_dem1m     $PY -u -W ignore t2_dem1m.py --all --dry-run
step size_lidar     $PY -u -W ignore cluster/v11_lidar_size.py $LVR
step size_aef       $PY -u -W ignore t2_embed.py --region $KEYS --reuse "$ARCH" --count-only
say "REFRESH V11 PREP DONE"
grep -h -E "cells \(|^LIDAR|reuse the old" logs/refresh_steps.log | tail -n 40 | tee -a logs/refresh.log
