# Robustness checks (`t3_robust_summary.py`)

CRPS skill (%) vs the refitted slope curve, 95% intervals (outings resampled for outing and time splits, regions for unseen regions).

Reproduces the terrain15m run: max |CRPS difference| = 1.1e-16 over 195 rows.

## Newer hikes: trained up to 2019, tested on 2020+

Test: 81,145 segments after 2019 (outings with a doubtful date left out).

| Model | New hikers, random | **Hikes after 2019** |
|---|---|---|
| Tobler 1993 | -12.8 [-14.7, -11.1] | -13.2 [-14.9, -11.3] |
| Campbell 2022 | -0.9 [-1.5, -0.2] | -0.7 [-1.1, -0.2] |
| STRIDE 2024 | -17.2 [-19.1, -15.2] | -17.9 [-20.6, -15.1] |
| OSM tags, additive | +1.3 [0.8, 1.9] | +0.9 [0.1, 1.6] |
| OSM tags, trees | +1.5 [0.8, 2.3] | +0.9 [-0.3, 2.0] |
| Terrain, additive | +2.2 [1.8, 2.6] | +2.2 [1.7, 2.8] |
| Terrain, trees | +3.2 [2.8, 3.7] | +2.9 [2.3, 3.5] |
| Terrain + tags, additive | +3.1 [2.4, 3.7] | +2.9 [2.1, 3.7] |
| Terrain + tags, trees | +4.3 [3.5, 5.1] | +3.4 [2.3, 4.5] |
| Terrain formula (5 numbers) | +1.0 [0.6, 1.3] | +1.5 [1.1, 1.9] |

`lin_rs - lin_tags` after 2019: [0.5, 2.2], 100% of draws above 0.

`gbm_rs - gbm_tags` after 2019: [1.0, 3.2], 100% of draws above 0.

`lin_both - lin_tags` after 2019: [1.6, 2.4], 100% of draws above 0.

`gbm_both - gbm_tags` after 2019: [1.8, 3.3], 100% of draws above 0.

## GPS recording rate: unseen regions, by trace interval

| Model | All | <= 2 s (54,187 segments) | 2-10 s (156,490 segments) | > 10 s (79,002 segments) |
|---|---|---|---|---|
| Tobler 1993 | -12.5 [-15.2, -10.5] | -9.7 [-13.3, -6.7] | -11.4 [-13.8, -8.3] | -16.5 [-22.7, -12.9] |
| Campbell 2022 | -0.5 [-1.8, 0.7] | +1.1 [0.1, 2.0] | -0.1 [-1.6, 1.4] | -2.4 [-3.9, -1.1] |
| STRIDE 2024 | -16.8 [-21.9, -10.5] | -12.9 [-17.3, -7.9] | -16.6 [-21.1, -9.6] | -19.8 [-29.6, -9.6] |
| OSM tags, additive | +0.9 [0.1, 1.7] | +0.7 [-0.4, 2.3] | +1.0 [0.3, 2.1] | +0.7 [-2.5, 2.5] |
| OSM tags, trees | +0.4 [-1.1, 1.6] | -0.2 [-1.4, 1.3] | +1.1 [-0.2, 2.4] | -0.3 [-4.6, 2.1] |
| Terrain, additive | +2.1 [1.5, 3.1] | +1.7 [0.7, 3.0] | +2.4 [1.7, 3.5] | +1.9 [0.5, 3.2] |
| Terrain, trees | +2.8 [1.8, 4.1] | +2.5 [1.2, 4.1] | +2.9 [1.9, 4.4] | +2.8 [1.1, 4.5] |
| Terrain + tags, additive | +2.6 [1.7, 3.9] | +2.0 [0.3, 4.3] | +3.0 [2.1, 4.6] | +2.3 [-1.4, 4.5] |
| Terrain + tags, trees | +3.0 [1.6, 4.5] | +2.3 [0.6, 4.4] | +3.6 [2.7, 5.2] | +2.4 [-2.7, 5.3] |
| Terrain formula (5 numbers) | +1.0 [0.6, 1.5] | +1.3 [0.5, 2.4] | +0.9 [0.5, 1.6] | +0.8 [-0.3, 1.7] |

- <= 2 s: terrain minus tags (additive) [0.3, 1.8], 99% of draws above 0.
- 2-10 s: terrain minus tags (additive) [0.7, 2.2], 100% of draws above 0.
- > 10 s: terrain minus tags (additive) [-0.4, 3.6], 91% of draws above 0.

Unseen regions by interval: coverage of 90% ranges, bias (log speed), median whole-hike error:

| Model | Interval | 90% coverage | Bias | Hike error |
|---|---|---|---|---|
| Slope curve | <= 2 s | 0.882 | +0.062 | 14.7% |
| Slope curve | 2-10 s | 0.899 | -0.002 | 13.6% |
| Slope curve | > 10 s | 0.891 | -0.102 | 13.4% |
| Terrain, additive | <= 2 s | 0.878 | +0.084 | 14.3% |
| Terrain, additive | 2-10 s | 0.897 | +0.023 | 12.7% |
| Terrain, additive | > 10 s | 0.891 | -0.081 | 12.7% |
