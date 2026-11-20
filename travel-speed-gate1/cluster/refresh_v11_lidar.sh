#!/bin/bash
#SBATCH -J v11_lidar
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH -t 2-00:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_v11_lidar_%j.log
# T1 v1.1 refresh, part 2b (19 Nov 2026): lidar vegetation and strata for
# the 14 regions with point clouds. Only blocks not yet in cache/ept are
# downloaded (size check 13 Nov: 4,576 blocks, ~2.19 GB, San Gabriels last).
# October's per-project parts carry the old segment ids, so they are moved
# aside first (a copy is also in the archive's t2/).
source /engrfs/project/jacobsn/zhou.n/travel-speed/cluster/v11_common.sh
LVR="adk olympic catskills gorge greenmtn pisgah smokies wasatch cascades frontrange tahoe wm shenandoah sangabriel"
if [ -d data/t2/lidarveg_parts ]; then
  mkdir -p "$ARCH/live_moved" && mv data/t2/lidarveg_parts "$ARCH/live_moved/lidarveg_parts_$(date +%s)"
fi
for r in $LVR; do
  step lidarveg_$r $PY -u -W ignore t2_lidarveg.py --region "$r" --workers 8
  guard
done
for r in $LVR; do
  step lidarstrata_$r $PY -u -W ignore t2_lidarveg.py --region "$r" --strata --workers 8
done
say "V11 LIDAR DONE"
