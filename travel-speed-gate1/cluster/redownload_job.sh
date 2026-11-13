#!/bin/bash
#SBATCH -J t1_osm
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 1
#SBATCH --mem 16G
#SBATCH -t 7-00:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_redownload_%j.log
# Decision #135 (11 Nov 2026): the full OSM download for the Bay Area
# (skipped in October because its tiles time out, so it was built from the
# lab crawl alone) and for the 4 tiles where the same timeout cut off the
# oldest uploads. t1_download.py now splits a box the API can't answer into
# quarters. One region at a time (the OSM API is volunteer-run). Stops at
# the size cap Brian approved: 8 GB of OSM pages + original GPX files in all
# (the rest of the 10 GB is left for elevation, lidar and embeddings).
# Each finished region submits its elevation + build jobs.
# 12 Nov (#136): the Bay Area is dropped (paused at 6.8 GB: 96% car logs);
# Brian OK'd the 4 tiles with up to 11 GB in all, so OSM stops at 10 GB
# (the budget file already holds the Bay Area's 6.8 GB).
#   sbatch --export=ALL,MAXGB=10 cluster/redownload_job.sh   (the 4 tiles)
#   sbatch cluster/redownload_job.sh shenandoah              (some of them)
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
KEYS=${*:-"sangabriel shenandoah frontrange cascades"}
MAXGB=${MAXGB:-8}
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/t1_queue.log; }
for KEY in $KEYS; do
  say "REDOWNLOAD $KEY: start"
  LOGF="logs/t1_download_${KEY}.log"
  N0=$(cat "$LOGF" 2>/dev/null | wc -l)          # only this run's lines count
  $PY -u t1_download.py --region "$KEY" --max-gb "$MAXGB" \
      --budget-file logs/redownload_bytes.json >> "$LOGF" 2>&1
  RC=$?
  LAST=$(tail -n +$((N0 + 1)) "$LOGF" | grep "^T1 DOWNLOAD" | tail -1)
  say "REDOWNLOAD $KEY: exit $RC, $LAST"
  if [ "$LAST" = "T1 DOWNLOAD DONE" ]; then
    rm -f "logs/build_submitted_${KEY}"
    $PY -c "import t1_queue as q; q.submit_build('$KEY')"
  elif echo "$LAST" | grep -q "size cap"; then
    say "REDOWNLOAD: stopped at the size cap; ask Brian before going on"
    exit 3
  fi
done
say "REDOWNLOAD DONE: $KEYS"
