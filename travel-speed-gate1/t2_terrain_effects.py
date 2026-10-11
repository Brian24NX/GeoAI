#!/usr/bin/env python3
"""
What the terrain covariates mean, in speed: for every walking segment of
every region, the residual of ln(speed) after the pooled slope curve,
summarized by quintile of each terrain covariate (all regions, and per
region). Plain-language companion to the harness numbers.

Input:  data/t1_all/segments_L50.parquet, data/t2/terrain5m_*.parquet
Output: results/t2_terrain_effects/quintiles.csv (feature, region,
        quintile, median residual as % speed, segments), fig_quintiles.png
Run:    python t2_terrain_effects.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import t1_findings as tf

OUT = Path("results/t2_terrain_effects")
FEATURES = {"pitch_sd_5m": "steppiness (spread of 5 m pitches)",
            "hidden_grade_5m": "hidden climbing (uneven grade)",
            "relief_sd_5m": "bumpiness along the path",
            "pitch_max_5m": "steepest 5 m pitch",
            "cross_slope_5m": "side slope"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = pd.read_parquet("data/t1_all/segments_L50.parquet",
                        columns=["region", "segment_id", "slope",
                                 "speed_kmh", "analysis_walk"])
    s = s[s.analysis_walk & (s.speed_kmh > 0)
          & s.slope.between(-0.6, 0.6)]
    cov = pd.concat(pd.read_parquet(f) for f in
                    sorted(Path("data/t2").glob("terrain5m_*.parquet")))
    s = s.merge(cov, on="segment_id", how="inner")
    y = np.log(s.speed_kmh.to_numpy())
    p = tf.fit_form("smooth_asym", s.slope.to_numpy(), y)
    s["res"] = y - tf.FORMS["smooth_asym"][0](p, s.slope.to_numpy())
    rows = []
    for f in FEATURES:
        s["q"] = pd.qcut(s[f], 5, labels=False, duplicates="drop") + 1
        for reg, d in [("ALL", s)] + list(s.groupby("region")):
            g = d.groupby("q").res.agg(["median", "size"])
            for q, r in g.iterrows():
                rows.append({"feature": f, "region": reg, "quintile": int(q),
                             "speed_pct": 100 * (np.exp(r["median"]) - 1),
                             "segments": int(r["size"])})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "quintiles.csv", index=False)
    a = out[out.region == "ALL"].pivot(index="quintile", columns="feature",
                                       values="speed_pct")
    print(a.round(1).to_string())

    fig, ax = plt.subplots(1, len(FEATURES), figsize=(13, 3.2), sharey=True)
    for i, (f, name) in enumerate(FEATURES.items()):
        d = out[(out.feature == f) & (out.region != "ALL")]
        for _, g in d.groupby("region"):
            ax[i].plot(g.quintile, g.speed_pct, color="#c9c8c3", lw=0.8)
        ax[i].plot(a.index, a[f], color="#2a78d6", lw=2.2, marker="o",
                   label="all regions")
        ax[i].axhline(0, color="#52514e", lw=0.8)
        ax[i].set_title(name, fontsize=9)
        ax[i].set_xticks([1, 3, 5], ["lowest", "middle", "highest"])
        ax[i].spines[["top", "right"]].set_visible(False)
    ax[0].set_ylabel("speed vs slope curve (%)\n(median, by quintile)")
    ax[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Terrain from elevation data: each gray line is one "
                 "region", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "fig_quintiles.png", dpi=150)


if __name__ == "__main__":
    main()
