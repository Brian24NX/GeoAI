# What changed in the paper: October data (v1) → November data (v1.1)

*24 Nov 2026. Made by Claude for Brian. The draft (`main.tex`, `sections/*.tex`),
Table I and all figures now use the new numbers. Every number was recomputed
by `travel-speed-gate1/paper_numbers.py` and `make_paper_table.py`; both
scripts give back October's numbers when run on the October files, so the
method is checked.*

## In short

**The main result did not change.** Terrain still transfers to new regions:
**+2.1% / +2.8%** (additive / trees) in regions the model never saw, the
same as in October. Tags still transfer less well.

Why the numbers moved a little: we removed the Bay Area (16 regions now, not
17), fixed the download in four regions, and joined anonymous hikes that had
been cut into pieces.

## Five things that change what a sentence says

| # | Before | Now | What I changed in the draft |
|---|---|---|---|
| 1 | Terrain beats tags in **16 of 17** regions | **14 of 16** | Yosemite loses (it did before too). North Shore is now a tie (−0.02 points). The Bay Area, a win, is gone. Abstract, Intro, Results and Fig. 3 caption updated. |
| 2 | Hidden climbing alone is **over half** of the terrain gain (+1.2 / +1.6) | **about half** (+1.0 / +1.3) | Results: "carries about half of the gain". |
| 3 | Embeddings help **mainly where the model was trained** | They help **about half as much as terrain, everywhere** (+1.0 / +1.9 within regions, +1.3 / +1.2 in unseen ones, with wide intervals) | Abstract, Results and Conclusion reworded. |
| 4 | 30 m land cover **adds nothing** | Adds nothing within regions and **makes unseen regions worse** (−0.6 / −1.4) | One clause added in Results. |
| 5 | Mountain-hiking tag slower in **10 of 10** regions | **10 of 11** | Discussion: "nearly every region". |

## Every number that changed, by section

### Abstract and Introduction

| What | Before | Now |
|---|---|---|
| Walking segments | 290,640 | 284,711 |
| Regions | 17 | 16 |
| Outings | 1,992 | 1,861 |
| Tobler in unseen regions | 12.5% worse | 11.8% worse |
| Terrain beats tags | 16 of 17 | 14 of 16 |
| Tags add | 0.4–0.9% | 0.2–0.8% |
| Downhill faster than uphill | 8–23% | 8–24% |
| Eq. (1), one input, unseen regions | +1.0% | +0.7% |

### Data

| What | Before | Now |
|---|---|---|
| Hiking traces | 2,876 | 2,654 |
| Walking set | 290,640 segments, 14,532 km, 2,046 traces, 1,992 outings, 4,702 h | 284,711 segments, 14,236 km, 1,904 traces, 1,861 outings, 4,623 h |
| Regions with 1 m lidar under ≥83% of trail | 13 | 12 |
| Mode check | 327 traces; 93% of hikes called walking; 5% of walkers say bike/ski | 334 traces; 92%; 5.5% |
| Bay Area sentence ("uses the crawl only") | there | removed: "Every region combines all three" |
| Fig. 1 | 17 regions, orange dot | 16 regions, all blue; caption: 1,861 outings, 4,623 h; White Mountains inset 34,607 segments |
| Thinning to 30 s lowers speed | 11% | 11% (no change) |

### Methods

| What | Before | Now |
|---|---|---|
| Eq. (1) | k0 = 2.152, s0 = 0.043 | k0 = 2.156, s0 = 0.044 (a0, a1, k1 the same) |
| Leave one region out | 17 folds | 16 folds |
| Regions with lidar point clouds | 15 | 14 |

### Table I (unseen-region column; full table in `sections/results.tex`)

| Row | Before | Now |
|---|---|---|
| Tobler 1993 | −12.5 | −11.8 |
| Campbell 2022 | −0.5 | +0.1 |
| STRIDE 2024 (refitted) | −16.8 (+0.2) | −16.0 (+0.2) |
| OSM tags | +0.9 / +0.4 | +0.8 / +0.2 |
| 30 m vegetation | −0.1 / −0.8 | −0.6 / −1.4 |
| Embeddings | +1.1 / +1.1 | +1.3 / +1.2 |
| Lidar vegetation | +0.3 / +0.2 | +0.4 / +0.2 |
| **Terrain** | **+2.1 / +2.8** | **+2.1 / +2.8** (same) |
| Terrain + emb. + tags | +3.0 / +3.9 | +3.4 / +3.7 |
| Eq. (1) | +1.0 | +0.7 |
| Learned Tobler | +3.0 (+3.4) | +3.0 (+4.0) |

New-hikes column: tags +1.3 / +1.5 → +1.3 / +1.4; embeddings +1.4 / +2.6 →
+1.0 / +1.9; terrain +2.2 / +3.2 → +2.1 / +3.3; learned Tobler +3.2 (+3.8) →
+3.2 (+4.0).

### Results text

