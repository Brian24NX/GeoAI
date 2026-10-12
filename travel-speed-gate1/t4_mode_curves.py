#!/usr/bin/env python3
"""
T4 / plan question 4: does travel mode just multiply walking speed by a
constant? Tobler (1993) handles other modes with fixed multipliers (x3/5
off-path, x5/4 on horseback), and GIS tools do the same for bikes. If that
held, the ratio of bike (or run) speed to walking speed would be the same
at every slope.

Data: trail segments (not suspect, slope known) of hiking traces in all 17
regions, by the trace's travel mode from t1_modes.py: walk, run, bike/ski.
  1. The tent curve ln v = ln v0 - k |s + s0| per mode, with 95% intervals
     resampling outings.
  2. Median speed per mode in 2% slope bins, and the ratio to walking in
     each bin, with 95% intervals resampling outings.
  3. The plan's test (sec. 9): one tent curve shared by all modes with a
     per-mode multiplier (M0) vs a tent curve per mode (M1), 5-fold
     cross-validation over outings, held-out RMSE of log speed per mode
     with 95% intervals resampling outings; and where M0 misses (its mean
     error on descents, level trail and climbs).

Output: results/t4_mode_curves/ curves.csv, ratio_by_slope.csv,
        multiplier_test.csv, multiplier_fit.json, fig_modes.png
Run (cluster): python t4_mode_curves.py      (--test-only: part 3 only)
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import t1_variants as v

OUT = Path("results/t4_mode_curves")
MODES = ["walk", "run", "bike/ski"]
EDGES = np.arange(-0.30, 0.3001, 0.04)
B = 200


def load():
    s = pd.read_parquet("data/t1_all/segments_L50.parquet",
                        columns=["region", "outing_id", "trace_id", "slope",
                                 "speed_kmh", "way_class", "suspect", "mode"])
    s = s[(s.way_class == "trail") & ~s.suspect & s.slope.notna()
          & (s.speed_kmh > 0) & s.slope.between(-0.4, 0.4)
          & s["mode"].isin(MODES)]
    return s.reset_index(drop=True)


def binned_medians(s):
    b = pd.cut(s.slope, EDGES)
    return s.groupby([b, "mode"], observed=False).speed_kmh.median() \
        .unstack("mode")


S0_GRID = np.arange(-0.10, 0.20001, 0.005)        # as t1_variants.fit


def fit_tent(x, y, groups=None, n_groups=1):
    """ln v = a_g - k |s + s0| by least squares, s0 on a grid: one
    intercept per group (the per-mode multiplier), k and s0 shared."""
    groups = np.zeros(len(x), int) if groups is None else groups
    G = np.eye(n_groups)[groups]
    best = None
    for s0 in S0_GRID:
        A = np.c_[G, -np.abs(x + s0)]
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = float(np.sum((A @ coef - y) ** 2))
        if best is None or sse < best[0]:
            best = (sse, s0, coef)
    _, s0, coef = best
    return coef[:-1], float(coef[-1]), float(s0)


def multiplier_test(s, rng, folds=5):
    """M0 (shared curve x per-mode multiplier) vs M1 (curve per mode)."""
    x, y = s.slope.to_numpy(), np.log(s.speed_kmh.to_numpy())
    mi = s["mode"].map({m: i for i, m in enumerate(MODES)}).to_numpy()
    outs = s.outing_id.unique().copy()
    rng.shuffle(outs)
    fold = s.outing_id.map({o: i % folds for i, o in
                            enumerate(outs)}).to_numpy()
    p0, p1 = np.empty_like(y), np.empty_like(y)
    for f in range(folds):
        tr, te = fold != f, fold == f
        a, k, s0 = fit_tent(x[tr], y[tr], mi[tr], len(MODES))
        p0[te] = a[mi[te]] - k * np.abs(x[te] + s0)
        for j in range(len(MODES)):
            aj, kj, s0j = fit_tent(x[tr & (mi == j)], y[tr & (mi == j)])
            q = te & (mi == j)
            p1[q] = aj[0] - kj * np.abs(x[q] + s0j)
    d = pd.DataFrame({"mode": s["mode"], "outing_id": s.outing_id,
                      "slope": x, "e0": y - p0, "e1": y - p1})
    rows = []
    for m in MODES:
        dm = d[d["mode"] == m]
        g = dm.groupby("outing_id").agg(n=("e0", "size"),
                                        s0=("e0", lambda e: (e ** 2).sum()),
                                        s1=("e1", lambda e: (e ** 2).sum()))
        idx = rng.integers(0, len(g), (B * 5, len(g)))
        n, a0, a1 = (g[c].to_numpy()[idx].sum(1) for c in ("n", "s0", "s1"))
        gain = 100 * (1 - np.sqrt(a1 / n) / np.sqrt(a0 / n))
        r0 = float(np.sqrt(g.s0.sum() / g.n.sum()))
        r1 = float(np.sqrt(g.s1.sum() / g.n.sum()))
        row = {"mode": m, "segments": len(dm), "outings": len(g),
               "rmse_log_multiplier": r0, "rmse_log_own_curve": r1,
               "gain_pct": 100 * (1 - r1 / r0),
               "gain_lo": float(np.percentile(gain, 2.5)),
               "gain_hi": float(np.percentile(gain, 97.5))}
        for name, lo, hi in [("descents", -1, -0.10), ("level", -0.10, 0.10),
                             ("climbs", 0.10, 1)]:
            e = dm.e0[(dm.slope >= lo) & (dm.slope < hi)]
            row[f"multiplier_error_{name}_pct"] = float(
                100 * (np.exp(e.mean()) - 1))
        rows.append(row)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "multiplier_test.csv", index=False)
    a, k, s0 = fit_tent(x, y, mi, len(MODES))
    fit = {"shared_k": k, "shared_peak_slope_pct": -100 * s0,
           "multiplier_vs_walk": {m: float(np.exp(a[j] - a[0]))
                                  for j, m in enumerate(MODES)},
           "v0_kmh": {m: float(np.exp(a[j])) for j, m in enumerate(MODES)}}
    (OUT / "multiplier_fit.json").write_text(json.dumps(fit, indent=1))
    print(res.round(3).to_string(index=False))
    print(json.dumps(fit, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-only", action="store_true",
                    help="only part 3, the multiplier test")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    s = load()
    print(s.groupby("mode").agg(segments=("slope", "size"),
                                traces=("trace_id", "nunique"),
                                outings=("outing_id", "nunique")).to_string())
    if args.test_only:
        multiplier_test(s, np.random.default_rng(1))
        return
    rows = []
    for m in MODES:
        d = s[s["mode"] == m]
        v0, k, s0 = v.fit(d)
        outs = d.outing_id.unique()
        boot = []
        for _ in range(B):
            dd = d.set_index("outing_id").loc[rng.choice(outs, len(outs))]
            boot.append(v.fit(dd.reset_index()))
        lo, hi = np.percentile(np.array(boot), [2.5, 97.5], axis=0)
        rows.append({"mode": m, "segments": len(d), "outings": len(outs),
                     "v0_kmh": v0, "v0_lo": lo[0], "v0_hi": hi[0],
                     "k": k, "k_lo": lo[1], "k_hi": hi[1],
                     "peak_slope_pct": -100 * s0})
    curves = pd.DataFrame(rows)
    curves.to_csv(OUT / "curves.csv", index=False)
    print(curves.round(3).to_string(index=False))

    # ratio to walking by slope bin, resampling outings within each mode
    med = binned_medians(s)
    by_out = {m: s[s["mode"] == m].outing_id.unique() for m in MODES}
    idx = {m: s[s["mode"] == m].set_index("outing_id") for m in MODES}
    boot = []
    for _ in range(B):
        parts = [idx[m].loc[rng.choice(by_out[m], len(by_out[m]))]
                 for m in MODES]
        boot.append(binned_medians(pd.concat(parts).reset_index()))
    rows = []
    for i, iv in enumerate(med.index):
        for m in ["run", "bike/ski"]:
            r = med.loc[iv, m] / med.loc[iv, "walk"]
            rb = np.array([b_.iloc[i][m] / b_.iloc[i]["walk"] for b_ in boot])
            rb = rb[np.isfinite(rb)]
            n = int(((s["mode"] == m) & (pd.cut(s.slope, EDGES) == iv)).sum())
            rows.append({"slope_bin": str(iv),
                         "slope_mid_pct": round(100 * iv.mid, 1), "mode": m,
                         "ratio_to_walk": r, "lo": np.percentile(rb, 2.5)
                         if len(rb) else np.nan,
                         "hi": np.percentile(rb, 97.5) if len(rb) else np.nan,
                         "segments": n})
    ratio = pd.DataFrame(rows)
    ratio.to_csv(OUT / "ratio_by_slope.csv", index=False)
    print(ratio.round(2).to_string(index=False))

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    colors = {"walk": "#2a78d6", "run": "#1baf7a", "bike/ski": "#eb6834"}
    mids = 100 * np.array([iv.mid for iv in med.index])
    for m in MODES:
        ax[0].plot(mids, med[m], marker="o", ms=3, color=colors[m], label=m)
    ax[0].plot(mids, 6 * np.exp(-3.5 * np.abs(mids / 100 + 0.05)), "--",
               color="#52514e", lw=1, label="Tobler (walking)")
    ax[0].set_xlabel("slope in travel direction (%)")
    ax[0].set_ylabel("median speed (km/h)")
    ax[0].set_title("Speed by mode on trails (17 regions)", fontsize=10)
    for m in ["run", "bike/ski"]:
        d = ratio[(ratio["mode"] == m) & (ratio.segments >= 200)]
        ax[1].plot(d.slope_mid_pct, d.ratio_to_walk, marker="o", ms=3,
                   color=colors[m], label=f"{m} / walk")
        ax[1].fill_between(d.slope_mid_pct, d.lo, d.hi, color=colors[m],
                           alpha=0.15, lw=0)
    ax[1].axhline(1, color="#52514e", lw=0.8)
    ax[1].set_xlabel("slope in travel direction (%)")
    ax[1].set_ylabel("speed ratio to walking")
    ax[1].set_title("A constant multiplier would be a flat line",
                    fontsize=10)
    for a in ax:
        a.grid(color="#e4e3df")
        a.spines[["top", "right"]].set_visible(False)
        a.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_modes.png", dpi=150)
    multiplier_test(s, np.random.default_rng(1))


if __name__ == "__main__":
    main()
