#!/bin/bash
# Campbell et al. (2018) understory strata for the given regions, one after
# another (t2_lidarveg.py --strata; the point clouds are already cached in
# cache/ept/, so nothing is downloaded).
#   sbatch -A engr-class-any -p linuxlab-project -c 8 --mem 32G -t 6:00:00 \
#       cluster/lidarstrata_job.sh gorge olympic
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/refresh.log; }
for r in "$@"; do
  if $PY -u -W ignore t2_lidarveg.py --region "$r" --strata --workers 8 \
       >> "logs/lidarstrata_$r.log" 2>&1; then
    say "done  lidarstrata $r"
  else
    say "FAILED lidarstrata $r"
  fi
done
