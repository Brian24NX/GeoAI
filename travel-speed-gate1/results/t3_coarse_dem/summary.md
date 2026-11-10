# Terrain from coarser elevation (decision #131)

CRPS skill (%) vs each run's own slope curve. Additive / trees.

|                                          | paper (1 m + 5 m)    | 5 m                  | 10 m                 | 30 m                | 30 m terrain, 5 m slope   |
|:-----------------------------------------|:---------------------|:---------------------|:---------------------|:--------------------|:--------------------------|
| new hikes: terrain add.                  | +2.21                | +2.03                | +2.10                | +1.84               | +1.59                     |
| new hikes: terrain trees                 | +3.24                | +2.72                | +2.70                | +2.32               | +2.13                     |
| new 10 km: terrain add.                  | +2.06                | +1.93                | +1.99                | +1.73               | +1.48                     |
| new 10 km: terrain trees                 | +2.83                | +2.45                | +2.42                | +2.07               | +1.90                     |
| unseen: terrain add.                     | +2.13                | +2.05                | +2.12                | +1.77               | +1.52                     |
| unseen: terrain trees                    | +2.78                | +2.55                | +2.62                | +2.19               | +1.98                     |
| unseen CI lin_rs                         | [1.5, 3.1]           | [1.5, 2.9]           | [1.7, 2.7]           | [1.3, 2.2]          | [1.1, 1.9]                |
| unseen CI gbm_rs                         | [1.8, 4.1]           | [1.9, 3.4]           | [2.1, 3.4]           | [1.6, 2.9]          | [1.4, 2.7]                |
| unseen: tags add.                        | +0.87                | +0.87                | +0.88                | +0.94               | +0.87                     |
| unseen: tags trees                       | +0.43                | +0.43                | +0.42                | +0.57               | +0.43                     |
| terrain - tags (add.)                    | [0.7, 2.2], 100% > 0 | [0.6, 1.9], 100% > 0 | [0.7, 1.8], 100% > 0 | [0.1, 1.4], 98% > 0 | [0.0, 1.1], 98% > 0       |
| beats tags (add.)                        | 16 / 17              | 14 / 17              | 13 / 17              | 12 / 17             | 13 / 17                   |
| beats tags (trees)                       | 14 / 17              | 15 / 17              | 15 / 17              | 14 / 17             | 14 / 17                   |
| unseen: slope curve vs 5 m slope curve   | +0.00                | +0.00                | -0.53                | -1.01               | +0.00                     |
| unseen: terrain trees vs 5 m slope curve | +2.78                | +2.55                | +2.10                | +1.20               | +1.98                     |

## Aspect and curvature

|                  |   paper terrain |   + aspect, curvature |   difference |
|:-----------------|----------------:|----------------------:|-------------:|
| new hikes: add.  |            2.21 |                  2.41 |         0.19 |
| new hikes: trees |            3.24 |                  3.48 |         0.25 |
| new 10 km: add.  |            2.06 |                  2.25 |         0.19 |
| new 10 km: trees |            2.83 |                  2.95 |         0.12 |
| unseen: add.     |            2.13 |                  2.34 |         0.21 |
| unseen: trees    |            2.78 |                  2.94 |         0.16 |
