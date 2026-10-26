#!/usr/bin/env python3
"""
Week 10 (semester plan section 9, T3): Tobler with learned constants.
See README.md and docs/T3_learned_tobler_design.md.

Given here (Claude):  loading, the harness's exact folds, the reference
                      slope curve (Table I's baseline), feature scaling,
                      scoring.
Yours (Brian):        the model, the loss, the training loop (TODOs below).

Data: ../../cache/exercise/t3_table.parquet, t3_inner.parquet,
      t3_columns.json (made on the cluster by t3_export_table.py)
Run:  ../../../.venv/bin/python learned_tobler.py --split outing5
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                       # travel-speed-gate1
sys.path.insert(0, str(ROOT))
import t1_findings as tf  # noqa: E402  the reference curve's form and fit
import t3_scoring as sc   # noqa: E402  the harness's CRPS, closed forms

DATA = ROOT / "cache" / "exercise"
CURVE = tf.FORMS["smooth_asym"][0]   # ln v = a - k(+/-) (sqrt((s+s0)^2+e^2) - e)
# parameter order of CURVE's p: (a, k_up, k_down, s0, e)


def load():
    t = pd.read_parquet(DATA / "t3_table.parquet")
    inner = pd.read_parquet(DATA / "t3_inner.parquet")
    cols = json.loads((DATA / "t3_columns.json").read_text())
    return t, inner, cols


def folds(t, inner, split):
    """Yield (fold, fit, stop, cal, test) row indices for one split, exactly
    as t3_harness.py used them: test = the fold's segments; fit / stop / cal
    = training segments whose outing has that role in this fold. For
    loro_hiker, training also drops every segment of a hiker who walked in
    the held-out region (a group outing can lose one hiker and keep
    another)."""
    lab = t[f"fold_{split}"].astype(str).to_numpy()
    for f in pd.unique(lab):
        roles = inner[(inner.split == split) & (inner.fold == f)]
        role = t.outing.map(roles.set_index("outing").role).to_numpy()
        train = lab != f
        if split == "loro_hiker":
            train &= ~t.hiker.isin(t.hiker[lab == f]).to_numpy()
        yield (f,
               np.flatnonzero(train & (role == "fit")),
               np.flatnonzero(train & (role == "stop")),
               np.flatnonzero(train & (role == "cal")),
               np.flatnonzero(lab == f))


def reference(s, y, fit, stop, cal, test):
    """t3_harness's slope_curve arm: the curve fitted on fit + stop, its
    spread from the cal residuals. Returns the curve's parameters and the
    test segments' CRPS (the denominator of every skill in Table I)."""
    both = np.r_[fit, stop]
    p = tf.fit_form("smooth_asym", s[both], y[both])
    r = sc.residual_quantiles(y[cal] - CURVE(p, s[cal]))
    return p, sc.crps_quantiles(CURVE(p, s[test]), r, y[test])


def features(t, columns, train):
    """Numeric covariates scaled with the training rows' mean and SD;
    missing values -> 0 (the training mean) plus a 0/1 'missing' column for
    each covariate that has gaps. Returns a float32 array, one row per
    segment."""
    x = t[columns].to_numpy(float)
    miss = np.isnan(x)
    mu, sd = np.nanmean(x[train], 0), np.nanstd(x[train], 0)
    sd[~(sd > 0)] = 1.0
    z = np.where(miss, 0.0, (x - mu) / sd)
    gaps = miss[train].any(0)
    return np.hstack([z, miss[:, gaps].astype(float)]).astype(np.float32)


# ---------------------------------------------------------------- TODO 1
class LearnedTobler(nn.Module):
    """A segment's terrain features -> its own Tobler-style constants:
    a (log of the peak speed), k_up / k_down (how fast speed falls above /
    below the peak; softplus keeps them positive), s0 (where the peak sits)
    and log_sigma (the spread). e (the rounded top) stays the reference's.
    Before training every segment gets exactly the reference curve: the last
    layer's weights are zero and its biases are the reference constants."""

    def __init__(self, n_in, p, sd, hidden=32):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(n_in, hidden), nn.SiLU(),
                                  nn.Linear(hidden, hidden), nn.SiLU())
        self.out = nn.Linear(hidden, 5)          # a, k_up, k_down, s0, log_sigma
        a, k_up, k_down, s0, e = p
        with torch.no_grad():
            self.out.weight.zero_()              # every segment starts the same...
            self.out.bias.copy_(torch.tensor([   # ...on the reference curve
                a,
                np.log(np.expm1(k_up)),          # softplus of this = k_up
                np.log(np.expm1(k_down)),        # softplus of this = k_down
                s0,
                np.log(sd),                      # log_sigma: the reference's spread
            ]))
        self.e = float(abs(e))

    def forward(self, x):
        z = self.out(self.body(x))
        return dict(a=z[:, 0], k_up=F.softplus(z[:, 1]),
                    k_down=F.softplus(z[:, 2]), s0=z[:, 3], log_sigma=z[:, 4])


