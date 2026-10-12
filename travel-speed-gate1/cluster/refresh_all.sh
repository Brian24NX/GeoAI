#!/bin/bash
# Rebuild everything downstream of the T1 region builds, in order:
# checks -> combined dataset -> T2 covariates -> T4 curve -> explainer data.
# The harness runs are separate jobs (cluster/refresh_harness.sh), started
# after this one succeeds. Progress: logs/refresh.log (one line per step);
# step output: logs/refresh_steps.log.
#   sbatch -A engr-class-any -p linuxlab-project -c 2 --mem 32G \
#          -t 12:00:00 cluster/refresh_all.sh
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
UPGRADED="northshore sangabriel gorge wasatch"   # regions rebuilt since the
                                                 # covariates were made
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/refresh.log; }
step() {
  local name=$1; shift
  say "start $name"
  if "$@" >> logs/refresh_steps.log 2>&1; then say "done  $name"
  else say "FAILED $name"; exit 1; fi
}
step summary        $PY -u -W ignore t1_summary.py
step dem_quality    $PY -u -W ignore t1_dem_quality.py --n 300
step mode_check     $PY -u -W ignore t1_mode_check.py
step combine        $PY -u -W ignore t1_combine.py
step findings       $PY -u -W ignore t1_findings.py
step terrain5m      $PY -u -W ignore t2_terrain5m.py --all
step dem1m          $PY -u -W ignore t2_dem1m.py --all    # new cells only
step terrain1m      $PY -u -W ignore t2_terrain1m.py --all
step landcover      $PY -u -W ignore t2_landcover.py --all
step embeddings     $PY -u -W ignore t2_embed.py --year 2022 --region $UPGRADED
step terrain_curve  $PY -u -W ignore t4_terrain_curve.py
step terrain_eff    $PY -u -W ignore t2_terrain_effects.py
say "REFRESH PREP DONE"
