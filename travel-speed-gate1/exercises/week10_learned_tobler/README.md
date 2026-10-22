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
