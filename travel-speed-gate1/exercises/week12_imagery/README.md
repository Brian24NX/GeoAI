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

## Checkpoints

Filled in after Claude's runs: see "Results" below.
