#!/usr/bin/env python3
"""
Collect the numbers behind the project explainer page (Project_Explainer.html)
into one small JSON file, from every built region. Re-run it to refresh the
page's charts as the project moves on.

Output: results/explainer_data.json
Run (on the cluster, after t1_summary.py and t1_findings.py):
    python make_explainer_data.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import regions
import t1_variants as v

OUT = Path("results/explainer_data.json")
EDGES = np.arange(-0.40, 0.4001, 0.02)


def binned(w):
    b = pd.cut(w.slope, EDGES)
    g = w.groupby(b, observed=False).speed_kmh
    return {"slope_pct": [round(100 * (e + 0.01), 1) for e in EDGES[:-1]],
            "median": [None if np.isnan(x) else round(float(x), 3)
                       for x in g.median()],
            "q25": [None if np.isnan(x) else round(float(x), 3)
                    for x in g.quantile(0.25)],
            "q75": [None if np.isnan(x) else round(float(x), 3)
                    for x in g.quantile(0.75)],
            "n": [int(x) for x in g.size()]}


def main():
    built = [k for k in regions.CANDIDATES
             if (regions.data_dir(k) / "modes.csv").exists()]
    summ = pd.read_csv("results/t1_summary/regions.csv").set_index("region")
    out = {"generated_utc": datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M"), "regions": [], "candidates": [],
        "curves": {}}
    walks = []
    for key, (label, (w_, s_, e_, n_), tz, veg) in regions.CANDIDATES.items():
        cand = {"key": key, "label": label, "veg": veg,
                "lat": round((s_ + n_) / 2, 3), "lon": round((w_ + e_) / 2, 3),
                "built": key in built}
        out["candidates"].append(cand)
        if key not in built:
            continue
        d = regions.data_dir(key)
        tr = pd.read_csv(d / "traces.csv")
        modes = pd.read_csv(d / "modes.csv")
        seg = pd.read_parquet(d / "segments_L50.parquet")
        hikers = set(tr.loc[tr.hiking_trace, "trace_id"])
        w = v.walker_trail_segments(seg, hikers, modes)
        walks.append(w.assign(region=key))
        m = modes[modes.trace_id.isin(hikers)]["mode"].value_counts()
        r = summ.loc[key] if key in summ.index else None
        row = {"key": key, "label": label, "veg": veg,
               "sources": "lab only" if set(tr.source) ==
               {"lab original file"} else "API + lab",
               "modes": {k2: int(m.get(k2, 0)) for k2 in
                         ("walk", "run", "fast", "bike/ski", "unknown")}}
        if r is not None:
            for c in ("hiking_traces", "outings", "named_uploaders",
                      "walking_outings", "walking_segments", "walking_km",
                      "walking_hours", "bike_ski_traces", "match_rate_pct",
                      "sac_scale_pct", "surface_pct", "v0", "v0_lo",
                      "v0_hi", "k", "k_lo", "k_hi", "peak_pct"):
                val = r.get(c)
                row[c] = None if pd.isna(val) else round(float(val), 3)
        out["regions"].append(row)
        out["curves"][key] = binned(w)
    pooled = pd.concat(walks, ignore_index=True)
    out["curves"]["ALL"] = binned(pooled)
    if "ALL" in summ.index:
        a = summ.loc["ALL"]
        out["pooled"] = {c: round(float(a[c]), 3) for c in (
            "hiking_traces", "outings", "walking_outings", "walking_segments",
            "walking_km", "walking_hours", "bike_ski_traces", "v0", "v0_lo",
            "v0_hi", "k", "k_lo", "k_hi", "peak_pct")}
    f = Path("results/t1_findings/numbers.json")
    if f.exists():
        fn = json.loads(f.read_text())
        out["findings"] = {k: fn[k] for k in ("forms_cv", "best_form",
                                             "variance_split_outing",
                                             "variance_between_regions_pct_of_total",
                                             "fatigue", "asymmetry",
                                             "walking_segments",
                                             "walking_outings", "regions")}
    q = Path("results/t1_dem_quality.csv")
    if q.exists():
        out["dem_quality"] = pd.read_csv(q).round(1).to_dict("records")
    h = next((d / "metrics.csv" for d in (Path("results/t3_harness_terrain5m"),
                                          Path("results/t3_harness"))
              if (d / "metrics.csv").exists()), Path("none"))
    if h.exists():      # the first test (t3_harness.py, with terrain if run)
        m = pd.read_csv(h)
        m = m[m.split.isin(["outing5", "loro"])]
        out["harness"] = m[["split", "arm", "subset", "segments", "r2_log",
                            "crps_log", "crps_skill_vs_slope_pct", "cov50",
                            "cov90", "stretch_ape_median",
                            "time_ape_median", "hikes"]] \
            .round(4).to_dict("records")
        b = h.parent / "loro_by_region.csv"
        if b.exists():
            b = pd.read_csv(b).pivot(index="region", columns="arm",
                                     values="crps_skill_vs_slope_pct")
            if {"lin_rs", "lin_tags"} <= set(b.columns):
                out["terrain_wins"] = int((b.lin_rs > b.lin_tags).sum())
    mc = Path("results/t1_mode_check/summary.json")
    if mc.exists():
        out["mode_check"] = {k: v for k, v in json.loads(mc.read_text())
                             .items() if k != "strava_numeric_types_vs_names"}
    wm = regions.data_dir("wm")
    sens = wm / "stop_rule_sensitivity.csv"
    if sens.exists():
        out["wm_stop_rules"] = pd.read_csv(sens)[[
            "rule", "time_removed_pct", "v0_kmh", "v0_lo", "v0_hi", "k"]] \
            .round(3).to_dict("records")
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT}: {len(out['regions'])} built regions, "
          f"{len(out['candidates'])} candidates")


if __name__ == "__main__":
    main()
