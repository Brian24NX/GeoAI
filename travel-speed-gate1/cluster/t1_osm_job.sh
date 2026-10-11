#!/bin/bash
#SBATCH -J t1_osm
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 1
#SBATCH --mem 8G
#SBATCH -t 7-00:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_osm_%j.log
# The OSM download queue on the cluster (one region at a time; polite to the
# volunteer-run OSM API). Each finished region submits its own build jobs.
cd /engrfs/project/jacobsn/zhou.n/travel-speed
PY=/engrfs/project/jacobsn/zhou.n/envs/t1/bin/python
$PY -u t1_queue.py --what osm --submit-builds cascades frontrange adk catskills yosemite olympic tahoe greenmtn smokies shenandoah pisgah
$PY -u t1_queue.py --what osm --submit-builds --probe --max-pages 9000 northshore sangabriel gorge wasatch bayarea
