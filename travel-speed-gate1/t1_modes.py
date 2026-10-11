#!/usr/bin/env python3
"""
Which mode is each trace? (plan sec. 8: "infer mode from permitted modes plus
observed speed ... anchor it: fit mode-conditional speed distributions only
on segments where permissions are exclusive, then use those fitted
distributions to classify traces on mixed-use segments. Report mode as
inferred with a confidence, not as ground truth, and keep an
unambiguous-permissions subset for validation.")

Per trace, from its trail segments (50 m, not suspect):
  v_med   median moving speed (km/h)
  v_p90   90th-percentile segment speed
  asym    ln(median speed downhill / median speed uphill), slopes of 6-20%:
          walkers and runners come down only a little faster than they go
          up; cyclists and skiers come down several times faster. Used ONLY
          to split the fast traces into run and bike/ski -- never to pick
          walkers, because Q3 studies this very ratio.
  foot    share of the trace's trail segments where bikes and horses are
          NOT allowed (OSM permissions; gate1_audit.permission)

Anchors: traces with foot >= 0.9 can only be on foot, because bikes aren't
allowed where they went. Walking is fitted on them (see classify); every
trace gets p_walk, the probability it is walking. Non-walking traces are
split into run and bike by a stated rule (no runner-only or bike-only
trails exist to anchor on). Validation: how the anchors are classified,
and the picture fig_mode_features.png.

Output (per region data dir): modes.csv (one row per trace), and the
columns mode / mode_conf / foot_anchor added to every segments_L*.parquet.
Anchors are pooled over all the regions given, so re-run it on ALL regions
whenever one is added.
Run:  python t1_modes.py data/t1_white_mountains [data/t1_<region> ...]
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

UP, DOWN, BAND = 0.06, -0.06, 0.20   # asym uses slopes of 6-20% each way
MIN_SEG = 10                    # fewer trail segments: mode "unknown"
MIN_SIDE = 3                    # segments needed on each side for asym
FOOT_ANCHOR = 0.9               # share of foot-only segments
WALK_Z = 3.0                    # spreads above the anchored walking speed
BIKE_RATIO = 1.7                # down/up speed ratio: legs rarely do this
BIKE_FAST_KMH = 6.0             #   ... together with descents this fast
BIKE_P90_KMH = 20.0             # or the fastest 10% at wheel / ski speed


def features(seg):
    """One row per trace with the mode features."""
    s = seg[(seg.way_class == "trail") & ~seg.suspect & seg.slope.notna()
            & (seg.moving_s > 0)]
    rows = []
    for tid, d in s.groupby("trace_id"):
        up = d[(d.slope >= UP) & (d.slope <= BAND)]
        dn = d[(d.slope <= DOWN) & (d.slope >= -BAND)]
        asym = (np.log(dn.speed_kmh.median() / up.speed_kmh.median())
                if len(up) >= MIN_SIDE and len(dn) >= MIN_SIDE else np.nan)
        rows.append({"trace_id": tid, "n_seg": len(d),
                     "v_med": d.speed_kmh.median(),
                     "v_p90": d.speed_kmh.quantile(0.9),
                     "v_up": up.speed_kmh.median() if len(up) else np.nan,
                     "v_down": dn.speed_kmh.median() if len(dn) else np.nan,
                     "asym": asym,
                     "foot": (d.permission == "foot-only").mean()})
    return pd.DataFrame(rows)


def robust_normal(v):
    """Median and MAD of ln(speed): a few runners on foot-only trails
    shouldn't stretch the walking distribution."""
    x = np.log(v)
    mu = float(np.median(x))
    return mu, float(1.4826 * np.median(np.abs(x - mu)))


