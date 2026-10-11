#!/usr/bin/env python3
"""
Map-matching QA (plan sec. 8 and 11: "expect to hand-inspect failures and
report a match rate").

Re-runs the T1 matching on the worst-matched hiking traces of a region and
draws each one over the OSM network: GPS points that matched a way in blue,
points that didn't in orange, trails dark gray, tracks and roads light gray.
Look at the pictures and say WHY each one failed.

Output: results/t1_match_qa/<region>/match_rate.json and qa_<trace>.png
Run:    python t1_match_qa.py [--region wm] [--n 10]
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gate1_audit as g
import regions
import t1_build_dataset as b

BLUE, ORANGE, INK, MUTED, FAINT = "#2a78d6", "#eb6834", "#0b0b0b", \
    "#52514e", "#c9c8c3"


def match_trace(tr):
    """(lat, lon, matched?) for every thinned point of one trace."""
    out = []
    for seg in tr["segments"]:
        for lat, lon, t in b.runs_of(seg):
            k = g.thin(t, b.THIN_S)
            if len(k) < 3:
                continue
            mlat, *_ = b.match_run(lat[k], lon[k])
            out.append(np.c_[lat[k], lon[k], ~np.isnan(mlat)])
    return np.vstack(out) if out else np.empty((0, 3))


def draw(ax, pts, title):
    lat, lon, ok = pts[:, 0], pts[:, 1], pts[:, 2].astype(bool)
    pad = 0.004
    w, e = lon.min() - pad, lon.max() + pad
    s, n = lat.min() - pad, lat.max() + pad
    for k, way in enumerate(b.W["ways"]):
        geo = [p for p in way.get("geometry") or [] if p]
        if not geo:
            continue
        la = np.array([p["lat"] for p in geo])
        lo = np.array([p["lon"] for p in geo])
        if lo.max() < w or lo.min() > e or la.max() < s or la.min() > n:
            continue
        c = b.W["cls"][k]
        if c == "trail":
            ax.plot(lo, la, color=MUTED, lw=1.0, zorder=1)
        elif c in ("track", "road"):
            ax.plot(lo, la, color=FAINT, lw=1.0, zorder=1)
    ax.scatter(lon[ok], lat[ok], s=4, color=BLUE, lw=0, zorder=2,
               label="matched")
    ax.scatter(lon[~ok], lat[~ok], s=6, color=ORANGE, lw=0, zorder=3,
               label="not matched")
    ax.set_xlim(w, e)
    ax.set_ylim(s, n)
    ax.set_aspect(1 / np.cos(np.radians((s + n) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=7.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="wm",
                    choices=sorted(regions.CANDIDATES))
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()
    key = args.region
    region, boxes = regions.region_name(key), regions.tiles(key)
    out = Path("results/t1_match_qa") / region
    out.mkdir(parents=True, exist_ok=True)
    tr = pd.read_csv(regions.data_dir(key) / "traces.csv")

    # the match rate, as the plan asks
    h = tr[tr.hiking_trace]
    rate = {
        "points_matched_all_traces": float(
            (tr.matched_share * tr.points_used).sum() / tr.points_used.sum()),
        "points_matched_hiking_traces": float(
            (h.matched_share * h.points_used).sum() / h.points_used.sum()),
        "hiking_traces": int(len(h)),
        "hiking_traces_under_90pct_matched": int((h.matched_share < 0.9)
                                                 .sum())}
    (out / "match_rate.json").write_text(json.dumps(rate, indent=2))
    print(rate)

    worst = h.sort_values("matched_share").head(args.n)
    b.init_worker(region, boxes)
    bbox = (min(x[1] for x in boxes), min(x[2] for x in boxes),
            max(x[3] for x in boxes), max(x[4] for x in boxes))
    lab = key if (worst.source == "lab original file").any() else None
    traces, _ = b.collect_traces(region, boxes, bbox, lab_key=lab)
    by_id = {t["trace_id"]: t for t in traces}
    cols = 4
    rows = int(np.ceil(len(worst) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 3.2 * rows))
    for ax, (_, r) in zip(np.ravel(axes), worst.iterrows()):
        pts = match_trace(by_id[r.trace_id])
        draw(ax, pts, f"{r.trace_id}: {100 * r.matched_share:.0f}% matched")
    for ax in np.ravel(axes)[len(worst):]:
        ax.axis("off")
    np.ravel(axes)[0].legend(fontsize=7, loc="lower left", markerscale=3)
    fig.suptitle(f"{region}: the {len(worst)} worst-matched hiking traces "
                 "(blue matched, orange not; dark lines = OSM trails)",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "qa_worst.png", dpi=150)
    print(f"saved {out / 'qa_worst.png'}")


if __name__ == "__main__":
    main()
