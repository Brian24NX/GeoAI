#!/bin/bash
#SBATCH --job-name=osm_lab_index
#SBATCH --partition=debug
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=/engrfs/project/jacobsn/zhou.n/logs/index_%j.log
cd /engrfs/project/jacobsn/zhou.n
venv/bin/python -u build_lab_index.py /engrfs/project/jacobsn/zhou.n/osm_lab_index
