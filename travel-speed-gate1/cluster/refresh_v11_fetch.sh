#!/bin/bash
#SBATCH -J v11_fetch
#SBATCH -A engr-class-any
#SBATCH -p linuxlab-project
#SBATCH -c 8
#SBATCH --mem 32G
#SBATCH -t 1-00:00:00
#SBATCH -o /engrfs/project/jacobsn/zhou.n/travel-speed/logs/slurm_v11_fetch_%j.log
# T1 v1.1 refresh, part 2a (19 Nov 2026): 1 m DEM cells for new trail
# (162 cells, ~0.16 GB), 1 m terrain, satellite embeddings (October's reused
# where the segment midpoint is unchanged; ~33k fetched), weather (Daymet,
# cached per outing), the terrain curve and effects. Lidar: refresh_v11_lidar.sh.
source /engrfs/project/jacobsn/zhou.n/travel-speed/cluster/v11_common.sh
KEYS=$($PY -c "import regions; print(' '.join(k for k in regions.CANDIDATES if regions.kept(k)))")
step dem1m          $PY -u -W ignore t2_dem1m.py --all
guard
step terrain1m      $PY -u -W ignore t2_terrain1m.py --all
step embeddings     $PY -u -W ignore t2_embed.py --year 2022 --region $KEYS --reuse "$ARCH"
step weather        $PY -u -W ignore t2_weather.py
step terrain_curve  $PY -u -W ignore t4_terrain_curve.py
step terrain_eff    $PY -u -W ignore t2_terrain_effects.py
say "V11 FETCH DONE"
