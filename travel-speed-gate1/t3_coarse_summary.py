#!/usr/bin/env python3
"""
Idea 1 (decision #131): one table from the coarse-elevation harness runs
(cluster/coarse_job.sh) next to the 5 m and paper runs.

Rows, by elevation data (the slope every arm uses comes from the same
grid, except "30 m terrain, 5 m slope"):
  paper        1 m + 5 m terrain, T1's 5 m slope   t3_harness_terrain15m
  5 m          5 m terrain, T1's 5 m slope         t3_harness_terrain5m
  10 m         10 m terrain and slope              t3_harness_coarse10
  30 m         30 m terrain and slope              t3_harness_coarse30
  30 m / 5 m   30 m terrain, T1's 5 m slope        t3_harness_coarse30_slope5m
  Copernicus   the real 30 m DEM (GLO-30, #132)    t3_harness_cop30
               ... its terrain on T1's 5 m slope   t3_harness_cop30_slope5m
Columns: CRPS skill (%) vs that run's own slope curve, additive / trees, for
new hikes, new 10 km squares and unseen regions (95% interval over regions);
tags on the same slope; terrain minus tags (95% interval, additive); held-
out regions where terrain beats tags; and the slope curve's and the terrain
trees' skill vs the 5 m slope curve (the same test segments in every run),
which shows what the coarser slope itself costs.
Second table: the paper's terrain with and without aspect and curvature
(t3_harness_terrain15m_aspcurv).

Output: results/t3_coarse_dem/summary.csv, aspcurv.csv, summary.md
Run:    python t3_coarse_summary.py   (after copying the result folders)
"""

from pathlib import Path

import pandas as pd

R = Path("results")
OUT = R / "t3_coarse_dem"
RUNS = {"paper (1 m + 5 m)": "t3_harness_terrain15m",
        "5 m": "t3_harness_terrain5m",
        "10 m": "t3_harness_coarse10",
        "30 m": "t3_harness_coarse30",
        "30 m terrain, 5 m slope": "t3_harness_coarse30_slope5m",
        "Copernicus 30 m": "t3_harness_cop30",
        "Copernicus terrain, 5 m slope": "t3_harness_cop30_slope5m"}
ASPCURV = {"paper terrain": "t3_harness_terrain15m",
           "+ aspect, curvature": "t3_harness_terrain15m_aspcurv"}
SPLITS = {"outing5": "new hikes", "block5": "new 10 km", "loro": "unseen"}


def load(run):
    d = R / run
    m = pd.read_csv(d / "metrics.csv")
    m = m[m.subset.eq("all")].set_index(["split", "arm"])
    return (m, pd.read_csv(d / "skill_ci.csv").set_index(["split", "arm"]),
            pd.read_csv(d / "loro_by_region.csv"))


def skill(m, split, arm):
    return m.loc[(split, arm), "crps_skill_vs_slope_pct"]


def main():
    have = {k: v for k, v in RUNS.items() if (R / v / "metrics.csv").exists()}
    base = load(RUNS["5 m"])[0]          # the 5 m slope curve, per split
    rows = []
    for name, run in have.items():
        m, ci, by = load(run)
        row = {"elevation": name}
        for sp, label in SPLITS.items():
            row[f"{label}: terrain add."] = skill(m, sp, "lin_rs")
            row[f"{label}: terrain trees"] = skill(m, sp, "gbm_rs")
        for arm in ("lin_rs", "gbm_rs"):
            lo, hi = ci.loc[("loro", arm), ["skill_lo", "skill_hi"]]
            row[f"unseen CI {arm}"] = f"[{lo:.1f}, {hi:.1f}]"
        row["unseen: tags add."] = skill(m, "loro", "lin_tags")
        row["unseen: tags trees"] = skill(m, "loro", "gbm_tags")
        lo, hi, share = ci.loc[("loro", "lin_rs - lin_tags"),
                               ["skill_lo", "skill_hi", "share_draws_above_0"]]
        row["terrain - tags (add.)"] = f"[{lo:.1f}, {hi:.1f}], {share:.0%} > 0"
        p = by.pivot(index="region", columns="arm", values="crps_log")
        row["beats tags (add.)"] = f"{(p.lin_rs < p.lin_tags).sum()} / {len(p)}"
        row["beats tags (trees)"] = f"{(p.gbm_rs < p.gbm_tags).sum()} / {len(p)}"
        for arm, label in (("slope_curve", "slope curve"),
                           ("gbm_rs", "terrain trees")):
            ref = base.loc[("loro", "slope_curve"), "crps_log"]
            row[f"unseen: {label} vs 5 m slope curve"] = 100 * (
                1 - m.loc[("loro", arm), "crps_log"] / ref)
        rows.append(row)
    tab = pd.DataFrame(rows).set_index("elevation")
    OUT.mkdir(parents=True, exist_ok=True)
    tab.to_csv(OUT / "summary.csv")

    ac = []
    if all((R / v / "metrics.csv").exists() for v in ASPCURV.values()):
        for name, run in ASPCURV.items():
            m = load(run)[0]
            ac.append({"terrain": name, **{
                f"{SPLITS[sp]}: {a}": skill(m, sp, arm)
                for sp in SPLITS for a, arm in (("add.", "lin_rs"),
                                                ("trees", "gbm_rs"))}})
        ac = pd.DataFrame(ac).set_index("terrain")
        ac.loc["difference"] = ac.iloc[1] - ac.iloc[0]
        ac.to_csv(OUT / "aspcurv.csv")

    md = ["# Terrain from coarser elevation (decision #131)", "",
          "CRPS skill (%) vs each run's own slope curve. Additive / trees.",
          ""]
    show = tab.copy()
    for c in show.columns:
        if show[c].dtype.kind == "f":
            show[c] = show[c].map(lambda v: f"{v:+.2f}")
    md += [show.T.to_markdown(), ""]
    if len(ac):
        md += ["## Aspect and curvature", "",
               ac.round(2).T.to_markdown(), ""]
    (OUT / "summary.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
