# Week 9 exercise: the log-linear diagnostic (semester plan §9)

*Set up by Claude (21 Oct 2026). You write the analysis; about an hour.
Bring the plot and 3–4 sentences to the weekly meeting ("what I did, what
broke, one plot").*

## The idea

Tobler's hiking function is `v = 6 exp(-3.5 |s + 0.05|)` km/h. Take the log
of both sides:

    ln v = ln 6 - 3.5 |s + 0.05|

So in log space Tobler is a **straight line** in `x = |s + 0.05|`, with
slope −3.5, and the same line on both sides of the peak. That gives a test
of Tobler's *form*, before fitting any model: plot the median log speed
against `x`, separately for the uphill side (`s + 0.05 > 0`) and the
downhill side (`s + 0.05 < 0`).

- Straight, parallel lines with slope −3.5: Tobler's form is right.
- A bend near `x = 0`, or two different slopes: the form itself is wrong,
  which the plan calls "a more interesting finding than any accuracy
  improvement".

## The data

`../../cache/exercise/walking_segments.parquet` (7.8 MB, not in git). One
row per 50 m walking segment: 289,679 segments, 1,992 outings, 17 regions.
No user names or coordinates.

| Column | Meaning |
|---|---|
| `region` | region key (`wm` = White Mountains, ...) |
| `outing` | integer id of the outing (one hike, possibly several uploads) |
| `slope` | rise / run along the walking direction: +0.10 = 10% uphill |
| `speed_kmh` | moving speed over the segment (stops removed) |
| `length_m`, `moving_s` | what the speed was computed from |
| `native_interval_s` | the GPS recording interval of the trace |

## Steps

The starter script `loglinear_diagnostic.py` loads the data and makes
`lnv`, `x` and `side`. Fill in the four TODOs:

1. Bin `x` in 0.01 steps, per side; per bin, the count, the median of `lnv`
   and its 25th and 75th percentiles. Keep bins with at least 200 segments.
2. Plot the medians against `x` for both sides, a band for the 25th–75th
   percentiles, and Tobler's line `ln 6 - 3.5 x`.
3. Fit a straight line to the medians on each side for 0.05 ≤ x ≤ 0.40 and
   compare its slope and intercept (as km/h) with Tobler's −3.5 and 6 km/h.
4. Write 3–4 sentences: Is it straight? Where does it bend? Are the two
   sides the same? How does the peak compare with 6 km/h?

Run it with the project's Python:

```bash
cd ~/Desktop/GeoAI/travel-speed-gate1/exercises/week09_loglinear && ../../../.venv/bin/python loglinear_diagnostic.py
```

## Things to watch

- Use the natural log of speed, and medians, not means. Speeds have a
  long tail (GPS glitches, missed stops).
- `slope` is a fraction, not a percent and not degrees.
- Segments from one hike are not independent, so the 289,679 rows behave
  like far fewer data points. That matters for error bars (stretch 2).

## Stretch, if you have time

1. Do the same per region: do all 17 regions bend the same way?
2. Error bars that respect hikes: resample whole outings (bootstrap) and
   refit the two slopes 200 times.
3. Where is the real peak? Try offsets other than 0.05 in `x = |s + s0|`
   and see which makes the two sides line up best.

When you're done, compare with Fig. 2a of the paper draft
(`paper/main.pdf`), which shows the same data in km/h.
