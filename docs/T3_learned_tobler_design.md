# T3, weeks 10–11: Tobler with learned constants (design)

*Drafted by Claude (22 Oct 2026) for Brian, following the semester plan §9
("let Tobler's constants vary") and Gate 2. A proposal to discuss with
Danni and Tianyi on 23 Oct, not a contract.*

## Why

The plan's main modeling idea is still open. So far we have:

- boosted trees and additive models on top of a refitted slope curve (the
  four arms; Table I);
- Eq. (1), Tobler's form with **one** input (steppiness): +1.0%.

The plan suggests keeping Tobler's form and letting its constants depend on
the covariates:

    v = v0(x) · exp(−k(x) · |s + s0(x)|)

with peak speed `v0`, slope sensitivity `k` and peak offset `s0` predicted
from terrain, vegetation and tags. The point is less accuracy than what
comes out: a sentence like "Tobler's k = 3.5 is closer to 2.8 on smooth
trail and 4.6 on steppy trail" is a result the field can use. It also
answers **Gate 2's last box**: does our model beat plain boosted trees on
the same features?

## The model

In log speed, with the rounded, two-sided top our data needs (Fig. 2a):

    ln v = a(x) − k±(x) · (sqrt((s + s0(x))² + e²) − e)

- `a = ln v0`; `k+` above the peak and `k−` below it; `e` rounds the top.
- A small neural network takes the covariates `x` and outputs `a`, `k+`,
  `k−`, `s0` (and `e`, or keep `e` shared). Positive outputs (`k`, `e`) go
  through softplus.
- **Variance head** (the plan's "heteroscedastic head"): the same network
  also outputs `ln σ(x, s)`. The likelihood is a Student-t in log speed,
  which tolerates GPS glitches and missed stops better than a Gaussian
  (plan §9, "output distribution").
- **Start from the reference:** initialise the output layer so every
  segment starts at the pooled slope-curve fit (t1_findings smooth_asym).
  Training then only learns departures from it, which keeps the model
  stable and interpretable.

Inputs, in order of priority:

1. terrain from elevation (5 m + 1 m: pitch SD and maximum, relief, side
   slope, roughness): the signal that transfers;
2. OSM tags (one-hot, with "missing" as a level);
3. lidar vegetation (15 regions) and AlphaEarth embeddings: later, as
   ablations.

## Evaluation, comparable with Table I

- **Same folds as the harness** (`t3_harness.py`, same seed): new hikes
  (`outing5`), new hikers (`hiker5`), new 10 km squares (`block5`), unseen
  regions (`loro`), and unseen regions + hikers (`loro_hiker`). Claude
  exports the fold labels so the comparison is exact.
- Early stopping on the harness's "stop" outings; nothing tuned on test
  folds.
- **Scores:** CRPS of ln v (closed form for the Student-t, checked against
  the harness's sample formula), skill vs the slope curve as in Table I;
  NLL; coverage of 50% and 90% intervals; PIT histogram.
- **Baselines:** the slope curve, Eq. (1), boosted trees on the same
  features (Table I: +2.8% in unseen regions for terrain).
- **What we report either way:** if the learned-constants model ties or
  beats the trees, it's the paper's model. If it loses, we report the gap
  honestly and keep it for what it explains: maps of `k(x)` and `v0(x)`
  against steppiness and understory.

## Who does what

| Brian | Claude |
|---|---|
| Writes the PyTorch model, loss and training loop | Exports a de-identified modeling table (covariates + fold labels) to `travel-speed-gate1/cache/exercise/` |
| Runs it on one split first (new hikes), then all | Writes and tests the CRPS / NLL functions against the harness |
| Makes the plots of `k(x)`, `v0(x)` | Reviews the code, runs any long jobs, writes up Gate 2 |

Compute: a CPU is plenty (290k rows, a network with a few thousand
weights); the Mac works. **PyTorch 2.14.1 is installed** in `.venv` (22 Oct,
at Brian's request; a 127 MB wheel from the Python package index), and the
Mac's GPU (MPS) works too. A test fit recovered Tobler's constants (6.01
km/h, k = 3.51) from synthetic data.

## Schedule (plan weeks)

| Week | Dates | Goal |
|---|---|---|
| 10 | 26 Oct – 1 Nov | Model + training loop on new hikes; sanity checks (starts at the slope curve? learns a sensible `k`?) |
| 11 | 2 – 8 Nov | All five splits; compare with the trees; **Gate 2** write-up for the 6 Nov meeting |
| 12 | 9 – 15 Nov | If time: the NAIP imagery arm (frozen pretrained encoder + small head, plan §9), feeding the same model |

The paper's numbers stay frozen on the current dataset (decision #113); new
models add rows to Table I, they don't change the existing ones.