def classify(feat):
    """Adds walk_z, gravity, mode and mode_conf to feat.

    1. WALK vs FAST on the median moving speed only (not on the downhill/
       uphill ratio, which Q3 studies -- that would be circular, plan
       sec. 8). Walking is ANCHORED on the traces that stayed on foot-only
       trails, where bikes aren't allowed: the robust mean and spread of
       their ln(median speed). walk_z = how many spreads above that a trace
       is; FAST if walk_z > WALK_Z (faster than ~all anchored walkers).
       mode_conf = Phi(WALK_Z - walk_z) for walkers, Phi(walk_z - WALK_Z)
       for fast traces: 0.5 at the boundary, near 1 far from it.
    2. GRAVITY (bike or ski): a stated rule, since no bike-only trails exist
       to anchor on -- the trace comes down >= BIKE_RATIO times faster than
       it climbs AND at >= BIKE_FAST_KMH, or its fastest 10% of segments
       reach BIKE_P90_KMH. Catches hike-up / ski-down tours whose median
       looks like walking. Ordinary fast-descending hikers don't reach it.
    mode: bike/ski if gravity; else walk or run ("fast" when there are too
    few slopes to compute the ratio)."""
    from math import erf, sqrt
    phi = np.vectorize(lambda z: 0.5 * (1 + erf(z / sqrt(2))))
    ok = (feat.n_seg >= MIN_SEG) & (feat.v_med > 0)
    anchors = ok & (feat.foot >= FOOT_ANCHOR)
    mu, sd = robust_normal(feat.v_med[anchors])
    out = feat.copy()
    out["walk_z"] = (np.log(out.v_med) - mu) / sd
    out.loc[~ok, "walk_z"] = np.nan
    ratio = np.exp(out.asym)
    out["gravity"] = ok & (((ratio >= BIKE_RATIO)
                            & (out.v_down >= BIKE_FAST_KMH))
                           | (out.v_p90 >= BIKE_P90_KMH))
    walk = ok & (out.walk_z <= WALK_Z)
    out["mode"] = "unknown"
    out.loc[walk, "mode"] = "walk"
    out.loc[ok & ~walk & out.asym.notna(), "mode"] = "run"
    out.loc[ok & ~walk & out.asym.isna(), "mode"] = "fast"
    out.loc[out.gravity, "mode"] = "bike/ski"
    conf = phi(np.nan_to_num(WALK_Z - out.walk_z))
    out["mode_conf"] = np.where(walk, conf, 1 - conf)
    out.loc[out.gravity, "mode_conf"] = np.nan        # a rule, not a fit
    out.loc[~ok, "mode_conf"] = np.nan
    out["foot_anchor"] = anchors
    model = {"walk_anchor": {"median_kmh": float(np.exp(mu)), "sd_ln": sd,
                             "traces": int(anchors.sum())},
             "walk_fast_boundary_kmh": float(np.exp(mu + WALK_Z * sd)),
             "gravity_rule": f"(down/up >= {BIKE_RATIO} and downhill median "
                             f">= {BIKE_FAST_KMH} km/h) or p90 >= "
                             f"{BIKE_P90_KMH} km/h"}
    return out, model


def main(dirs):
    feats = []
    for d in map(Path, dirs):
        f = features(pd.read_parquet(d / "segments_L50.parquet"))
        f["region_dir"] = str(d)
        feats.append(f)
    feat = pd.concat(feats, ignore_index=True)
    out, model = classify(feat)
    for d in map(Path, dirs):
        o = out[out.region_dir == str(d)].drop(columns="region_dir")
        o.to_csv(d / "modes.csv", index=False)
        # plan sec. 8 schema: inferred mode and confidence on every row
        cols = ["mode", "mode_conf", "foot_anchor"]
        for f in sorted(d.glob("segments_L*.parquet")):
            seg = pd.read_parquet(f).drop(columns=cols, errors="ignore")
            seg = seg.merge(o[["trace_id"] + cols], on="trace_id", how="left")
            seg["mode"] = seg["mode"].fillna("unknown")
            seg.to_parquet(f, index=False)
    anchors = out[out.foot_anchor]
    report = {
        "traces": int(len(out)),
        "classified": int((out["mode"] != "unknown").sum()),
        "by_mode": out["mode"].value_counts().to_dict(),
        "anchor_traces": int(len(anchors)),
        "anchors_called_bike_ski": int((anchors["mode"] == "bike/ski")
                                       .sum()),
        "anchors_called_walk": int((anchors["mode"] == "walk").sum()),
        "median_confidence": float(out.mode_conf.median()),
        "walkers_conf_over_0.9": float((out.loc[out["mode"] == "walk",
                                                "mode_conf"] > 0.9).mean()),
        "model": model}
    print(json.dumps(report, indent=2))
    return out, report


if __name__ == "__main__":
    main(sys.argv[1:] or ["data/t1_white_mountains"])
