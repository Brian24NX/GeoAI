#!/bin/bash
#SBATCH -J t1_build
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH -t 12:00:00
#SBATCH --dependency=singleton
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_finish_rebuild_%j.log
# Decision #135: after ALL 17 regions are rebuilt (cluster/rebuild_job.sh and
# the builds cluster/redownload_job.sh submits), redo the steps that pool
# regions, once, in order: travel modes over every region (anchors are
# pooled), the stop-rule variants of every region (they read the modes), the
# data cards, the T1 summary. Then refresh_all.sh and the harness runs.
#   sbatch cluster/finish_rebuild_job.sh
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/t1_queue.log; }
LOG=logs/finish_rebuild.log
KEYS=$($PY -c "import regions; print(' '.join(k for k in regions.CANDIDATES if regions.kept(k) and (regions.data_dir(k) / 'segments_L50.parquet').exists()))")
BUILT=$(for k in $KEYS; do $PY -c "import regions; print(regions.data_dir('$k'))"; done)
say "FINISH: modes over $(echo $KEYS | wc -w) regions"
$PY -u t1_modes.py $BUILT >> $LOG 2>&1 || { say "FINISH: t1_modes FAILED"; exit 1; }
for k in $KEYS; do
  $PY -u t1_variants.py --region "$k" >> $LOG 2>&1 || { say "FINISH: t1_variants $k FAILED"; exit 1; }
done
for k in $KEYS; do
  $PY t1_finalize.py --region "$k" >> $LOG 2>&1 || { say "FINISH: t1_finalize $k FAILED"; exit 1; }
done
$PY t1_summary.py >> $LOG 2>&1 || { say "FINISH: t1_summary FAILED"; exit 1; }
say "FINISH DONE: modes, variants, data cards, summary"
