#!/usr/bin/env python3
"""
Week 11 runs (prepared by Claude, 26 Oct 2026): the learned-Tobler model
from learned_tobler.py on every split and several seeds, next to the
harness's boosted trees (gbm_rs: slope + the same 12 terrain covariates,
same folds, same settings), saving one row per scored segment so that
gate2_summary.py can put paired intervals on "learned Tobler minus trees".

Run:   ../../../.venv/bin/python run_all.py                 # 5 splits, seeds 0 1 2
       ../../../.venv/bin/python run_all.py --splits outing5 --seeds 0
Writes: ../../cache/t3_learned/<split>.parquet  (not in git)
          row, fold, region, outing, hiker   which segment, and its units
          crps_ref, crps_trees               slope curve; trees (harness way)
          crps_a_s<k>, crps_b_s<k>, in90_s<k>  learned Tobler, seed k: CRPS
                                             with the cal-residual spread (a)
                                             and its own Student-t (b); inside
                                             its own 90% range?
          <constant>_mean, <constant>_sd     a, k_up, k_down, s0, log_sigma:
                                             mean and SD over the seeds
Needs scikit-learn 1.9.1 (the cluster's version) for the trees.
"""
import argparse
import time

import numpy as np
import pandas as pd
import torch
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor

import learned_tobler as lt

sc = lt.sc
OUT = lt.ROOT / "cache" / "t3_learned"
SPLITS = ["outing5", "hiker5", "block5", "loro", "loro_hiker"]
CONSTANTS = ["a", "k_up", "k_down", "s0", "log_sigma"]


def trees(t, terrain, y, fit, stop, cal, test):
    """t3_harness's gbm_rs arm (gbm() and Arm.fit): trees on slope + the raw
    terrain covariates (missing values left to the trees), early-stopped on
    the stop rows, spread from the cal residuals; CRPS on test."""
    X = pd.concat([t[["slope"]], t[terrain]], axis=1)
    Xf = X.iloc[fit]
    cols = [c for c in X.columns if Xf[c].nunique(dropna=True) >= 2]
    m = HistGradientBoostingRegressor(
        learning_rate=0.05, max_iter=1000, max_leaf_nodes=31,
        min_samples_leaf=200, l2_regularization=1.0, early_stopping=True,
        n_iter_no_change=30, random_state=0)
    m.fit(Xf[cols], y[fit], X_val=X.iloc[stop][cols], y_val=y[stop])
    r = sc.residual_quantiles(y[cal] - m.predict(X.iloc[cal][cols]))
    return sc.crps_quantiles(m.predict(X.iloc[test][cols]), r, y[test])


def learned(x, s, y, p, fit, stop, cal, test, seed):
    """learned_tobler.py's model, trained and scored as in its main()."""
    sd = np.std(y[cal] - lt.CURVE(p, s[cal]))
    torch.manual_seed(seed)
    model = lt.LearnedTobler(x.shape[1], p, sd)
    X = torch.from_numpy(x)
    S = torch.tensor(s, dtype=torch.float32)
    Y = torch.tensor(y, dtype=torch.float32)
    lt.train(model, X, S, Y, fit, stop, seed=seed)
    te, ca = torch.from_numpy(test), torch.from_numpy(cal)
    with torch.no_grad():
        q_te, q_ca = model(X[te]), model(X[ca])
        mu_te = lt.curve_torch(S[te], q_te, model.e).numpy()
        mu_ca = lt.curve_torch(S[ca], q_ca, model.e).numpy()
    r = sc.residual_quantiles(y[cal] - mu_ca)
    sig = np.exp(q_te["log_sigma"].numpy())
    out = {"crps_a": sc.crps_quantiles(mu_te, r, y[test]),
           "crps_b": sc.crps_student_t(mu_te, sig, 5.0, y[test]),
           "in90": np.abs(y[test] - mu_te) <= stats.t.ppf(0.95, 5.0) * sig}
    out.update({c: q_te[c].numpy() for c in CONSTANTS})
    return out


def run_split(t, inner, terrain, split, seeds):
    s, y = t.slope.to_numpy(), t.y.to_numpy()
    parts = []
    for f, fit, stop, cal, test in lt.folds(t, inner, split):
        t0 = time.time()
        p, c_ref = lt.reference(s, y, fit, stop, cal, test)
        d = pd.DataFrame({"row": test, "fold": f,
                          "region": t.region.to_numpy()[test],
                          "outing": t.outing.to_numpy()[test],
                          "hiker": t.hiker.to_numpy()[test],
                          "crps_ref": c_ref,
                          "crps_trees": trees(t, terrain, y, fit, stop, cal,
                                              test)})
        x = lt.features(t, terrain, np.r_[fit, stop])
        runs = [learned(x, s, y, p, fit, stop, cal, test, k) for k in seeds]
        for k, o in zip(seeds, runs):
            d[f"crps_a_s{k}"] = o["crps_a"]
            d[f"crps_b_s{k}"] = o["crps_b"]
            d[f"in90_s{k}"] = o["in90"]
        for c in CONSTANTS:
            v = np.stack([o[c] for o in runs])
            d[f"{c}_mean"], d[f"{c}_sd"] = v.mean(0), v.std(0)
        parts.append(d)
        print(f"  {split} fold {f}: {len(test):,} test segments, "
              f"trees {sc.skill(d.crps_trees, d.crps_ref):+.2f}%, learned (a) "
              + " ".join(f"{sc.skill(d[f'crps_a_s{k}'], d.crps_ref):+.2f}"
                         for k in seeds)
              + f"%  ({time.time() - t0:.0f} s)", flush=True)
    d = pd.concat(parts, ignore_index=True)
    floats = d.select_dtypes("float64").columns
    d[floats] = d[floats].astype("float32")
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_parquet(OUT / f"{split}.parquet", index=False)
    print(f"{split}: trees {sc.skill(d.crps_trees, d.crps_ref):+.2f}%, "
          "learned (a) by seed "
          + " ".join(f"{sc.skill(d[f'crps_a_s{k}'], d.crps_ref):+.2f}"
                     for k in seeds)
          + f"% -> {OUT / f'{split}.parquet'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", nargs="+", default=SPLITS, choices=SPLITS)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    args = ap.parse_args()
    t, inner, cols = lt.load()
    terrain = cols["covariates"]["terrain5m"] + cols["covariates"]["terrain1m"]
    for split in args.splits:
        run_split(t, inner, terrain, split, args.seeds)


if __name__ == "__main__":
    main()
