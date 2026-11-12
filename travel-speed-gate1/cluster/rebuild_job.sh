#!/bin/bash
#SBATCH -J t1_build
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH -t 1-00:00:00
#SBATCH --dependency=singleton
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_rebuild_%j.log
# Decision #135 (11 Nov 2026): rebuild regions with the current builder, so
# every region is built by the same code (the new rule that rejoins
# anonymous recordings cut at box edges changes every region a little).
# Default: the 12 regions whose OSM download is unchanged; the other 5 are
# rebuilt after their re-download (cluster/redownload_job.sh). Shares the job
# name t1_build (singleton) with those builds: one build at a time.
# First copies every region's October build (T1 v1) to data/archive/.
#   sbatch cluster/rebuild_job.sh            (the 12 regions)
#   sbatch cluster/rebuild_job.sh wm adk     (some regions)
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
KEYS=${*:-"wm adk catskills greenmtn smokies pisgah wasatch gorge olympic northshore tahoe yosemite"}
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/t1_queue.log; }
ARCH=data/archive/t1_v1_2026-10
mkdir -p "$ARCH"
for D in $($PY -c "import regions; print(' '.join(str(regions.data_dir(k)) for k in regions.CANDIDATES))"); do
  [ -d "$D" ] && [ ! -e "$ARCH/$(basename "$D")" ] && cp -a "$D" "$ARCH/"
done
say "REBUILD: October builds copied to $ARCH"
FAILED=""
for KEY in $KEYS; do
  say "REBUILD $KEY: start (cluster, ${SLURM_CPUS_PER_TASK:-8} CPUs)"
  if $PY -u t1_build_dataset.py --region "$KEY" --workers "${SLURM_CPUS_PER_TASK:-8}" \
      >> "logs/t1_build_${KEY}.log" 2>&1; then
    say "REBUILD $KEY: done"
  else
    say "REBUILD $KEY: FAILED, see logs/t1_build_${KEY}.log"; FAILED="$FAILED $KEY"
  fi
done
say "REBUILD DONE: $KEYS${FAILED:+ (FAILED:$FAILED)}"
[ -z "$FAILED" ]
