#!/bin/bash
#SBATCH -J t1_chain
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 1
#SBATCH --mem 1G
#SBATCH -t 00:10:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_chain_%j.log
# Decision #135-136 (12 Nov 2026): after the re-download job ends, submit
# cluster/finish_rebuild_job.sh to run once the LAST region's new build has
# succeeded. The build job id comes from this run's "SUBMIT <key>" line in
# logs/t1_queue.log (not from an old marker file). Submit it with
#   sbatch --dependency=afterany:<re-download job> cluster/chain_finish_job.sh [key]
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
KEY=${1:-cascades}
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/t1_queue.log; }
# this run: the lines after the last "REDOWNLOAD <key>: start"
RUN=$(awk -v k="REDOWNLOAD $KEY: start" 'index($0, k) {buf=""} {buf = buf $0 "\n"} END {printf "%s", buf}' logs/t1_queue.log)
if ! echo "$RUN" | grep -q "REDOWNLOAD $KEY: exit 0, T1 DOWNLOAD DONE"; then
  say "CHAIN: $KEY did not finish its download; finish step NOT submitted"
  exit 1
fi
BUILD=$(echo "$RUN" | sed -n "s/.*SUBMIT $KEY: elevation job [0-9]*, build job \([0-9]*\).*/\1/p" | tail -1)
if [ -z "$BUILD" ]; then
  say "CHAIN: no build job found for $KEY; finish step NOT submitted"
  exit 1
fi
OUT=$(sbatch --parsable --dependency=afterok:$BUILD,singleton cluster/finish_rebuild_job.sh 2>&1 | grep -E '^[0-9]+' | head -1)
say "CHAIN: finish step submitted as job ${OUT:-?} (after build job $BUILD of $KEY)"
