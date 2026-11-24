# Robustness checks (`t3_robust_summary.py`)

CRPS skill (%) vs the refitted slope curve, 95% intervals (outings resampled for outing and time splits, regions for unseen regions).

Reproduces the terrain15m run: max |CRPS difference| = 0 over 587 rows.

## Newer hikes: trained up to 2019, tested on 2020+

Test: 78,828 segments after 2019 (outings with a doubtful date left out).

| Model | New hikers, random | **Hikes after 2019** |
|---|---|---|
| Tobler 1993 | -12.4 [-14.1, -10.9] | -14.3 [-16.6, -12.0] |
| Campbell 2022 | -0.6 [-1.1, -0.1] | -1.3 [-2.3, -0.4] |
| STRIDE 2024 | -16.5 [-18.9, -14.3] | -17.7 [-20.8, -14.8] |
| OSM tags, additive | +1.3 [0.8, 1.8] | +0.7 [0.2, 1.3] |
| OSM tags, trees | +1.4 [0.6, 2.2] | +1.1 [0.1, 2.2] |
| Terrain, additive | +2.1 [1.7, 2.5] | +2.1 [1.8, 2.5] |
| Terrain, trees | +3.3 [2.8, 3.7] | +2.9 [2.2, 3.6] |
| Terrain + tags, additive | +3.0 [2.3, 3.6] | +2.7 [2.0, 3.3] |
| Terrain + tags, trees | +4.1 [3.3, 4.9] | +3.7 [2.7, 4.9] |
| Terrain formula (5 numbers) | +1.1 [0.7, 1.4] | +1.6 [1.2, 2.1] |

`lin_rs - lin_tags` after 2019: [0.9, 2.0], 100% of draws above 0.

`gbm_rs - gbm_tags` after 2019: [0.7, 2.8], 100% of draws above 0.

`lin_both - lin_tags` after 2019: [1.6, 2.3], 100% of draws above 0.

`gbm_both - gbm_tags` after 2019: [2.0, 3.1], 100% of draws above 0.

## GPS recording rate: unseen regions, by trace interval

| Model | All | <= 2 s (52,226 segments) | 2-10 s (154,445 segments) | > 10 s (77,084 segments) |
|---|---|---|---|---|
| Tobler 1993 | -11.8 [-14.7, -9.8] | -9.2 [-13.3, -6.3] | -10.8 [-13.5, -8.1] | -15.3 [-20.2, -11.8] |
| Campbell 2022 | +0.1 [-0.9, 1.0] | +1.9 [-0.2, 3.7] | +0.2 [-1.0, 1.0] | -1.3 [-2.7, 0.2] |
| STRIDE 2024 | -16.0 [-21.0, -9.3] | -11.8 [-17.1, -6.0] | -16.1 [-20.7, -9.5] | -18.6 [-28.8, -7.2] |
| OSM tags, additive | +0.8 [-0.0, 1.6] | +0.6 [-0.1, 1.5] | +1.0 [0.4, 2.0] | +0.6 [-2.0, 2.1] |
| OSM tags, trees | +0.2 [-1.1, 1.3] | -0.2 [-1.6, 1.4] | +0.6 [-0.5, 2.2] | -0.3 [-3.4, 1.5] |
| Terrain, additive | +2.1 [1.3, 3.2] | +1.7 [0.7, 2.9] | +2.4 [1.7, 3.6] | +1.7 [0.2, 3.2] |
| Terrain, trees | +2.8 [1.8, 4.2] | +2.7 [1.3, 4.2] | +3.0 [2.0, 4.6] | +2.4 [0.6, 4.3] |
| Terrain + tags, additive | +2.6 [1.4, 3.9] | +2.1 [0.7, 3.6] | +3.0 [2.0, 4.7] | +2.0 [-1.1, 3.9] |
| Terrain + tags, trees | +3.0 [1.7, 4.5] | +2.4 [0.3, 4.5] | +3.4 [2.1, 5.4] | +2.5 [-0.9, 4.6] |
| Terrain formula (5 numbers) | +0.7 [0.2, 1.3] | +1.1 [0.1, 2.3] | +0.7 [0.3, 1.4] | +0.4 [-0.8, 1.4] |

- <= 2 s: terrain minus tags (additive) [0.2, 2.1], 99% of draws above 0.
- 2-10 s: terrain minus tags (additive) [0.7, 2.4], 100% of draws above 0.
- > 10 s: terrain minus tags (additive) [-0.3, 3.1], 94% of draws above 0.

