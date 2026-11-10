#!/bin/bash
# Decision #132: terrain from the real 30 m DEM (Copernicus GLO-30 tiles in
# cache/cop30/, cluster/cop30_download.sh), then two harness runs in
# parallel: everything from Copernicus, and its terrain on T1's 5 m slope.
# Progress: logs/coarse.log.
#   sbatch -A engr-class-any -p linuxlab-project -c 8 --mem 48G \
#          -t 4:00:00 -o logs/cop30_job_%j.out cluster/cop30_job.sh
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/coarse.log; }
say "start terrain_cop30"
if $PY -I -u -W ignore t2_terrain_coarse.py --source cop30 --all \
     --workers 8 >> logs/coarse_steps.log 2>&1; then say "done  terrain_cop30"
else say "FAILED terrain_cop30"; exit 1; fi
export OMP_NUM_THREADS=4            # 2 runs x 4 threads = 8 CPUs
for r in cop30 cop30s5; do
  bash cluster/refresh_harness.sh $r && say "done  harness $r" \
    || say "FAILED harness $r" &
done
wait
say "COP30 DONE"
