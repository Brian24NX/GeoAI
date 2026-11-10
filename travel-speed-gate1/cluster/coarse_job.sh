#!/bin/bash
# Idea 1 (decision #131): terrain from coarser elevation (10 m, 30 m) plus
# aspect and curvature, then their four harness runs in parallel. One job,
# because Brian's other jobs leave one slot; the class QOS allows 8 CPUs
# per job. Progress: logs/coarse.log.
#   sbatch -A engr-class-any -p linuxlab-project -c 8 --mem 48G \
#          -t 6:00:00 -o logs/coarse_job_%j.out cluster/coarse_job.sh
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/coarse.log; }
say "start terrain_coarse"
if $PY -u -W ignore t2_terrain_coarse.py --all --workers 8 \
     >> logs/coarse_steps.log 2>&1; then say "done  terrain_coarse"
else say "FAILED terrain_coarse"; exit 1; fi
export OMP_NUM_THREADS=2            # 4 runs x 2 threads = 8 CPUs
for r in coarse10 coarse30 coarse30s5 aspcurv; do
  bash cluster/refresh_harness.sh $r && say "done  harness $r" \
    || say "FAILED harness $r" &
done
wait
say "COARSE DONE"