Unseen regions by interval: coverage of 90% ranges, bias (log speed), median whole-hike error:

| Model | Interval | 90% coverage | Bias | Hike error |
|---|---|---|---|---|
| Slope curve | <= 2 s | 0.876 | +0.063 | 14.9% |
| Slope curve | 2-10 s | 0.893 | -0.001 | 13.3% |
| Slope curve | > 10 s | 0.889 | -0.100 | 13.5% |
| Terrain, additive | <= 2 s | 0.875 | +0.088 | 14.2% |
| Terrain, additive | 2-10 s | 0.892 | +0.025 | 12.7% |
| Terrain, additive | > 10 s | 0.888 | -0.078 | 12.7% |


## Slope in the walking direction: unseen regions

| Model | All | < -15% (42,224 segments) | -15 to -5% (60,032 segments) | -5 to 5% (81,146 segments) | 5 to 15% (58,621 segments) | >= 15% (41,732 segments) |
|---|---|---|---|---|---|---|
| Tobler 1993 | -11.8 [-14.7, -9.8] | -1.2 [-3.2, 0.3] | -23.5 [-29.9, -19.0] | -19.7 [-22.8, -16.7] | -0.1 [-1.1, 0.6] | -7.7 [-13.0, -0.6] |
| Campbell 2022 | +0.1 [-0.9, 1.0] | +1.3 [0.0, 3.0] | +1.1 [0.6, 2.0] | +0.5 [0.2, 1.0] | +0.1 [-1.5, 1.2] | -3.4 [-8.2, 0.7] |
| STRIDE 2024 | -16.0 [-21.0, -9.3] | -10.1 [-13.4, -5.3] | -19.4 [-26.0, -10.3] | -16.1 [-23.0, -9.7] | -19.1 [-26.6, -10.8] | -13.9 [-19.3, -8.2] |
| OSM tags, additive | +0.8 [-0.0, 1.6] | +0.2 [-0.8, 1.6] | +0.5 [-0.9, 1.6] | +1.2 [0.1, 1.9] | +1.1 [0.1, 1.8] | +0.8 [-0.2, 2.1] |
| OSM tags, trees | +0.2 [-1.1, 1.3] | -0.6 [-2.8, 1.8] | +0.1 [-1.7, 1.2] | +0.8 [-0.5, 2.0] | +0.3 [-1.5, 1.4] | +0.0 [-3.7, 3.3] |
| Terrain, additive | +2.1 [1.3, 3.2] | +2.6 [1.8, 3.6] | +2.4 [1.4, 3.9] | +2.5 [1.6, 3.8] | +1.7 [0.8, 3.0] | +0.9 [-0.3, 2.0] |
| Terrain, trees | +2.8 [1.8, 4.2] | +3.8 [2.1, 6.5] | +2.7 [1.6, 4.2] | +2.8 [1.8, 4.3] | +1.6 [0.7, 2.9] | +3.3 [1.0, 6.1] |
| Terrain + tags, additive | +2.6 [1.4, 3.9] | +2.2 [1.0, 4.1] | +2.6 [1.0, 4.4] | +3.6 [2.3, 5.0] | +2.6 [1.1, 3.8] | +1.1 [-0.1, 2.4] |
| Terrain + tags, trees | +3.0 [1.7, 4.5] | +3.5 [1.7, 6.5] | +2.6 [0.9, 4.6] | +3.2 [1.7, 5.2] | +2.1 [0.4, 3.4] | +3.4 [1.3, 6.7] |
| Terrain formula (5 numbers) | +0.7 [0.2, 1.3] | +0.4 [-0.5, 1.5] | +1.0 [0.2, 1.8] | +1.3 [0.4, 2.1] | +0.7 [-0.5, 2.5] | -0.4 [-2.5, 1.2] |

- < -15%: terrain minus tags (additive) [1.2, 3.5], 100% of draws above 0.
- -15 to -5%: terrain minus tags (additive) [0.7, 3.6], 100% of draws above 0.
- -5 to 5%: terrain minus tags (additive) [0.6, 2.5], 100% of draws above 0.
- 5 to 15%: terrain minus tags (additive) [-0.4, 2.0], 85% of draws above 0.
- >= 15%: terrain minus tags (additive) [-1.7, 1.1], 56% of draws above 0.