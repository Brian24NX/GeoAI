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

Output: results/t4_mode_curves/ curves.csv, ratio_by_slope.csv,
        fig_modes.png
Run (cluster): python t4_mode_curves.py
"""

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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    s = load()
    print(s.groupby("mode").agg(segments=("slope", "size"),
                                traces=("trace_id", "nunique"),
                                outings=("outing_id", "nunique")).to_string())
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


if __name__ == "__main__":
    main()
