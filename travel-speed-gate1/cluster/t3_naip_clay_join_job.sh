#!/bin/bash
#SBATCH -J naip_join
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 2
#SBATCH --mem 16G
#SBATCH -t 0-04:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_naip_join_%j.log
# Track A, step 2 (decision #124): each walking segment gets the Clay
# embedding of the NAIP chip under its midpoint. Submit after the download:
#   sbatch --dependency=afterok:<download job id> cluster/t3_naip_clay_join_job.sh
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
$PY -u t3_naip_clay_join.py
