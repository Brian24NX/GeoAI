#!/usr/bin/env python3
"""
Every data-dependent number in the IGARSS draft (paper/sections/*.tex and
the abstract), recomputed from a results folder (Claude, 24 Nov 2026), so
the v1 (October, 17 regions) and v1.1 (November, 16 regions) values can be
compared side by side. Table I itself: make_paper_table.py.

Run:  ../.venv/bin/python paper_numbers.py NEW_RESULTS [OLD_RESULTS]
      [--table NEW_T3_TABLE OLD_T3_TABLE]   (cache/exercise/t3_table.parquet,
                                            for the loro_hiker training share)
Prints one line per number: key, where it is in the paper, old, new.
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

TOBLER = dict(v0=6.0, k=3.5, s0=0.05)


def met(res, folder, split, arm, subset="all", col="crps_skill_vs_slope_pct"):
    m = pd.read_csv(res / folder / "metrics.csv")
    r = m[(m.split == split) & (m.arm == arm) & (m.subset == subset)]
    return float(r[col].iloc[0]) if len(r) else np.nan


def ci(res, folder, split, arm):
    c = pd.read_csv(res / folder / "skill_ci.csv")
    r = c[(c.split == split) & (c.arm == arm)].iloc[0]
    return float(r.skill_lo), float(r.skill_hi), r.get("share_draws_above_0")


def loro(res, folder="t3_harness_terrain15m"):
    l = pd.read_csv(res / folder / "loro_by_region.csv")
    return l[l.subset == "all"] if "subset" in l else l


def p1(x):
    return f"{x:+.1f}"


def rng(a, b):
    return f"[{a:.1f}, {b:.1f}]"


def numbers(res, table=None):
    T = "t3_harness_terrain15m"
    n = {}
    # --- dataset (results/t1_all/DATA_CARD.md, t1_summary/regions.csv)
    card = (res / "t1_all" / "DATA_CARD.md").read_text()
    m = re.search(r"Walking analysis set.*?: ([\d,]+) segments, ([\d,]+) traces,"
                  r" ([\d,]+) outings, ([\d,]+) moving hours, ([\d,]+) km", card)
    n["segments"], n["walk_traces"], n["outings"], n["hours"], n["km"] = m.groups()
    n["hiking_traces"] = re.search(r"Hiking traces: ([\d,]+)", card).group(1)
    n["regions"] = re.search(r"Regions: (\d+)", card).group(1)
    reg = pd.read_csv(res / "t1_summary" / "regions.csv")
    n["match_rate_range"] = (f"{reg.match_rate_pct.min():.0f}-"
                             f"{reg.match_rate_pct.max():.0f}%")
    lid = [int(x) for x in re.findall(r"\| (\d+)% \| (?:none|\d)", card)]
    if lid:
        n["lidar>=83%_regions"] = (f"{sum(x >= 83 for x in lid)} of {len(lid)}"
                                   f" (min of those {min(x for x in lid if x >= 83)}%)")
    wm = res / "fig1_wm_segments.parquet"
    if wm.exists():
        n["wm_inset_segments"] = f"{len(pd.read_parquet(wm)):,}"
    mc = json.loads((res / "t1_mode_check" / "summary.json").read_text())
    n["mode_check"] = (f"{mc['labeled']} labelled; hikes called walk "
                       f"{mc['hike_labels_called_walk_pct']}%; walkers labelled "
                       f"bike/ski {mc['called_walk_labeled_bike_or_ski_pct']}%")
    sc = res / "t1_sampling_check" / "summary.json"
    if sc.exists():
        s = json.loads(sc.read_text())
        r30 = s.get("rates", {}).get("30", {})
        if r30:
            n["thin_to_30s_speed"] = f"{100 * (r30['speed_ratio'] - 1):+.1f}%"
    # --- speed vs slope (t1_findings)
    f = json.loads((res / "t1_findings" / "numbers.json").read_text())
    b = pd.read_csv(res / "t1_findings" / "slope_bins.csv")
    tob = TOBLER["v0"] * np.exp(-TOBLER["k"] * np.abs(b.slope_mid + TOBLER["s0"]))
    ratio = tob / b.median_kmh - 1
    n["peak_bin_kmh"] = f"{b.median_kmh.max():.2f} at {b.slope_mid[b.median_kmh.idxmax()]:+.2f}"
    n["tobler_fast_within_10"] = f"{100 * ratio[b.slope_mid.abs() <= 0.10].mean():+.0f}%"
    n["tobler_vs_climbs>25"] = f"{100 * ratio[b.slope_mid > 0.25].mean():+.0f}%"
    a = f["asymmetry"]
    n["pairs"] = f"{a['pairs']:,} pairs from {a['outings']:,} outings"
    g = a["by_grade"]
    n["down_up_3-10"] = f"{100 * (g['0.03-0.10'][0] - 1):.0f}%"
    n["down_up_>20"] = (f"{100 * (g['0.20-0.30'][0] - 1):.0f}-"
                        f"{100 * (g['0.30-1.00'][0] - 1):.0f}%")
    n["var_between_outings"] = f"{f['variance_split_outing']['share_between_pct']:.0f}%"
    # --- Table I headline cells and their intervals (unseen regions)
    for arm in ["tobler", "campbell", "stride", "stride_refit", "lin_tags",
                "gbm_tags", "lin_rs", "gbm_rs", "lin_both", "gbm_both",
                "terrain_curve"]:
        lo, hi, _ = ci(res, T, "loro", arm)
        n[f"loro_{arm}"] = f"{p1(met(res, T, 'loro', arm))} {rng(lo, hi)}"
    for arm in ["lin_tags", "gbm_tags", "lin_rs", "gbm_rs"]:
        n[f"outing5_{arm}"] = p1(met(res, T, "outing5", arm))
    n["loro_local_refit"] = p1(met(res, T, "loro", "slope_curve_local"))
    lo, hi, sh = ci(res, T, "loro", "lin_rs - lin_tags")
    n["terrain_minus_tags_add"] = f"{rng(lo, hi)}, {100 * sh:.0f}% of draws > 0"
    lo, hi, sh = ci(res, T, "loro", "gbm_rs - gbm_tags")
    n["terrain_minus_tags_trees"] = f"{rng(lo, hi)}, {100 * sh:.0f}% of draws > 0"
    # --- per region (loro)
    L = loro(res)
    p = L.pivot_table(index="region", columns="arm",
                      values="crps_skill_vs_slope_pct")
    n["regions_held_out"] = str(len(p))
    n["tobler_worse_in"] = f"{(p.tobler < 0).sum()} of {len(p)}"
    n["campbell_range"] = (f"{p.campbell.min():+.1f} ({p.campbell.idxmin()}) to "
                           f"{p.campbell.max():+.1f} ({p.campbell.idxmax()})")
    d = p.lin_rs - p.lin_tags
    n["terrain_beats_tags_add"] = (f"{(d > 0).sum()} of {len(p)}; losers: " +
                                   ", ".join(f"{r} {v:+.2f}" for r, v in
                                             d[d <= 0].items()))
    n["terrain_beats_tags_trees"] = f"{(p.gbm_rs > p.gbm_tags).sum()} of {len(p)}"
    cov = L.pivot_table(index="region", columns="arm", values="cov90")
    arms = [c for c in cov.columns if "+me" not in c]
    mm = pd.read_csv(res / T / "metrics.csv")
    pooled = mm[(mm.split == "loro") & (mm.subset == "all") &
                (mm.arm.isin(arms))].cov90
    n["cov90_pooled"] = f"{100 * pooled.min():.1f}-{100 * pooled.max():.1f}%"
    lowest = cov[arms].min(axis=1)
    n["cov90_lowest_region"] = f"{100 * lowest.min():.0f}% ({lowest.idxmin()})"
    # --- controls and other inputs
    n["hidden_climbing"] = (f"{p1(met(res, 't3_harness_hidden5m', 'loro', 'lin_rs'))}"
                            f" / {p1(met(res, 't3_harness_hidden5m', 'loro', 'gbm_rs'))}")
    rf = "t3_harness_regionfe"
    n["terrain_over_region_offsets"] = " / ".join(
        f"{met(res, rf, s, 'lin_rs_region') - met(res, rf, s, 'lin_region'):.1f}"
        for s in ["outing5", "block5"])
    n["terrain_over_own_pace"] = " / ".join(
        f"{met(res, T, 'loro', a + '+me', 'rest') - met(res, T, 'loro', 'slope_curve+me', 'rest'):.1f}"
        for a in ["lin_rs", "gbm_rs"])
    n["own_pace_alone"] = p1(met(res, T, "loro", "slope_curve+me", "rest"))
    n["landcover_loro"] = (f"{p1(met(res, 't3_harness_landcover', 'loro', 'lin_rs'))} / "
                           f"{p1(met(res, 't3_harness_landcover', 'loro', 'gbm_rs'))}")
    A = "t3_harness_aef"
    n["aef_within"] = f"{p1(met(res, A, 'outing5', 'lin_rs'))} / {p1(met(res, A, 'outing5', 'gbm_rs'))}"
    n["aef_unseen"] = f"{p1(met(res, A, 'loro', 'lin_rs'))} / {p1(met(res, A, 'loro', 'gbm_rs'))}"
    lv, lt = "t3_harness_veg15_terrain_lidarveg_fixid", "t3_harness_veg15_terrain_fixid"
    add = [met(res, lv, s, a) - met(res, lt, s, a) for s in
           ["outing5", "block5", "loro"] for a in ["lin_rs", "gbm_rs"]]
    n["lidarveg_over_terrain"] = f"{min(add):+.2f} to {max(add):+.2f}"
    n["terrain_tags_unseen"] = (f"{p1(met(res, T, 'loro', 'lin_both'))} / "
                                f"{p1(met(res, T, 'loro', 'gbm_both'))}")
    # --- robustness
    R = "t3_harness_robust"
    n["time_split_terrain"] = f"{p1(met(res, R, 'time', 'lin_rs'))} / {p1(met(res, R, 'time', 'gbm_rs'))}"
    n["time_split_tags"] = f"{p1(met(res, R, 'time', 'lin_tags'))} / {p1(met(res, R, 'time', 'gbm_tags'))}"
    g = [met(res, R, "loro", "lin_rs", s) for s in ["gps_le2", "gps_2to10", "gps_gt10"]]
    n["gps_rate_terrain_add"] = f"{min(g):+.1f} to {max(g):+.1f}"
    Z = "t3_harness_zones"
    for s in ["macro", "eastwest"]:
        n[f"{s}_terrain"] = f"{p1(met(res, Z, s, 'lin_rs'))} / {p1(met(res, Z, s, 'gbm_rs'))}"
        n[f"{s}_tags"] = f"{p1(met(res, Z, s, 'lin_tags'))} / {p1(met(res, Z, s, 'gbm_tags'))}"
        n[f"{s}_formula"] = p1(met(res, Z, s, "terrain_curve"))
    H = "t3_harness_hikers"
    n["hiker5_terrain"] = f"{p1(met(res, H, 'hiker5', 'lin_rs'))} / {p1(met(res, H, 'hiker5', 'gbm_rs'))}"
    n["hiker5_tags"] = f"{p1(met(res, H, 'hiker5', 'lin_tags'))} / {p1(met(res, H, 'hiker5', 'gbm_tags'))}"
    n["loro_hiker_terrain"] = f"{p1(met(res, H, 'loro_hiker', 'lin_rs'))} / {p1(met(res, H, 'loro_hiker', 'gbm_rs'))}"
    n["loro_hiker_tags"] = f"{p1(met(res, H, 'loro_hiker', 'lin_tags'))} / {p1(met(res, H, 'loro_hiker', 'gbm_tags'))}"
    sh = [ci(res, H, "loro_hiker", a)[2] for a in ["lin_rs - lin_tags", "gbm_rs - gbm_tags"]]
    n["loro_hiker_terrain>tags_draws"] = " / ".join(f"{100 * x:.0f}%" for x in sh)
    if table is not None and Path(table).exists():
        t = pd.read_parquet(table, columns=["region", "hiker"])
        shares = []
        for r in t.region.unique():
            hk = set(t.hiker[t.region == r])
            tr = t[t.region != r]
            shares.append(100 * tr.hiker.isin(hk).mean())
        n["loro_hiker_train_share_dropped"] = f"{min(shares):.1f}-{max(shares):.1f}%"
    # --- by slope band (robust run, unseen, terrain additive / trees)
    for s in ["down_steep", "down", "level", "up", "up_steep"]:
        n[f"slope_{s}_terrain"] = (f"{p1(met(res, R, 'loro', 'lin_rs', s))} / "
                                   f"{p1(met(res, R, 'loro', 'gbm_rs', s))}")
    # --- whole hikes (unseen regions, after the first km)
    n["hikes_scored"] = f"{int(met(res, T, 'loro', 'slope_curve', 'rest', col='hikes')):,}"
    for a in ["tobler", "campbell", "slope_curve", "lin_rs", "gbm_rs",
              "slope_curve+me", "lin_rs+me", "gbm_rs+me"]:
        n[f"hike_time_err_{a}"] = f"{100 * met(res, T, 'loro', a, 'rest', col='time_ape_median'):.1f}%"
    # --- Eq. (1) and the terrain curve
    fj = json.loads((res / "t4_terrain_curve" / "formula.json").read_text())
    n["eq1"] = ", ".join(f"{k} {fj[k]:.3f}" for k in ["a0", "a1", "k0", "k1", "s0"])
    # --- weather
    w = res / "t2_weather" / "summary.json"
    if w.exists():
        n["weather_summary"] = json.dumps(json.loads(w.read_text()))[:300]
    n["weather_unseen"] = (f"{p1(met(res, 't3_harness_weather', 'loro', 'lin_rs'))} / "
                           f"{p1(met(res, 't3_harness_weather', 'loro', 'gbm_rs'))}")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("new")
    ap.add_argument("old", nargs="?")
    ap.add_argument("--table", nargs=2)
    a = ap.parse_args()
    new = numbers(Path(a.new), a.table[0] if a.table else None)
    old = numbers(Path(a.old), a.table[1] if a.table else None) if a.old else {}
    w = max(map(len, new))
    for k, v in new.items():
        o = old.get(k, "")
        mark = "  " if o == v else "* "
        print(f"{mark}{k:<{w}}  {o!s:<44}  ->  {v}")


if __name__ == "__main__":
    main()
