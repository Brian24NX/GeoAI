#!/usr/bin/env python3
"""
Draft figures for the IGARSS paper (paper/OUTLINE.md), IEEE column width
(3.5 in), from the harness results. Re-run after every harness run.

  fig_skill.png    CRPS skill vs the refitted slope curve, by model, for
                   new hikers (outing folds) and unseen regions (leave one
                   region out), with 95% bootstrap intervals
  fig_regions.png  per held-out region: terrain vs tags (additive arms),
                   sorted, with the count of regions where terrain wins

Input:  results/t3_harness_terrain5m/{metrics,skill_ci,loro_by_region}.csv
Output: ../paper/figures/
Run:    python make_paper_figures.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE / "results" / "t3_harness_terrain5m"
OUT = HERE.parent / "paper" / "figures"
BLUE, LIGHT, ORANGE, AQUA, GRAY = ("#2a78d6", "#9ec5f0", "#eb6834",
                                   "#1baf7a", "#9a9893")
plt.rcParams.update({"font.size": 7.5, "axes.titlesize": 8,
                     "axes.labelsize": 7.5, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "font.family": "DejaVu Sans"})

ROWS = [("Tobler (published)", "tobler"),
        ("Tags, additive", "lin_tags"),
        ("Tags, trees", "gbm_tags"),
        ("Terrain, additive", "lin_rs"),
        ("Terrain, trees", "gbm_rs"),
        ("Terrain + tags, additive", "lin_both"),
        ("Terrain + tags, trees", "gbm_both")]


def fig_skill():
    m = pd.read_csv(RES / "metrics.csv")
    ci = pd.read_csv(RES / "skill_ci.csv")
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    for j, (split, col, name) in enumerate(
            [("outing5", LIGHT, "new hikers"),
             ("loro", BLUE, "unseen region")]):
        mm = m[(m.split == split) & (m.subset == "all")].set_index("arm")
        cc = ci[ci.split == split].set_index("arm")
        for i, (_, arm) in enumerate(ROWS):
            y = i + (j - 0.5) * 0.36
            v = mm.loc[arm, "crps_skill_vs_slope_pct"]
            lo, hi = cc.loc[arm, ["skill_lo", "skill_hi"]]
            vis = max(v, -4.6)                      # Tobler: cut, labeled
            ax.barh(y, vis, height=0.34, color=col,
                    label=name if i == 0 else None, zorder=2)
            if v > -4.6:
                ax.plot([lo, hi], [y, y], color="#333", lw=0.8, zorder=3)
            else:
                ax.text(-4.5, y, f"{v:.0f}%", va="center", ha="left",
                        fontsize=6.5, color="white", zorder=4)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_yticks(range(len(ROWS)), [r[0] for r in ROWS])
    ax.invert_yaxis()
    ax.set_xlim(-4.6, 5.5)
    ax.set_xlabel("CRPS skill vs slope curve (%), with 95% CI")
    ax.grid(axis="x", color="#e4e3df", zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "fig_skill.png", dpi=300)


def fig_regions():
    b = pd.read_csv(RES / "loro_by_region.csv").pivot(
        index="region", columns="arm", values="crps_skill_vs_slope_pct")
    b = b.sort_values("lin_rs")
    names = {"wm": "White Mtns", "adk": "Adirondacks", "catskills":
             "Catskills", "greenmtn": "Green Mtns", "shenandoah":
             "Shenandoah", "smokies": "Smokies", "pisgah": "Pisgah",
             "frontrange": "Front Range", "wasatch": "Wasatch", "cascades":
             "Cascades", "gorge": "Col. Gorge", "olympic": "Olympic",
             "bayarea": "Bay Area", "sangabriel": "San Gabriels",
             "yosemite": "Yosemite", "tahoe": "Tahoe", "northshore":
             "North Shore"}
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    y = range(len(b))
    for i, (t_, r_) in enumerate(zip(b.lin_tags, b.lin_rs)):
        ax.plot([t_, r_], [i, i], color="#c9c8c3", lw=1, zorder=1)
    ax.scatter(b.lin_tags, y, s=14, color=ORANGE, label="tags", zorder=2)
    ax.scatter(b.lin_rs, y, s=14, color=BLUE, label="terrain", zorder=3)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_yticks(list(y), [names.get(r, r) for r in b.index])
    ax.set_xlabel("CRPS skill vs slope curve (%), region held out")
    wins = int((b.lin_rs > b.lin_tags).sum())
    ax.set_title(f"Terrain beats tags in {wins} of {len(b)} unseen regions",
                 fontsize=8)
    ax.grid(axis="x", color="#e4e3df", zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "fig_regions.png", dpi=300)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig_skill()
    fig_regions()
    print(f"wrote {OUT}/fig_skill.png, fig_regions.png")


if __name__ == "__main__":
    main()
