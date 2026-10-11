#!/bin/bash
#SBATCH --job-name=osm_lab_extract
#SBATCH --account=engr-class-any
#SBATCH --partition=debug
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=48G
#SBATCH --output=/engrfs/project/jacobsn/zhou.n/logs/extract_%j.log
cd /engrfs/project/jacobsn/zhou.n
venv/bin/python -u extract_lab_traces.py /engrfs/project/jacobsn/zhou.n/lab_extracts wm:-71.95,43.8,-70.95,44.5 adk:-74.25,43.95,-73.7,44.35 catskills:-74.6,41.9,-74.0,42.3 greenmtn:-73.0,44.15,-72.6,44.6 acadia:-68.45,44.22,-68.15,44.45 shenandoah:-78.7,38.2,-78.15,38.95 smokies:-84.0,35.45,-83.05,35.8 pisgah:-82.95,35.25,-82.4,35.75 frontrange:-105.75,39.55,-105.15,40.15 cosprings:-105.1,38.7,-104.8,38.95 wasatch:-111.85,40.45,-111.55,40.9 tetons:-110.95,43.6,-110.6,43.95 glacier:-114.1,48.5,-113.5,48.95 sedona:-111.9,34.75,-111.55,35.4 boise:-116.3,43.55,-116.0,43.75 cascades:-122.1,47.2,-120.6,47.9 gorge:-122.3,45.5,-121.4,45.75 olympic:-123.9,47.75,-123.1,48.1 bayarea:-122.65,37.3,-121.95,38.0 sangabriel:-118.3,34.15,-117.6,34.4 yosemite:-119.8,37.65,-119.3,37.95 tahoe:-120.25,38.85,-119.85,39.3 northshore:-123.3,49.3,-122.9,49.48
