#!/usr/bin/env python3
"""
T4: a terrain-adjusted hiking function, a drop-in replacement for Tobler's
formula that needs one extra number from any DEM.

    v = v0 * exp(-k * |s + s0|)          (km/h; s = slope as rise/run)
    ln v0 = a0 + a1 * z,   k = k0 + k1 * z,   z = steppiness

Steppiness = the spread (SD) of the 5 m pitches along the walked path
(`pitch_sd_5m` from t2_terrain5m.py), in grade units; z is it divided by
0.10 (so z = 1 means a 10% spread of 5 m pitches). It needs only a DEM and
the trail line. Tobler's form is kept (a tent in log space) so it can be
used anywhere Tobler is; the rounded / asymmetric forms are reported next
to it.

Outputs (results/t4_terrain_curve/):
  terciles.csv   the curve fitted in each steppiness tercile (v0, k, s0,
                 with 95% intervals resampling outings)
  formula.json   the continuous formula's coefficients, fitted on all
                 walking segments
  fig_curves.png speed vs slope by steppiness tercile, with Tobler
Run (cluster): python t4_terrain_curve.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

import t1_variants as v

OUT = Path("results/t4_terrain_curve")
SCALE = 0.10                     # z = steppiness / 10% grade
B = 200                          # bootstrap draws (outings)


def load():
    s = pd.read_parquet("data/t1_all/segments_L50.parquet",
                        columns=["region", "segment_id", "outing_id",
                                 "slope", "speed_kmh", "analysis_walk"])
    s = s[s.analysis_walk & (s.speed_kmh > 0)
          & s.slope.between(-0.6, 0.6)]
    t = pd.concat(pd.read_parquet(f, columns=["segment_id", "pitch_sd_5m"])
                  for f in sorted(Path("data/t2").glob("terrain5m_*.parquet")))
    s = s.merge(t, on="segment_id").dropna(subset=["pitch_sd_5m"])
    s["z"] = s.pitch_sd_5m / SCALE
    s["y"] = np.log(s.speed_kmh)
    return s.reset_index(drop=True)


def model(p, s, z):
    a0, a1, k0, k1, s0 = p
    return a0 + a1 * z - (k0 + k1 * z) * np.abs(s + s0)


def fit_formula(d):
    r = least_squares(lambda p: model(p, d.slope.to_numpy(), d.z.to_numpy())
                      - d.y.to_numpy(), [1.45, -0.1, 1.8, 0.2, 0.05],
                      loss="soft_l1", f_scale=0.3)
    return r.x


def tercile_fits(s, rng):
    s["tercile"] = pd.qcut(s.pitch_sd_5m, 3, labels=["smooth", "medium",
                                                     "steppy"])
    rows = []
    for name, d in s.groupby("tercile", observed=True):
        v0, k, s0 = v.fit(d)
        outs = d.outing_id.unique()
        boot = []
        for _ in range(B):
            pick = rng.choice(outs, len(outs))
            dd = d.set_index("outing_id").loc[pick].reset_index()
            boot.append(v.fit(dd))
        boot = np.array(boot)
        lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
        rows.append({"tercile": name,
                     "steppiness_range": f"{d.pitch_sd_5m.min():.3f}-"
                                         f"{d.pitch_sd_5m.max():.3f}",
                     "segments": len(d), "outings": len(outs),
                     "v0_kmh": v0, "v0_lo": lo[0], "v0_hi": hi[0],
                     "k": k, "k_lo": lo[1], "k_hi": hi[1],
                     "peak_slope_pct": -100 * s0})
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    s = load()
    print(f"{len(s):,} walking segments with steppiness, "
          f"{s.outing_id.nunique():,} outings")
    terc = tercile_fits(s, rng)
    terc.to_csv(OUT / "terciles.csv", index=False)
    print(terc.round(3).to_string(index=False))
    p = fit_formula(s)
    zq = np.percentile(s.z, [10, 50, 90])
    out = {"form": "v = exp(a0 + a1 z) * exp(-(k0 + k1 z) |s + s0|), km/h; "
                   "z = SD of 5 m pitches along the path / 0.10",
           "a0": p[0], "a1": p[1], "k0": p[2], "k1": p[3], "s0": p[4],
           "z_p10_p50_p90": [round(float(q), 3) for q in zq],
           "v0_at_p10_p50_p90": [round(float(np.exp(p[0] + p[1] * q)), 3)
                                 for q in zq],
           "k_at_p10_p50_p90": [round(float(p[2] + p[3] * q), 3)
                                for q in zq],
           "segments": len(s)}
    (OUT / "formula.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

    sl = np.linspace(-0.4, 0.4, 161)
    fig, ax = plt.subplots(figsize=(6.4, 4))
    colors = {"smooth": "#1baf7a", "medium": "#2a78d6", "steppy": "#eb6834"}
    for r in terc.itertuples():
        ax.plot(100 * sl, r.v0_kmh * np.exp(-r.k * np.abs(
            sl - r.peak_slope_pct / 100)), color=colors[r.tercile], lw=2,
            label=f"{r.tercile} trails: v0 {r.v0_kmh:.2f} km/h, "
                  f"k {r.k:.2f}")
    ax.plot(100 * sl, 6 * np.exp(-3.5 * np.abs(sl + 0.05)), "--",
            color="#52514e", lw=1.2, label="Tobler 1993")
    ax.set_xlabel("slope in walking direction (%)")
    ax.set_ylabel("walking speed (km/h)")
    ax.set_title("Hiking speed by trail steppiness (all 17 regions)",
                 fontsize=10)
    ax.grid(color="#e4e3df")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_curves.png", dpi=150)


if __name__ == "__main__":
    main()
