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
#   sbatch cluster/redownload_job.sh            (default regions)
#   sbatch cluster/redownload_job.sh bayarea    (some of them)
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
KEYS=${*:-"bayarea sangabriel shenandoah frontrange cascades"}
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/t1_queue.log; }
for KEY in $KEYS; do
  say "REDOWNLOAD $KEY: start"
  $PY -u t1_download.py --region "$KEY" --max-gb 8 \
      --budget-file logs/redownload_bytes.json >> "logs/t1_download_${KEY}.log" 2>&1
  RC=$?
  LAST=$(grep "^T1 DOWNLOAD" "logs/t1_download_${KEY}.log" | tail -1)
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
