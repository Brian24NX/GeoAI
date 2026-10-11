#!/bin/bash
# One region's elevation download ("dem") or build ("build") on the cluster.
# Submitted by t1_queue.py --submit-builds; see the README.
set -u
STEP=$1; KEY=$2
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/t1_queue.log; }
if [ "$STEP" = prep ]; then
  # fast lab-only path: trail ways (Overpass) and elevation (USGS) at once
  $PY -u t1_ways.py --region "$KEY" >> "logs/t1_ways_${KEY}.log" 2>&1 &
  W=$!
  for try in 1 2 3; do
    $PY -u t1_prefetch_dem.py --region "$KEY" >> "logs/t1_dem_${KEY}.log" 2>&1 && break
    sleep 600
  done
  wait $W; WRC=$?
  $PY -c "import t1_queue as q, sys; sys.exit(0 if q._dem_complete('$KEY') else 1)" && [ $WRC -eq 0 ] \
    && say "PREP $KEY: ways + elevation done (cluster)" || { say "PREP $KEY: FAILED (ways exit $WRC)"; exit 1; }
elif [ "$STEP" = dem ]; then
  for try in 1 2 3; do
    $PY -u t1_prefetch_dem.py --region "$KEY" >> "logs/t1_dem_${KEY}.log" 2>&1 && break
    sleep 600
  done
  $PY -c "import t1_queue as q, sys; sys.exit(0 if q._dem_complete('$KEY') else 1)" \
    && say "DEM $KEY: done (cluster)" || { say "DEM $KEY: INCOMPLETE (cluster)"; exit 1; }
else
  LOG="logs/t1_build_${KEY}.log"
  say "BUILD $KEY: start (cluster, $SLURM_CPUS_PER_TASK CPUs)"
  $PY -u t1_build_dataset.py --region "$KEY" --workers "${SLURM_CPUS_PER_TASK:-8}" >> "$LOG" 2>&1 \
    || { say "BUILD $KEY: build FAILED, see $LOG"; exit 1; }
  BUILT=$(ls -d data/t1_*/ | grep -v -e sample -e archive | while read d; do [ -f "$d/segments_L50.parquet" ] && echo "${d%/}"; done)
  $PY t1_modes.py $BUILT >> "$LOG" 2>&1 \
    && $PY -u t1_variants.py --region "$KEY" >> "$LOG" 2>&1 \
    && for d in $BUILT; do k=$($PY -c "import regions; print(regions.key_of('$(basename $d)') or '')"); [ -n "$k" ] && $PY t1_finalize.py --region "$k" >> "$LOG" 2>&1; done \
    && $PY t1_summary.py >> "$LOG" 2>&1 \
    && say "BUILD $KEY: done (cluster)" || { say "BUILD $KEY: FAILED after the build, see $LOG"; exit 1; }
fi
