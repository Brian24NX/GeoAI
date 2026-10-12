#!/usr/bin/env python3
"""
Two robustness checks on the final harness run (results/t3_harness_robust,
= the terrain15m run plus a time split and GPS-rate subsets):

  time  train on outings up to 2019, test on 2020 and later (all regions
        pooled), next to random new hikers (outing folds);
  gps   unseen-region skill on traces recorded every <= 2 s, 2-10 s and
        > 10 s (models trained on everything; only the scoring differs).

Also checks that the run reproduces the terrain15m numbers (same seed).
Output: results/t3_harness_robust/robust_summary.md
Run (Mac or cluster, after the harness run): python t3_robust_summary.py
"""

from pathlib import Path

import pandas as pd

RES = Path("results/t3_harness_robust")
REF = Path("results/t3_harness_terrain15m")
ARMS = {"tobler": "Tobler 1993", "campbell": "Campbell 2022",
        "stride": "STRIDE 2024", "lin_tags": "OSM tags, additive",
        "gbm_tags": "OSM tags, trees", "lin_rs": "Terrain, additive",
        "gbm_rs": "Terrain, trees", "lin_both": "Terrain + tags, additive",
        "gbm_both": "Terrain + tags, trees",
        "terrain_curve": "Terrain formula (5 numbers)"}
GPS = {"gps_le2": "<= 2 s", "gps_2to10": "2-10 s", "gps_gt10": "> 10 s"}


def cell(m, ci, split, arm, subset="all"):
    v = m[(m.split == split) & (m.arm == arm) & (m.subset == subset)]
    if not len(v):
        return ""
    s = f"{v.crps_skill_vs_slope_pct.iloc[0]:+.1f}"
    c = ci[(ci.split == split) & (ci.arm == arm)]
    if "subset" in ci:
        c = c[c.subset == subset]
    if len(c):
        s += f" [{c.skill_lo.iloc[0]:.1f}, {c.skill_hi.iloc[0]:.1f}]"
    return s


def main():
    m = pd.read_csv(RES / "metrics.csv")
    ci = pd.read_csv(RES / "skill_ci.csv")
    cg = pd.read_csv(RES / "skill_ci_gps.csv")
    out = ["# Robustness checks (`t3_robust_summary.py`)", "",
           "CRPS skill (%) vs the refitted slope curve, 95% intervals "
           "(outings resampled for outing and time splits, regions for "
           "unseen regions).", ""]

    # same seed, same data: the first three splits must equal terrain15m
    r = pd.read_csv(REF / "metrics.csv")
    k = ["split", "arm", "subset"]
    j = m.merge(r, on=k, suffixes=("", "_ref"))
    diff = (j.crps_log - j.crps_log_ref).abs().max()
    out += [f"Reproduces the terrain15m run: max |CRPS difference| = "
            f"{diff:.2g} over {len(j)} rows.", ""]

    seg = m[(m.arm == "slope_curve") & (m.subset == "all")].set_index(
        "split").segments
    out += ["## Newer hikes: trained up to 2019, tested on 2020+", "",
            f"Test: {seg.get('time', 0):,} segments after 2019 "
            "(outings with a doubtful date left out).", "",
            "| Model | New hikers, random | **Hikes after 2019** |",
            "|---|---|---|"]
    for a, name in ARMS.items():
        if a in set(m.arm):
            out.append(f"| {name} | {cell(m, ci, 'outing5', a)} | "
                       f"{cell(m, ci, 'time', a)} |")
    d = ci[(ci.split == "time") & ci.arm.str.contains(" - ")]
    for _, x in d.iterrows():
        out.append(f"\n`{x.arm}` after 2019: [{x.skill_lo:.1f}, "
                   f"{x.skill_hi:.1f}], {x.share_draws_above_0:.0%} of "
                   "draws above 0.")

    out += ["", "## GPS recording rate: unseen regions, by trace interval",
            ""]
    segs = m[(m.split == "loro") & (m.arm == "slope_curve")].set_index(
        "subset").segments
    hdr = " | ".join(f"{GPS[g]} ({segs.get(g, 0):,} segments)" for g in GPS)
    out += [f"| Model | All | {hdr} |", "|---|---|" + "---|" * len(GPS)]
    for a, name in ARMS.items():
        if a in set(m.arm):
            row = [cell(m, ci, "loro", a)] + [cell(m, cg, "loro", a, g)
                                              for g in GPS]
            out.append(f"| {name} | " + " | ".join(row) + " |")
    out.append("")
    for g in GPS:
        d = cg[(cg.split == "loro") & (cg.subset == g)
               & (cg.arm == "lin_rs - lin_tags")]
        if len(d):
            x = d.iloc[0]
            out.append(f"- {GPS[g]}: terrain minus tags (additive) "
                       f"[{x.skill_lo:.1f}, {x.skill_hi:.1f}], "
                       f"{x.share_draws_above_0:.0%} of draws above 0.")
    cov = m[(m.split == "loro") & (m.arm.isin(["slope_curve", "lin_rs"]))
            & m.subset.isin(GPS)]
    out += ["", "Unseen regions by interval: coverage of 90% ranges, bias "
            "(log speed), median whole-hike error:", "",
            "| Model | Interval | 90% coverage | Bias | Hike error |",
            "|---|---|---|---|---|"]
    out += [f"| {ARMS.get(x.arm, 'Slope curve')} | {GPS[x.subset]} | {x.cov90:.3f} "
            f"| {x.bias_log:+.3f} | {100 * x.time_ape_median:.1f}% |"
            for x in cov.itertuples()]
    out.append("")
    (RES / "robust_summary.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
