#!/usr/bin/env python3
"""
T1 across regions: one table and two figures for everything built so far.

For every region with a finished T1 build (data/t1_<region>/ with modes.csv),
the dataset numbers and the walking slope-speed fit (95% intervals by
resampling outings), plus the fit for all regions pooled.

Output: results/t1_summary/regions.csv
        results/t1_summary/fig_regions_fit.png   v0 and k per region vs Tobler
        results/t1_summary/fig_regions_size.png  how much data each region has
Run:    python t1_summary.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import regions
import t1_variants as v

OUT = Path("results/t1_summary")
# reference palette (dataviz skill): one series -> slot 1 blue; gray ink
BLUE, INK, MUTED, GRID = "#2a78d6", "#0b0b0b", "#52514e", "#e4e3df"


def region_row(key, rng):
    d = regions.data_dir(key)
    seg = pd.read_parquet(d / "segments_L50.parquet")
    tr = pd.read_csv(d / "traces.csv")
    modes = pd.read_csv(d / "modes.csv")
    hikers = set(tr.loc[tr.hiking_trace, "trace_id"])
    walk = v.walker_trail_segments(seg, hikers, modes)
    hike = seg[seg.trace_id.isin(hikers) & (seg.way_class == "trail")]
    h = tr[tr.hiking_trace]
    m = modes[modes.trace_id.isin(hikers)]["mode"].value_counts()
    row = {"region": key, "label": regions.CANDIDATES[key][0],
           "sources": "lab only" if set(tr.source) == {"lab original file"}
           else "API + lab",
           "traces": len(tr), "hiking_traces": len(h),
           "outings": h.outing_id.nunique(),
           "named_uploaders": h.loc[h.identifiable, "uploader"].nunique(),
           "walking_traces": walk.trace_id.nunique(),
           "walking_outings": walk.outing_id.nunique(),
           "walking_segments": len(walk),
           "walking_km": len(walk) * 0.05,
           "walking_hours": walk.moving_s.sum() / 3600,
           "bike_ski_traces": int(m.get("bike/ski", 0)),
           "run_fast_traces": int(m.get("run", 0) + m.get("fast", 0)),
           "match_rate_pct": 100 * (h.matched_share * h.points_used).sum()
           / h.points_used.sum(),
           "sac_scale_pct": 100 * hike.tag_sac_scale.notna().mean(),
           "surface_pct": 100 * hike.tag_surface.notna().mean(),
           "blocks_10km": walk.block_10km.nunique()
           if "block_10km" in walk else np.nan}
    if walk.outing_id.nunique() >= 10:
        v0, k, s0 = v.fit(walk)
        lo, hi = np.percentile(v.boot(walk, rng), [2.5, 97.5], axis=0)
        row.update(v0=v0, v0_lo=lo[0], v0_hi=hi[0], k=k, k_lo=lo[1],
                   k_hi=hi[1], peak_pct=-100 * s0)
    return row, walk.assign(region=key)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    rows, walks = [], []
    for key in regions.CANDIDATES:
        if (regions.data_dir(key) / "modes.csv").exists():
            r, w = region_row(key, rng)
            rows.append(r)
            walks.append(w)
    tab = pd.DataFrame(rows)
    pooled = pd.concat(walks, ignore_index=True)
    v0, k, s0 = v.fit(pooled)
    lo, hi = np.percentile(v.boot(pooled, rng), [2.5, 97.5], axis=0)
    total = {"region": "ALL", "label": f"all {len(tab)} regions pooled",
             **{c: tab[c].sum() for c in ("traces", "hiking_traces",
                                          "outings", "walking_traces",
                                          "walking_outings",
                                          "walking_segments", "walking_km",
                                          "walking_hours", "bike_ski_traces",
                                          "run_fast_traces")},
             "v0": v0, "v0_lo": lo[0], "v0_hi": hi[0], "k": k, "k_lo": lo[1],
             "k_hi": hi[1], "peak_pct": -100 * s0}
    tab = pd.concat([tab, pd.DataFrame([total])], ignore_index=True)
    tab.to_csv(OUT / "regions.csv", index=False)
    show = ["region", "sources", "hiking_traces", "outings", "walking_outings",
            "walking_segments", "walking_hours", "bike_ski_traces", "v0",
            "v0_lo", "v0_hi", "k", "peak_pct"]
    print(tab[show].round(2).to_string(index=False))

    # --- figure 1: v0 and k per region (dot + 95% interval), Tobler as ref
    t = tab.dropna(subset=["v0"]).iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(9, 0.45 * len(t) + 1.6),
                             sharey=True)
    y = np.arange(len(t))
    for ax, (col, lo_, hi_, tob, lab) in zip(axes, (
            ("v0", "v0_lo", "v0_hi", 6.0, "peak speed v0 (km/h)"),
            ("k", "k_lo", "k_hi", 3.5, "slope sensitivity k"))):
        ax.errorbar(t[col], y, xerr=[t[col] - t[lo_], t[hi_] - t[col]],
                    fmt="o", color=BLUE, ms=6, capsize=3, lw=1.6)
        ax.axvline(tob, color=MUTED, ls="--", lw=1.2)
        ax.text(tob, len(t) - 0.4, " Tobler", color=MUTED, fontsize=8,
                ha="left", va="center")
        ax.set_xlabel(lab)
        ax.grid(axis="x", color=GRID, lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([f"{r.label} ({int(r.walking_outings)} "
                             f"outings{', lab only' if r.sources == 'lab only' else ''})"
                             for r in t.itertuples()],
                            fontsize=8)
    fig.suptitle("Walking slope-speed curve by region (95% intervals, "
                 "resampling outings)", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig_regions_fit.png", dpi=170)
    plt.close(fig)

    # --- figure 2: how much walking data each region has
    t = tab[tab.region != "ALL"].sort_values("walking_hours")
    fig, ax = plt.subplots(figsize=(7, 0.4 * len(t) + 1.4))
    ax.barh(np.arange(len(t)), t.walking_hours, color=BLUE, height=0.6)
    for i, r in enumerate(t.itertuples()):
        ax.text(r.walking_hours, i, f"  {int(r.walking_outings)} outings, "
                f"{r.walking_km:,.0f} km", va="center", fontsize=8,
                color=INK)
    ax.set_yticks(np.arange(len(t)))
    ax.set_yticklabels(t.label, fontsize=8)
    ax.set_xlabel("moving hours of walking on trails")
    ax.set_xlim(0, t.walking_hours.max() * 1.45)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("T1 walking data per region", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig_regions_size.png", dpi=170)
    plt.close(fig)
    print(f"saved {OUT}/")


if __name__ == "__main__":
    main()
