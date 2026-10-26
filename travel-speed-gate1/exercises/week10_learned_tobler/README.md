# Weeks 10–11 exercise: Tobler with learned constants (T3)

*Set up by Claude (22 Oct 2026). The design and the reasons are in
`docs/T3_learned_tobler_design.md`. You build the model; Claude has prepared
the data, the folds, the baseline and the scoring, and will review and run
anything long.*

## The goal

Tobler's form, with its constants learned from the terrain:

    ln v = a(x) − k±(x) · (sqrt((s + s0(x))² + e²) − e)

`x` = a segment's terrain covariates. The rounded top (`e`) and separate
uphill / downhill slopes (`k+`, `k−`) are what our data needs (Fig. 2a).
A variance head `σ(x)` gives each segment its own spread. Question for
Gate 2: does this beat boosted trees on the same terrain features? And what
do the learned `k(x)` and `v0(x)` say? Compare with the harness run that
uses the same corrected covariates (`results/t3_harness_terrain15m_fixid/`,
decision #118): trees +3.22% new hikes, +2.83% new squares, +2.79% unseen
regions; additive +2.21%, +2.06%, +2.13% (Table I rounds these the same).

## What's ready

- `../../cache/exercise/t3_table.parquet`: the 289,679 scored walking
  segments, in the harness's order: `region`, `outing`, `hiker` (an integer
  per uploader), `slope`, `y` (ln km/h), tags, terrain and lidar vegetation
  covariates, and each split's fold. No user names, ids, coordinates or
  timestamps (not in git).
- `t3_inner.parquet`: which training outings fit / early-stop / calibrate
  each fold, exactly as the harness used them.
- `t3_columns.json`: which covariate came from where (`terrain5m`,
  `terrain1m`, `lidarveg`).
- `learned_tobler.py`: loads all that, walks through the folds, fits Table
  I's baseline (the refitted slope curve) per fold, scales the features.
- `../../t3_scoring.py`: the harness's CRPS, closed forms for a Normal or
  Student-t prediction, a torch loss; self-tested.

## Steps

0. Run the starter as it is. It prints each fold's sizes and reference
   curve and the reference's mean CRPS, which equals Table I's baseline for
   that split (checked 22 Oct: all five splits agree with the harness to
   ~1e-12, so the folds and the scoring are the harness's own).

   ```bash
   cd ~/Desktop/GeoAI/travel-speed-gate1/exercises/week10_learned_tobler && ../../../.venv/bin/python learned_tobler.py --split outing5
   ```

1. **Model** (TODO 1): a small `torch.nn.Module` (e.g. 2 hidden layers of
   32) from the terrain features to `a, k+, k−, s0, log σ`. Start it at the
   reference: zero the last layer's weights, set its biases to the
   reference fit. Then it begins as the slope curve and only learns
   departures from it.
2. **Loss** (TODO 2): Student-t negative log-likelihood (`nu` = 5 at first)
   via `sc.nll_student_t_torch`.
3. **Training** (TODO 3): Adam on the `fit` rows; early stopping on `stop`.
   Never touch `test`.
4. **Scoring** (TODO 4): the harness way (comparable with Table I) and with
   your own `σ`.

Start with `--split outing5` (new hikes). Week 11: all five splits,
`hiker5`, `block5`, `loro`, `loro_hiker`, then the Gate 2 summary.

## Sanity checks before trusting a number

- At step 0 of training (before any update) your model's CRPS equals the
  reference's: skill 0.0%.
- The learned `k+` should land near 2–3 and `k−` near 2–2.5 on average
  (the reference fit), not 3.5.
- The skill on `stop` and on `test` should be similar; if test is much
  worse, it's overfitting.

## Plots to bring (week 11)

`k+(x)` and `v0(x) = exp(a(x))` against steppiness (`pitch_sd_5m`): the
plan's "Tobler's k = 3.5 is closer to … on smooth trail and … on steppy
trail".

## Week 11: the runs for Gate 2 (prepared by Claude, 26 Oct)

Week 10 ended with TODOs 1–4 done on `outing5` (decision #120). Week 11
runs the same model on all five splits with three seeds, next to the
harness's boosted trees on the same features, and puts paired intervals on
the difference.

```bash
cd ~/Desktop/GeoAI/travel-speed-gate1/exercises/week10_learned_tobler && ../../../.venv/bin/python run_all.py
```

- `run_all.py`: for every split (`outing5`, `hiker5`, `block5`, `loro`,
  `loro_hiker`) and seed (0, 1, 2), trains `learned_tobler.py`'s model and
  scores it both ways; refits the harness's `gbm_rs` trees (slope + the
  same 12 terrain covariates, same folds and settings; scikit-learn 1.9.1,
  as on the cluster). One row per scored segment goes to
  `../../cache/t3_learned/<split>.parquet` (not in git), with the learned
  constants averaged over the seeds for the plots. About 40 s per split
  for one seed on the laptop; all five splits with three seeds, roughly
  10–15 minutes (the two region splits have 17 folds each).
- `gate2_summary.py`: per split, the skills of the trees and of the learned
  model (a) and (b), 95% bootstrap intervals that resample the split's
  units like the harness (outings; uploaders for `hiker5`; regions for the
  region splits), the paired differences (learned − trees) with the share
  of draws above zero, and the share of test segments inside the model's
  own 90% range. Writes `../../results/t3_learned_tobler/gate2_summary.csv`.

Smoke test on `outing5`, seed 0 (26 Oct): the reproduced trees give
+3.22% [2.79, 3.67], exactly the harness's value; the learned model +3.12%
(a) and +3.67% (b); (a) − trees −0.11 [−0.30, +0.05], (b) − trees +0.45
[+0.04, +0.86]; its own 90% range holds 89.8% of the test segments.

**Gate 2's five boxes** (plan §6) and where the answers come from:

| Box | Source |
|---|---|
| Every learned arm beats Tobler on held-out traces | Table I (harness): Tobler −12.5% |
| The tags arm beats slope-only | Table I: tags +1.3% / +1.5% (new hikes) |
| Remote sensing reported against tags, gap quantified | Table I and decision #116 |
| Predicted variances calibrated, not just the means | `gate2_summary.csv`: own 90% range |
| Your model beats plain boosted trees on the same features | `gate2_summary.csv`: (a) − trees, (b) − trees |

**Yours (Brian), week 11:** the plots of `k_up(x)` and `v0(x) = exp(a(x))`
against steppiness (`pitch_sd_5m`), from the seed-averaged constants in
`cache/t3_learned/<split>.parquet` (join on `row` to `t3_table.parquet`),
and the Gate 2 write-up for 6 Nov.
