#!/usr/bin/env python3
"""
Two T1 checks that need the 1 m elevation (White Mountains, T1 v0 segments).

1. Segment length (plan sec. 8): "pick the length by checking how much slope
   still varies within a segment at each candidate". Along every 25 m and
   50 m walker trail segment we read the 1 m DEM every meter, take the local
   slope over a 10 m window at each meter, and measure how far it strays
   from the segment's own slope (RMS, in percentage points of grade).
   The other side of the trade-off: how many GPS points time each segment.

2. Slope noise: T1 v0 takes slope from the 5 m DEM. Was the rounded top of
   the slope-speed curve (9 Oct meeting) real, or 5 m noise? Recompute every
   segment's slope from the 1 m DEM and refit (95% intervals by trace).
   Also refit on 25 m segments: does the curve depend on segment length?

Result (9 Oct 2026): neither. 1 m and 5 m slopes differ by 0.3 points of
grade (median) and give the same curve; 25 m and 50 m give the same curve.
50 m stays the main length (twice the GPS points per segment); 25 m is the
robustness variant. Never filter segments by GPS point count: slow
traversals collect more points, so the filter keeps the slow ones.

The 1 m elevation is read along the straight line between a segment's two
ends (its chord); the two end elevations are exact, the profile in between
is approximate on curvy segments, so the profile part uses only segments
whose chord is >= 80% of their length.

Input:  data/t1_white_mountains/segments_L50.parquet, segments_L25.parquet,
        traces.csv; cache/dem1m/ (t2_prefetch_dem1m.py)
Output: results/t1_slope_check/numbers.json, fig_segment_length.png,
        fig_slope_1m_vs_5m.png
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer

import t1_variants as v
import t2_prefetch_dem1m as d1

DATA = Path("data/t1_white_mountains")
OUT = Path("results/t1_slope_check")
WINDOW_M = 10                 # local slope over 10 m
MIN_STRAIGHTNESS = 0.8        # chord / length, for the profile check
# reference palette (dataviz skill): slot 1 blue, slot 2 orange, gray ink
BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
TO_UTM = Transformer.from_crs(4326, d1.EPSG, always_xy=True)


def sample_1m(x, y):
    """Bilinear 1 m elevation at UTM x, y (NaN where no cell is on disk)."""
    z = np.full(len(x), np.nan)
    cx = (np.floor(x / d1.CELL_M) * d1.CELL_M).astype(np.int64)
    cy = (np.floor(y / d1.CELL_M) * d1.CELL_M).astype(np.int64)
    for (a, b), idx in pd.Series(np.arange(len(x))).groupby([cx, cy]) \
            .groups.items():
        if not d1.path(a, b).exists():
            continue
        g = d1.read(a, b)
        idx = np.asarray(idx)
        col = np.clip(x[idx] - a - 0.5, 0, d1.CELL_M - 1.001)
        row = np.clip(b + d1.CELL_M - y[idx] - 0.5, 0, d1.CELL_M - 1.001)
        c0, r0 = col.astype(int), row.astype(int)
        fx, fy = col - c0, row - r0
        z[idx] = (g[r0, c0] * (1 - fx) * (1 - fy) + g[r0, c0 + 1] * fx
                  * (1 - fy) + g[r0 + 1, c0] * (1 - fx) * fy
                  + g[r0 + 1, c0 + 1] * fx * fy)
    return z


def profiles(seg):
    """1 m elevation every meter along each chord.

    Returns (chord lengths, flat sample index -> segment, distance, z)."""
    x0, y0 = TO_UTM.transform(seg.lon0.to_numpy(), seg.lat0.to_numpy())
    x1, y1 = TO_UTM.transform(seg.lon1.to_numpy(), seg.lat1.to_numpy())
    chord = np.hypot(x1 - x0, y1 - y0)
    n = np.floor(chord).astype(int) + 2                 # 0, 1, ..., end
    sid = np.repeat(np.arange(len(seg)), n)
    start = np.r_[0, np.cumsum(n)[:-1]]
    k = np.arange(n.sum()) - np.repeat(start, n)
    dist = np.minimum(k, np.repeat(chord, n))           # last = the end
    f = dist / np.repeat(np.maximum(chord, 1e-9), n)
    x = np.repeat(x0, n) + f * np.repeat(x1 - x0, n)
    y = np.repeat(y0, n) + f * np.repeat(y1 - y0, n)
    return chord, sid, dist, sample_1m(x, y)


def within_variation(seg):
    """RMS of (10 m local slope - segment slope) inside each segment, in
    percentage points; NaN for curvy or too-short chords."""
    chord, sid, dist, z = profiles(seg)
    out = np.full(len(seg), np.nan)
    ends = np.full(len(seg), np.nan), np.full(len(seg), np.nan)
    starts = np.r_[0, np.nonzero(np.diff(sid))[0] + 1]
    stops = np.r_[starts[1:], len(sid)]
    for i, (a, b) in enumerate(zip(starts, stops)):
        zz, dd = z[a:b], dist[a:b]
        ends[0][i], ends[1][i] = zz[0], zz[-1]
        if chord[i] < seg.length_m.iloc[i] * MIN_STRAIGHTNESS or \
                chord[i] < WINDOW_M + 2 or np.isnan(zz).any():
            continue
        whole = (zz[-1] - zz[0]) / dd[-1]
        m = int(dd[-1]) - WINDOW_M + 1                  # 10 m windows
        local = (zz[WINDOW_M:WINDOW_M + m] - zz[:m]) / WINDOW_M
        out[i] = 100 * np.sqrt(np.mean((local - whole) ** 2))
    return out, ends[0], ends[1], chord


def tobler(s):
    return 6 * np.exp(-3.5 * np.abs(s + 0.05))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    traces = pd.read_csv(DATA / "traces.csv")
    hikers = set(traces.loc[traces.hiking_trace, "trace_id"])
    s50 = v.walker_trail_segments(pd.read_parquet(
        DATA / "segments_L50.parquet"), hikers)
    walkers = set(s50.trace_id)
    s25 = pd.read_parquet(DATA / "segments_L25.parquet")
    s25 = s25[s25.trace_id.isin(walkers) & (s25.way_class == "trail")
              & ~s25.suspect & s25.slope.notna()]
    nums = {}

    # ------------------------------------------------ 1. segment length
    for L, s in ((25, s25), (50, s50)):
        rms, z0, z1, chord = within_variation(s)
        s = s.assign(rms_pp=rms, z0_1m=z0, z1_1m=z1, chord_m=chord)
        if L == 50:
            s50 = s
        else:
            s25 = s
        ok = np.isfinite(rms)
        nums[f"L{L}"] = {
            "segments": int(len(s)), "profiled": int(ok.sum()),
            "within_rms_pp_median": float(np.median(rms[ok])),
            "within_rms_pp_p90": float(np.percentile(rms[ok], 90)),
            "share_rms_over_5pp": float(np.mean(rms[ok] > 5)),
            "gps_points_median": float(s.n_points.median()),
            "share_under_3_points": float(np.mean(s.n_points < 3))}

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for L, s, c in ((25, s25, BLUE), (50, s50, ORANGE)):
        r = np.sort(s.rms_pp.dropna().to_numpy())
        ax.plot(r, np.arange(1, len(r) + 1) / len(r), color=c, lw=2,
                label=f"{L} m segments: median {np.median(r):.1f} points; "
                      f"timed by {s.n_points.median():.0f} GPS points")
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 1)
    ax.set_xlabel("slope variation inside a segment\n(RMS of 10 m slope "
                  "minus the segment's slope, points of grade)")
    ax.set_ylabel("share of segments")
    ax.grid(color="#e4e3df", lw=0.6)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("How much does slope vary inside one segment? "
                 "(1 m DEM, White Mountains walkers)", fontsize=9)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_segment_length.png", dpi=170)
    plt.close(fig)

    # ------------------------------------------------ 2. 1 m vs 5 m slope
    s = s50[np.isfinite(s50.z0_1m) & np.isfinite(s50.z1_1m)].copy()
    s["slope_1m"] = (s.z1_1m - s.z0_1m) / s.length_m
    dz = 100 * (s.slope_1m - s.slope)
    nums["slope_1m_minus_5m_pp"] = {
        "median": float(dz.median()),
        "median_abs": float(dz.abs().median()),
        "p90_abs": float(dz.abs().quantile(0.9))}
    rng = np.random.default_rng(0)
    fits = {}
    for name, col in (("dem5m", "slope"), ("dem1m", "slope_1m")):
        t = s.assign(slope=s[col])
        v0, k, s0 = v.fit(t)
        lo, hi = np.percentile(v.boot(t, rng), [2.5, 97.5], axis=0)
        fits[name] = (v0, k, s0)
        nums[f"fit_{name}"] = {
            "v0": [v0, lo[0], hi[0]], "k": [k, lo[1], hi[1]],
            "peak_slope_pct": [-100 * s0, -100 * hi[2], -100 * lo[2]]}

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    grid = np.linspace(-0.4, 0.4, 161)
    edges = np.arange(-0.40, 0.4001, 0.02)
    mids = (edges[:-1] + edges[1:]) / 2
    ax.plot(100 * grid, tobler(grid), "--", color=MUTED, lw=1.4,
            label="Tobler (1993)")
    # the two curves coincide: draw 5 m wide and solid, 1 m thin and dashed
    for name, col, c, lab, ls, lw, mk in (
            ("dem5m", "slope", BLUE, "5 m DEM (T1 v0)", "-", 4, dict(
                marker="o", ms=5, mfc=BLUE, mec=BLUE)),
            ("dem1m", "slope_1m", ORANGE, "1 m DEM", "--", 1.6, dict(
                marker="o", ms=7, mfc="none", mec=ORANGE, mew=1.2))):
        b = pd.cut(s[col], edges)
        med = s.groupby(b, observed=False).speed_kmh.median().to_numpy()
        v0, k, s0 = fits[name]
        ax.plot(100 * mids, med, ls="none", **mk)
        ax.plot(100 * grid, v0 * np.exp(-k * np.abs(grid + s0)), color=c,
                ls=ls, lw=lw, label=f"{lab}: v0 {v0:.2f} km/h, k {k:.2f}, "
                                    f"peak {-100 * s0:+.1f}%")
    ax.set_xlabel("slope along direction of travel (%), + = uphill")
    ax.set_ylabel("speed (km/h); dots = median per 2% bin")
    ax.set_ylim(0, 6.5)
    ax.grid(color="#e4e3df", lw=0.6)
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
    ax.set_title(f"Same {len(s):,} segments, slope from the 5 m vs the 1 m "
                 f"DEM", fontsize=9)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_slope_1m_vs_5m.png", dpi=170)
    plt.close(fig)

    # does the curve depend on segment length? (and a trap: keeping only
    # segments timed by >= 3 GPS points keeps the SLOW traversals)
    for name, t in (("L25", s25), ("L25_min3points", s25[s25.n_points >= 3])):
        v0, k, s0 = v.fit(t)
        lo, hi = np.percentile(v.boot(t, rng), [2.5, 97.5], axis=0)
        nums[f"fit_{name}_dem5m"] = {
            "segments": int(len(t)), "v0": [v0, lo[0], hi[0]],
            "k": [k, lo[1], hi[1]],
            "peak_slope_pct": [-100 * s0, -100 * hi[2], -100 * lo[2]]}

    (OUT / "numbers.json").write_text(json.dumps(nums, indent=2))
    print(json.dumps(nums, indent=2))


if __name__ == "__main__":
    main()
