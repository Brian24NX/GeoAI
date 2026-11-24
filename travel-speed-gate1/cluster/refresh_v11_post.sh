#!/bin/bash
#SBATCH -J v11_post
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH -t 0-06:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_v11_post_%j.log
# T1 v1.1 refresh, part 4 (24 Nov 2026): after all 32 harness runs (23 Nov),
# the summaries and analyses the paper quotes, on the 16-region data. No
# downloads. make_explainer_data.py last: it reads the others.
# (robust_summary ran in job 397407; t3_coarse_summary.py runs on the laptop)
source /engrfs/project/jacobsn/zhou.n/travel-speed/cluster/v11_common.sh
# a failed side analysis is logged and the job goes on
soft() { ( step "$@" ) || true; }
step export_table    $PY -u -W ignore t3_export_table.py
step paper_data      $PY -u -W ignore make_paper_data.py
soft tag_transfer    $PY -u -W ignore t3_tag_transfer.py
soft sampling_check  $PY -u -W ignore t1_sampling_check.py
soft mode_curves     $PY -u -W ignore t4_mode_curves.py
soft trail_map       $PY -u -W ignore t4_trail_map.py --region wm
soft lidarveg_eff    $PY -u -W ignore t2_lidarveg_effects.py --region wm
step explainer_data  $PY -u -W ignore make_explainer_data.py
say "V11 POST DONE"
