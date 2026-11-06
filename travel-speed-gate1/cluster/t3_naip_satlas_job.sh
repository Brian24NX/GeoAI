#!/bin/bash
#SBATCH -J naip_satlas
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 16G
#SBATCH -t 0-12:00:00
#SBATCH --array=0-15
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_naip_satlas_%A_%a.log
# Track B of the imagery arm (decision #126): one task per US region; each
# trail spot's 96 m NAIP chip embedded with the frozen Satlas aerial Swin-B.
# A finished region is skipped, so resubmitting resumes.
REGIONS=(cascades wm olympic tahoe sangabriel frontrange adk yosemite gorge wasatch bayarea catskills smokies shenandoah greenmtn pisgah)
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
$PY -u t3_naip_satlas.py ${REGIONS[$SLURM_ARRAY_TASK_ID]}