| What | Before | Now |
|---|---|---|
| Tobler worse in | all 17 regions | all 16 |
| Campbell by region | −3.8% (White Mtns) to +5.8% (Shenandoah) | −3.6% (Adirondacks) to +3.2% (Olympic) |
| 90% intervals cover | about 89% | 88–89% (North Shore lowest, 81%, same) |
| Out-and-back pairs | 2,763 from 1,145 outings | 2,688 from 1,084 |
| Tags in unseen regions | +0.9% [0.1, 1.7] / +0.4% [−1.1, 1.6]; "keeps two thirds" | +0.8% [0.0, 1.6] / +0.2% [−1.1, 1.3]; "keeps about 60%" |
| Terrain intervals | [1.5, 3.1] / [1.8, 4.1] | [1.3, 3.2] / [1.8, 4.2] |
| Terrain beats tags, trees | 14 of 17 | 13 of 16 |
| Local refit of the slope curve | +1.2% | +1.7% (terrain still beats it) |
| Terrain minus tags | +0.7 to +2.2 points | +0.6 to +2.4 (still above zero in every draw) |
| Terrain over region offsets / over own pace | ~1.9 / ~2.3 points | ~1.8 / ~2.0 |
| Lidar vegetation over terrain | at most +0.2 | at most +0.25 (trees lose 0.3 in unseen regions) |
| STRIDE published | −16.8% | −16.0% |
| Trained to 2019, tested 2020+ | terrain +2.2 / +2.9; tags +0.9 | terrain +2.1 / +2.9; tags +0.7 / +1.1 |
| Whole zone held out | terrain +1.9 / +2.7; tags +0.7 / −0.1 | terrain +1.8 / +2.5; tags +0.8 / −0.0 |
| West ↔ East | terrain +2.6 / +3.3; tags +1.5 / −0.3 | terrain +2.1 / +2.5; tags +0.8 / −0.4 |
| New hikers | +2.2 / +3.2 | +2.2 / +3.1 |
| Region + its hikers left out | 0.1–8.5% of training; terrain +1.8 / +2.4; tags +0.5 / −0.4 | 0.1–8.8%; terrain +1.9 / +2.5; tags +0.4 / +0.2 |
| Whole hikes | 1,354 hikes; 13.6% → 13.0% (terrain), 10.0% (own pace), 9.6% (both) | 1,288 hikes; 13.5% → 13.1%, 9.9%, 9.3% |

No change: peak speed ~4.2 km/h; Tobler ~20% too fast on gentle trail; GPS
rate +1.7 to +2.4%; terrain + tags +2.6 / +3.0.

### Discussion

| What | Before | Now |
|---|---|---|
| Mountain-hiking tag | −5%, 10 of 10 regions | −6%, 10 of 11 |
| Tags in trees, within → unseen | +1.5% → +0.4% | +1.4% → +0.2% |
| Terrain same sign | all 17 regions (−12%) | all 16 (−12%) |
| Terrain gain by slope | descents and level +2.3 to +2.8%; steep climbs +0.8% (trees +2.6%) | +2.4 to +2.6%; steep climbs +0.9% (trees +3.3%) |
| Trail map: formula fitted on | the other 16 regions | the other 15 |
| Eq. (1) between East and West | −0.3% | −0.4% |
| Hot days | −3% | −3.5% |
| Weather in new regions | −0.0% | −0.2% |
| Conclusion | 17 regions | 16 |

No change: 3,369 km of White Mountains trail, 77% unwalked; sac_scale on
1–96% of trail; snow −4%; Copernicus slope curve 4.9% worse.

## Also fixed

- A sentence in Results started "point clouds adds…" because its first
  words sat on a comment line. It now reads "Vegetation from the lidar
  point clouds adds…".
- Your TODO note on coarser elevation (Results): 10 m +2.1 / +2.6 →
  +2.0 / +2.6; 30 m +1.8 / +2.2 → +1.7 / +2.1; still above tags. Copernicus
  still loses to tags.
- Sizes: still 4 pages of text; references run onto page 5 (allowed).

## Learned Tobler (Gate 2) on the new data

| Test | Trees | Learned (a) | Learned (b), own spread | (b) − trees [95%] |
|---|---|---|---|---|
| New hikes | +3.26 | +3.23 | +4.01 | +0.75 [0.22, 1.24] |
| New hikers | +3.07 | +3.11 | +3.13 | +0.05 [−0.25, 0.37] |
| New 10 km squares | +2.81 | +3.00 | +3.64 | +0.83 [0.56, 1.09] |
| Unseen regions | +2.81 | +2.96 | +3.98 | +1.17 [0.63, 1.83] |
| Unseen regions and hikers | +2.46 | +2.75 | +3.06 | +0.60 [0.19, 1.02] |

Same story as October: scored the trees' way, it ties them. With its own
spread it beats them, now in four of five tests (October: three). Its 90%
ranges hold 89.4–90.0% of segments.
