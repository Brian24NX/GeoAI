#!/usr/bin/env python3
"""
What the lidar vegetation measures (t2_lidarveg.py) mean in speed: within
the same hike, how much faster or slower segments are by quintile of
understory density (nrd, nrd_center), canopy cover and canopy height, and
whether understory density still matters among segments of similar
steppiness (it could just be standing in for rough terrain).

Speed: the residual of ln(speed) after the pooled slope curve
(t1_findings smooth_asym), minus its outing's mean residual (same hiker,
same day). 95% intervals resample outings.

Input:  data/t1_all/segments_L50.parquet, data/t2/lidarveg_<region>.parquet,
        data/t2/terrain5m_<region>.parquet, results/t1_findings/numbers.json
Output: results/t2_lidarveg_effects/<region>_quintiles.csv,
        <region>_summary.json, fig_<region>_lidarveg.png
Run (cluster): python t2_lidarveg_effects.py --region wm
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import t1_findings as tf

OUT = Path("results/t2_lidarveg_effects")
FEATURES = {"nrd": "understory density, 3 m buffer",
            "nrd_center": "understory density on the tread (1 m)",
            "cover2m": "canopy cover (> 2 m)",
            "hag_p95": "canopy height (95th pct)"}
B = 1000


def pct(x):
    return 100 * (np.exp(x) - 1)


def boot(d, rng):
    """Mean rd over segments with a 95% interval resampling outings."""
    g = d.groupby("outing_id").rd.agg(["sum", "size"])
    s, n = g["sum"].to_numpy(), g["size"].to_numpy()
    idx = rng.integers(0, len(g), (B, len(g)))
    m = s[idx].sum(1) / n[idx].sum(1)
    return (pct(s.sum() / n.sum()),
            *[pct(x) for x in np.percentile(m, [2.5, 97.5])])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="wm")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    s = pd.read_parquet("data/t1_all/segments_L50.parquet",
                        columns=["region", "segment_id", "outing_id",
                                 "slope", "speed_kmh", "analysis_walk"],
                        filters=[("region", "==", a.region)])
    s = s[s.analysis_walk & (s.speed_kmh > 0)
          & s.slope.between(-0.6, 0.6)].reset_index(drop=True)
    p = json.loads(Path("results/t1_findings/numbers.json").read_text()
                   )["forms_cv"]["smooth_asym"]["params_all"]
    s["res"] = np.log(s.speed_kmh) - tf.FORMS["smooth_asym"][0](
        p, s.slope.to_numpy())
    s["rd"] = s.res - s.groupby("outing_id").res.transform("mean")
    lv = pd.read_parquet(f"data/t2/lidarveg_{a.region}.parquet")
    t5 = pd.read_parquet(f"data/t2/terrain5m_{a.region}.parquet",
                         columns=["segment_id", "pitch_sd_5m"])
    s = s.merge(lv, on="segment_id", how="left").merge(
        t5, on="segment_id", how="left")
    rows = []
    for f in FEATURES:
        d = s.dropna(subset=[f])
        q = pd.qcut(d[f], 5, labels=False, duplicates="drop")
        for k in sorted(q.unique()):
            x = d[q == k]
            m, lo, hi = boot(x, rng)
            rows.append({"feature": f, "quintile": int(k) + 1,
                         "median_value": float(x[f].median()),
                         "segments": len(x), "speed_pct": m, "lo": lo,
                         "hi": hi})
    qt = pd.DataFrame(rows)
    qt.to_csv(OUT / f"{a.region}_quintiles.csv", index=False)

    # understory density within steppiness terciles (terrain held fixed)
    d = s.dropna(subset=["nrd", "pitch_sd_5m"]).copy()
    d["step3"] = pd.qcut(d.pitch_sd_5m, 3, labels=["smooth", "medium",
                                                   "steppy"])
    within = {}
    for t, x in d.groupby("step3", observed=True):
        hi_, lo_ = x[x.nrd >= x.nrd.quantile(0.8)], x[x.nrd <= x.nrd.quantile(
            0.2)]
        mh, mh_lo, mh_hi = boot(hi_, rng)
        ml, _, _ = boot(lo_, rng)
        within[str(t)] = {"densest_fifth_pct": mh, "ci": [mh_lo, mh_hi],
                          "sparsest_fifth_pct": ml}
    summary = {
        "region": a.region, "segments": int(len(s)),
        "with_vegetation": float(s.nrd.notna().mean()),
        "correlation_with_steppiness": {
            f: float(s[[f, "pitch_sd_5m"]].corr(method="spearman").iloc[0, 1])
            for f in FEATURES},
        "nrd_quantiles": [float(v) for v in s.nrd.quantile(
            [0.1, 0.25, 0.5, 0.75, 0.9])],
        "nrd_within_steppiness_terciles": within}
    (OUT / f"{a.region}_summary.json").write_text(json.dumps(summary,
                                                             indent=1))
    print(qt.round(3).to_string(index=False))
    print(json.dumps(summary, indent=1))

    fig, ax = plt.subplots(1, len(FEATURES), figsize=(12, 3.2), sharey=True)
    for i, (f, name) in enumerate(FEATURES.items()):
        x = qt[qt.feature == f]
        ax[i].fill_between(x.quintile, x.lo, x.hi, color="#2a78d6",
                           alpha=0.15, lw=0)
        ax[i].plot(x.quintile, x.speed_pct, "o-", color="#2a78d6", ms=4)
        ax[i].axhline(0, color="#52514e", lw=0.8)
        ax[i].set_xticks([1, 3, 5], ["lowest", "middle", "highest"])
        ax[i].set_title(name, fontsize=8)
        ax[i].grid(color="#e4e3df")
        ax[i].spines[["top", "right"]].set_visible(False)
    ax[0].set_ylabel("speed within the same hike (%)")
    fig.suptitle(f"Lidar vegetation, {a.region}: quintiles of each measure",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / f"fig_{a.region}_lidarveg.png", dpi=170)


if __name__ == "__main__":
    main()
