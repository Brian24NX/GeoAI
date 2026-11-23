#!/bin/bash
#SBATCH -J v11_fetch2
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH -t 1-00:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_v11_fetch2_%j.log
# T1 v1.1 refresh, part 2a resumed (23 Nov 2026): the 19 Nov run (job 389906)
# did the 1 m DEM and terrain1m, then the embeddings failed on a short HTTP
# read. t2_embed.py now retries; regions are those in data/t1_all only.
source /engrfs/project/jacobsn/zhou.n/travel-speed/cluster/v11_common.sh
KEYS=$($PY -c "import pandas as pd, regions; b = set(pd.read_parquet('data/t1_all/segments_L50.parquet', columns=['region']).region); print(' '.join(k for k in regions.CANDIDATES if k in b))")
say "fetch2 regions: $KEYS"
step embeddings     $PY -u -W ignore t2_embed.py --year 2022 --region $KEYS --reuse "$ARCH" --skip-done
step weather        $PY -u -W ignore t2_weather.py
step terrain_curve  $PY -u -W ignore t4_terrain_curve.py
step terrain_eff    $PY -u -W ignore t2_terrain_effects.py
say "V11 FETCH DONE"
