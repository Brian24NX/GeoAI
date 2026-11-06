#!/bin/bash
#SBATCH -J naip_clay
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 4
#SBATCH --mem 4G
#SBATCH -t 0-06:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_naip_clay_%j.log
# Track A of the imagery arm (decision #124): download Clay v1.5's NAIP
# embeddings for the 754 quarter quads under our walking segments (6.05 GB,
# approved by Brian on 5 Nov). Re-running resumes.
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
$PY -u t3_naip_clay_download.py
