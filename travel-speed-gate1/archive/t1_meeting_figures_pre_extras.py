#!/usr/bin/env python3
"""
Figures and numbers for the 9 Oct 2026 meeting, from the T1 dataset.

  fig_t1_dataset.png        every hiking trail segment in the region
  fig_t1_slope_speed.png    slope vs speed (T1 segments) against Tobler,
                            with bootstrap bands (resampling whole hikes)
  fig_t1_stop_rules.png     do the results survive every stop rule?
  fig_t1_out_and_back.png   Q3 preview: same hiker, same trail, up vs down
  meeting_numbers.json      every number quoted in the meeting notes

Run after t1_build_dataset.py and t1_variants.py:
    python t1_meeting_figures.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

import t1_download as t1
import t1_variants as v

DATA = Path("data/t1_white_mountains")
OUT = Path("../meeting_plots/oct9")
plt.rcParams.update({"font.size": 9})
BLUE, ORANGE, GREEN = "#185FA5", "#D85A30", "#1D9E75"


def tobler(s):
    return 6 * np.exp(-3.5 * np.abs(s + 0.05))


def main():
    import argparse
    global DATA, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true",
                    help="test on data/t1_sample, write to a scratch folder")
    args = ap.parse_args()
    if args.sample:
        DATA, OUT = Path("data/t1_sample"), Path("data/t1_sample/figs")
    OUT.mkdir(parents=True, exist_ok=True)
    seg = pd.read_parquet(DATA / "segments_L50.parquet")
    traces = pd.read_csv(DATA / "traces.csv")
    hikers = set(traces.loc[traces.hiking_trace, "trace_id"])
    hike = seg[seg.trace_id.isin(hikers) & (seg.way_class == "trail")]
    walk = v.walker_trail_segments(seg, hikers)
    nums = {}

    # ---------------------------------------------------------- the dataset
    h_tr = traces[traces.hiking_trace]
    nums["dataset"] = {
        "traces_processed": int(len(traces)),
        "hiking_traces": int(len(h_tr)),
        "named_uploaders": int(h_tr.loc[h_tr.identifiable, "uploader"]
                               .nunique()),
        "anonymous_hiking_traces": int((~h_tr.identifiable).sum()),
        "full_gpx_hiking_traces": int((h_tr.source == "original GPX").sum()),
        "trail_segments_50m": int(len(hike)),
        "trail_km_traversed": float(len(hike) * 0.05),
        "trail_hours_moving": float(hike.moving_s.sum() / 3600),
        "distinct_osm_trail_ways": int(hike.osm_way_id.nunique()),
        "median_matched_share": float(traces.matched_share.median()),
        "median_match_err_m": float(hike.match_err_m.median()),
        "suspect_pct": float(100 * hike.suspect.mean()),
        "years": f"{int(hike.year.min())}-{int(hike.year.max())}",
        "winter_share_pct": float(100 * hike.loc[
            hike.day_of_year.isin(list(range(1, 91)) +
                                  list(range(335, 367))),
            "moving_s"].sum() / hike.moving_s.sum()),
        "foot_only_pct": float(100 * (hike.permission == "foot-only")
                               .mean()),
        "sac_scale_tagged_pct": float(100 * hike.tag_sac_scale.notna()
                                      .mean()),
        "surface_tagged_pct": float(100 * hike.tag_surface.notna().mean()),
        "width_tagged_pct": float(100 * hike.tag_width.notna().mean()),
    }
    d = nums["dataset"]
    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    for tile in t1.tiles():
        _, w, s, e, n = tile
        ax.plot([w, e, e, w, w], [s, s, n, n, s], color="#dddddd", lw=0.6,
                zorder=0)
    lines = np.stack([np.c_[hike.lon0, hike.lat0],
                      np.c_[hike.lon1, hike.lat1]], axis=1)
    lc = LineCollection(lines, cmap="plasma", norm=plt.Normalize(0, 5),
                        linewidths=1.0)
    lc.set_array(hike.speed_kmh.clip(0, 5).to_numpy())
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label("speed on the segment (km/h)")
    ax.set_xlim(t1.WEST, t1.EAST)
    ax.set_ylim(t1.SOUTH, t1.NORTH)
    ax.set_aspect(1 / np.cos(np.radians((t1.SOUTH + t1.NORTH) / 2)))
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title(f"T1 dataset, White Mountains: {d['hiking_traces']} hikes,"
                 f" {d['trail_segments_50m']:,} trail segments of 50 m "
                 f"(~{d['trail_km_traversed']:,.0f} km walked, "
                 f"{d['trail_hours_moving']:,.0f} moving hours)",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig_t1_dataset.png", dpi=170)
    plt.close(fig)

    # ------------------------------------------------ slope vs speed + fit
    rng = np.random.default_rng(1)
    v0, k, s0 = v.fit(walk)
    bs = v.boot(walk, rng)
    lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
    nums["fit_default_rule"] = {
        "walker_traces": int(walk.trace_id.nunique()),
        "segments": int(len(walk)), "v0_kmh": v0, "v0_ci": [lo[0], hi[0]],
        "k": k, "k_ci": [lo[1], hi[1]], "peak_slope_pct": -100 * s0,
        "peak_ci_pct": [-100 * hi[2], -100 * lo[2]]}
    edges = np.arange(-0.41, 0.4101, 0.02)
    mid = (edges[:-1] + edges[1:]) / 2
    idx = np.digitize(walk.slope, edges) - 1
    med, q1, q3, cnt = [], [], [], []
    for bi in range(len(mid)):
        sp = walk.speed_kmh[idx == bi]
        cnt.append(len(sp))
        med.append(sp.median() if len(sp) >= 30 else np.nan)
        q1.append(sp.quantile(0.25) if len(sp) >= 30 else np.nan)
        q3.append(sp.quantile(0.75) if len(sp) >= 30 else np.nan)
    grid = np.linspace(-0.4, 0.4, 401)
    curves = np.array([b0 * np.exp(-bk * np.abs(grid + bs0))
                       for b0, bk, bs0 in bs])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.3))
    a1.fill_between(100 * mid, q1, q3, color=BLUE, alpha=0.15,
                    label="middle 50% of segments")
    a1.plot(100 * mid, med, "o-", color=BLUE, ms=3,
            label="median per 2% slope bin")
    a1.fill_between(100 * grid, *np.percentile(curves, [2.5, 97.5], axis=0),
                    color=GREEN, alpha=0.25)
    a1.plot(100 * grid, v0 * np.exp(-k * np.abs(grid + s0)), color=GREEN,
            lw=1.6, label=f"fit: v0 {v0:.1f} km/h, k {k:.1f} "
                          f"(95% band, resampling hikes)")
    a1.plot(100 * grid, tobler(grid), "k--", lw=1.4,
            label="Tobler (1993): v0 6.0, k 3.5")
    a1.set_xlabel("slope along direction of travel (%), + = uphill")
    a1.set_ylabel("speed (km/h)")
    a1.set_ylim(0, 6.6)
    a1.legend(fontsize=7.5)
    a1.set_title(f"T1 segments: {len(walk):,} trail segments of 50 m from "
                 f"{walk.trace_id.nunique()} walking hikes", fontsize=9)
    x = np.abs(walk.slope + 0.05)
    e2 = np.arange(0, 0.46, 0.02)
    j = np.digitize(x, e2) - 1
    for side, mask, mk in [("uphill side", walk.slope > -0.05, "o"),
                           ("downhill side", walk.slope <= -0.05, "s")]:
        pts = [((e2[b] + e2[b + 1]) / 2,
                np.log(walk.speed_kmh[(j == b) & mask]).median())
               for b in range(len(e2) - 1) if ((j == b) & mask).sum() >= 30]
        if pts:
            px, py = zip(*pts)
            a2.plot(px, py, mk, color=BLUE,
                    mfc=BLUE if mk == "o" else "white", ms=5, ls="",
                    label=side)
    xx = np.linspace(0, 0.45, 50)
    a2.plot(xx, np.log(6) - 3.5 * xx, "k--", lw=1.4, label="Tobler")
    a2.plot(xx, np.log(v0) - k * xx, color=GREEN, lw=1.4, label="fit")
    a2.set_xlabel("|slope + 0.05|")
    a2.set_ylabel("ln(speed in km/h)")
    a2.set_title("Plan sec. 9 diagnostic: a straight line if Tobler's form "
                 "holds", fontsize=9)
    a2.legend(fontsize=7.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig_t1_slope_speed.png", dpi=170)
    plt.close(fig)

    # --------------------------------------------------- stop-rule check
    sens = pd.read_csv(DATA / "stop_rule_sensitivity.csv")
    nums["stop_rules"] = sens.to_dict(orient="records")
    names = {"window60_10": "draft: 60 s, <10 m", "window30_5":
             "stricter: 30 s, <5 m", "window90_15": "looser: 90 s, <15 m",
             "crude05": "plan's crude: <0.5 km/h"}
    labels = [names.get(r, r) for r in sens.rule]
    y = np.arange(len(sens))
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.0), sharey=True)
    axes[0].barh(y, sens.time_removed_pct, color="#9e9e9e")
    axes[0].set_xlabel("% of time removed as stops")
    for ax, col, ref, title in [(axes[1], "v0", 6.0, "peak speed v0 (km/h)"),
                                (axes[2], "k", 3.5, "slope sensitivity k")]:
        ax.errorbar(sens[f"{col}_kmh" if col == "v0" else col], y,
                    xerr=[sens[f"{col}_kmh" if col == "v0" else col]
                          - sens[f"{col}_lo"],
                          sens[f"{col}_hi"] - sens[f"{col}_kmh"
                                                    if col == "v0" else col]],
                    fmt="o", color=GREEN, capsize=3)
        ax.axvline(ref, color="k", ls="--", lw=1)
        ax.text(ref, len(sens) - 0.45, "Tobler ", fontsize=7, va="top",
                ha="right")
        ax.set_xlabel(title)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels)
    fig.suptitle("Do the results survive the choice of stop rule? "
                 "(95% intervals from resampling whole hikes)", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig_t1_stop_rules.png", dpi=170)
    plt.close(fig)

    # --------------------------------- Q3 preview: out-and-back pairs
    pairs = []
    sw = walk[walk.way_dir != 0]
    for (tid, wid), d in sw.groupby(["trace_id", "osm_way_id"]):
        if d.way_dir.nunique() < 2:
            continue
        a = d[d.way_dir == 1]
        b_ = d[d.way_dir == -1]
        if len(a) < 2 or len(b_) < 2:
            continue
        sa, sb = a.slope.mean(), b_.slope.mean()
        va = a.length_m.sum() / a.moving_s.sum() * 3.6
        vb = b_.length_m.sum() / b_.moving_s.sum() * 3.6
        up, dn = ((va, sa), (vb, sb)) if sa > sb else ((vb, sb), (va, sa))
        grade = (abs(sa) + abs(sb)) / 2
        if grade < 0.03 or up[1] <= 0 or dn[1] >= 0:
            continue
        pairs.append({"trace_id": tid, "way": wid, "grade": grade,
                      "v_up": up[0], "v_down": dn[0],
                      "segments": len(a) + len(b_)})
    pairs = pd.DataFrame(pairs)
    nums["out_and_back"] = {
        "pairs": int(len(pairs)),
        "hikers": int(pairs.trace_id.nunique()) if len(pairs) else 0,
        "median_up_kmh": float(pairs.v_up.median()) if len(pairs) else None,
        "median_down_kmh": float(pairs.v_down.median()) if len(pairs)
        else None,
        "share_down_faster_pct": float(100 * (pairs.v_down > pairs.v_up)
                                       .mean()) if len(pairs) else None}
    if len(pairs):
        fig, ax = plt.subplots(figsize=(6.2, 4.3))
        ratio = np.log2(pairs.v_down / pairs.v_up)
        ax.scatter(100 * pairs.grade, ratio, s=10 + pairs.segments,
                   color=BLUE, alpha=0.6, label="one trail, one hiker, "
                                                 "both directions")
        gg = np.linspace(0.03, max(0.45, pairs.grade.max()), 100)
        ax.plot(100 * gg, np.log2(tobler(-gg) / tobler(gg)), "k--",
                label="Tobler's prediction")
        ax.axhline(0, color="#999999", lw=0.8)
        ax.set_xlabel("trail grade (%)")
        ax.set_ylabel("log2(speed down / speed up)\n(+1 = down twice as "
                      "fast)")
        ax.set_title(f"Q3 preview: {len(pairs)} out-and-back pairs from "
                     f"{pairs.trace_id.nunique()} hikes", fontsize=9)
        ax.legend(fontsize=7.5)
        fig.tight_layout()
        fig.savefig(OUT / "fig_t1_out_and_back.png", dpi=170)
        plt.close(fig)

    (OUT / "meeting_numbers.json").write_text(json.dumps(nums, indent=2,
                                                         default=float))
    print(json.dumps(nums, indent=2, default=float))


if __name__ == "__main__":
    main()