def curve_torch(s, q, e):
    """CURVE's formula, with each segment's own constants q (the model's
    output) instead of one set for everybody."""
    x = s + q["s0"]
    r = torch.sqrt(x ** 2 + e ** 2) - e
    return q["a"] - torch.where(x >= 0, q["k_up"], q["k_down"]) * r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="outing5",
                    choices=["outing5", "hiker5", "block5", "loro",
                             "loro_hiker"])
    args = ap.parse_args()
    t, inner, cols = load()
    s, y = t.slope.to_numpy(), t.y.to_numpy()
    terrain = cols["covariates"]["terrain5m"] + cols["covariates"]["terrain1m"]
    print(f"{len(t):,} segments; split {args.split}; "
          f"{len(terrain)} terrain covariates")

    ref_crps, model_crps = [], []
    for f, fit, stop, cal, test in folds(t, inner, args.split):
        p, c_ref = reference(s, y, fit, stop, cal, test)
        ref_crps.append(c_ref)
        x = features(t, terrain, np.r_[fit, stop])
        print(f"  fold {f}: fit {len(fit):,}, stop {len(stop):,}, "
              f"cal {len(cal):,}, test {len(test):,}; reference "
              f"a={p[0]:.3f} k_up={p[1]:.2f} k_down={p[2]:.2f} "
              f"s0={p[3]:.3f} e={p[4]:.3f}")

        # TODO 1 (the model): a torch nn.Module that maps x (one row per
        #   segment) to the curve's constants a, k_up, k_down, s0 (keep e
        #   from p, or learn it) and a spread log_sigma. Keep k positive
        #   with softplus. Start it AT the reference: zero the last layer's
        #   weights and set its biases so the outputs equal p (and
        #   log_sigma = log of the SD of the cal residuals).
        sd = np.std(y[cal] - CURVE(p, s[cal]))       # the reference's spread
        model = LearnedTobler(x.shape[1], p, sd)
        with torch.no_grad():                        # check: untrained = reference
            q = model(torch.from_numpy(x[test]))
            mu0 = curve_torch(torch.from_numpy(s[test]).float(), q, model.e)
        diff = np.abs(mu0.numpy() - CURVE(p, s[test])).max()
        print(f"    untrained model vs the reference curve: largest "
              f"difference {diff:.1e} (should be about 1e-6 or less)")
        # TODO 2 (the loss): Student-t negative log-likelihood of y,
        #   sc.nll_student_t_torch(mu, sigma, nu, y) with mu = the curve
        #   evaluated with the predicted constants; nu fixed (say 5) at
        #   first. (Or sc.crps_gaussian_torch.)
        # TODO 3 (training): Adam, mini-batches of rows in fit; after each
        #   epoch compute the loss on stop and keep the best weights (early
        #   stopping). Nothing from test may be used.
        # TODO 4 (scoring, two ways):
        #   (a) like the harness: mu on test + residual quantiles of
        #       y - mu on cal -> sc.crps_quantiles(...); this is the number
        #       that compares with Table I
        #   (b) with your own spread: sc.crps_student_t(mu, sigma, nu, y)
        #   append (a) to model_crps.

    ref = np.concatenate(ref_crps)
    print(f"reference slope curve, mean CRPS (log) {ref.mean():.6f} "
          "(compare: Table I's baseline for this split)")
    if model_crps:
        mod = np.concatenate(model_crps)
        print(f"your model: CRPS skill vs the reference "
              f"{sc.skill(mod, ref):+.2f}%")


if __name__ == "__main__":
    main()
