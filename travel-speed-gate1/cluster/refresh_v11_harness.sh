#!/bin/bash
#SBATCH -J v11_harness
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 48G
#SBATCH -t 8:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_v11_harness_%A_%a.log
# T1 v1.1 refresh, part 3 (19 Nov 2026): one harness run per array task.
#   sbatch --array=0-24%3 cluster/refresh_v11_harness.sh base terrain5m ...
set -u
cd /engrfs/project/jacobsn/zhou.n/travel-speed
RUNS=("$@")
R=${RUNS[$SLURM_ARRAY_TASK_ID]}
say() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" | tee -a logs/refresh.log; }
say "start harness $R"
if bash cluster/refresh_harness.sh "$R" >> "logs/refresh_harness_$R.log" 2>&1; then
  say "done  harness $R"; else say "FAILED harness $R"; exit 1; fi
