# Week 12 exercise: does aerial imagery help? (Track A)

*Set up by Claude (6 Nov 2026). The plan and its reasons are in
`docs/T3_naip_imagery_design.md`; the go is decision #124 (Brian's call,
5 Nov). Claude prepared the data, ran the trees and will review; you add
imagery to learned Tobler.*

## The question in one line

Terrain is the only input that has helped in regions the model never saw.
Do aerial photos of the trail add anything on top of terrain there?

## What the imagery is

- **NAIP** is aerial photography of the US at 0.6 m pixels: you can see
  single trees, rocks and often the trail.
- **Clay v1.5**, an open image model, has already turned every 155 m × 155 m
  square of NAIP into **1,024 numbers** (an *embedding*, like a CNN's
  feature vector). We downloaded them for the 754 squares under our trails.
- Each walking segment gets the embedding of the square under its midpoint.
  That covers **15 regions**: Olympic is left out (Clay only has 2017 photos
  at 1 m there) and the North Shore is in Canada (no NAIP).
- 1,024 numbers is too many for about 2,000 hikes, so each fold shrinks
  them to **16 with PCA**, fitted on that fold's training rows only.

## What's ready

- `../../cache/exercise/t3_naip_clay.npy`: the embeddings, one row per row
  of `t3_table.parquet` (float16; NaN for Olympic and the North Shore). Not
  in git: 0.6 GB.
- `track_a_trees.py` (Claude, run on 6 Nov): the Gate 2 trees on the 15
  regions in three versions (terrain, imagery only, terrain + imagery) for
  all five test setups. Results: `../../results/t3_imagery/track_a_trees_summary.csv`.
- `learned_tobler_imagery.py`: **yours**, four TODOs.

## Your TODOs (`learned_tobler_imagery.py`)

1. **Which rows the PCA may learn from.** The same training rows as every
   other step of the fold. Never the held-out region, or the test leaks in.
2. **The two input lists:** terrain alone, then terrain + the 16 imagery
   columns.
3. **Skill and the gain, with its interval:** the gain of terrain + imagery
   over terrain, and a 95% interval from resampling the 15 regions.
4. **One sentence:** does imagery help learned Tobler in regions it never
   saw?

Run it (a few minutes):

    cd ~/Desktop/GeoAI/travel-speed-gate1/exercises/week12_imagery
    ../../../.venv/bin/python learned_tobler_imagery.py

## The success rule (set before looking)

In the unseen-region tests (`loro`, `loro_hiker`), terrain + imagery must
beat terrain alone, with the 95% interval above zero, for learned Tobler or
the trees. Otherwise imagery gets one sentence in the paper, like the
satellite embeddings.

## Results (Claude's runs, 6 Nov)

The trees (`track_a_trees.py`). Skill is the % improvement over the
slope-only curve on the 15 regions; the gain's range is a 95% bootstrap
over the setup's units.

| Test | Terrain | Imagery only | Terrain + imagery | Gain [95% range] |
|---|---|---|---|---|
| New hikes (`outing5`) | 2.73 | 1.90 | 3.76 | +1.03 [+0.35, +1.71] |
| New hikers (`hiker5`) | 2.69 | 1.47 | 3.23 | +0.55 [−0.38, +1.42] |
| New 10 km squares (`block5`) | 2.51 | 1.26 | 3.16 | +0.65 [+0.13, +1.18] |
| Unseen regions (`loro`) | 2.61 | 0.56 | 2.80 | +0.19 [−0.77, +1.19] |
| Unseen regions + hikers (`loro_hiker`) | 2.08 | 0.84 | 2.45 | +0.37 [−0.79, +1.22] |

**Checkpoint for your TODO 3.** Claude's filled-in copy, with seed 0 and
the same draws: terrain +3.37%, both +3.81%, gain **+0.44 [−0.67, +1.20]**.
- Biggest gains: Adirondacks +4.1, Green Mountains +4.0, San Gabriels +1.5.
- Biggest losses: Wasatch −3.6, Tahoe −3.3, Catskills −1.3.

**What it means.** Imagery helps inside regions the model knows: new hikes
and new squares, with ranges above zero. It does not help reliably in
regions it never saw, where every range crosses zero. That is the same
pattern as the satellite embeddings (decision #93). By the success rule,
Track A does not pass. Whether to try Track B (photos centred on the trail)
is Brian's call (decision #125).

## Track B results (6 Nov; `track_a_trees.py --emb satlas`)

Track B uses 96 m NAIP photos centred on each trail spot, run through the
frozen Satlas aerial model, on 16 regions.

| Test | Terrain | Imagery only | Terrain + imagery | Gain [95% range] |
|---|---|---|---|---|
| New hikes | 3.20 | 1.74 | 4.21 | +1.01 [+0.57, +1.44] |
| New hikers | 3.10 | 1.26 | 3.62 | +0.52 [−0.08, +1.09] |
| New 10 km squares | 2.79 | 1.04 | 3.24 | +0.45 [+0.01, +0.85] |
| Unseen regions | 2.92 | 0.52 | 3.08 | +0.16 [−0.24, +0.57] |
| Unseen regions + hikers | 2.52 | 0.07 | 2.43 | −0.09 [−0.79, +0.46] |

**Checkpoint with `EMB = "satlas"`:** terrain +3.50%, both +3.50%,
gain **−0.01 [−0.52, +0.34]**.

**What it means.** Photos of the trail itself give the same answer as
Track A: they help inside regions the model knows, not in new ones. So
neither track passes, and only terrain carries over (decision #127).
