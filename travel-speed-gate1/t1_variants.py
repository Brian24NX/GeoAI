#!/usr/bin/env python3
"""
Stop-rule sensitivity check (semester plan sec. 8).

The stop rule "will move your headline numbers more than any model change",
and it isn't validated by hand yet. So instead of trusting one rule, rebuild
the 50 m segments under every rule in t1_build_dataset.STOP_RULES -- from the
saved matched points, no re-matching -- and report how much the results move.

Output (data/t1_white_mountains/):
  segments_L50__<rule>.parquet   one table per stop rule
  stop_rule_sensitivity.csv      time removed and fitted curve per rule

Run after t1_build_dataset.py:  python t1_variants.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

import regions
import t1_build_dataset as b
import t1_download as t1

DATA = Path("data/t1_white_mountains")
WALKER_MAX_KMH = 7.0          # per-trace median speed cap (walkers only)
N_BOOT = 200                  # bootstrap resamples (by trace)
LAYERS = (t1.REGION, t1.tiles())  # (region, boxes) for the elevation grids


def rebuild(points, rule, L=50.0):
    rows, stopped_s, total_s = [], 0.0, 0.0
    for (tid, piece), d in points.groupby(["trace_id", "piece"], sort=False):
        d = d.sort_values("t")
        lat, lon, t = d.lat.to_numpy(), d.lon.to_numpy(), d.t.to_numpy()
        stopped = b.stop_mask(lat, lon, t, rule)
        dt = np.diff(t)
        stopped_s += dt[stopped].sum()
        total_s += dt.sum()
        p = {"lat": lat, "lon": lon, "t": t, "mlat": d.mlat.to_numpy(),
             "mlon": d.mlon.to_numpy(), "err": d.match_err_m.to_numpy(),
             "way": d.way_index.to_numpy().astype(int),
             "direction": d.direction.to_numpy(), "stopped": stopped,
             "native_dt": float(d.native_dt.iloc[0])}
        rows += b.segments_of_piece(p, L, {"trace_id": tid, "piece": piece})
    seg = b.attributes(pd.DataFrame(rows))
    seg = b.add_elevation(seg, b.dem_pieces(*LAYERS))
    return seg, stopped_s / total_s if total_s else np.nan


def walker_trail_segments(seg, hikers, modes=None):
    """Trail segments of walking hikes. Walking = t1_modes.py's mode "walk"
    when given (anchored on foot-only trails; bikes and skis out), else the
    T1 v0 stand-in: trace median speed <= WALKER_MAX_KMH."""
    s = seg[seg.trace_id.isin(hikers) & (seg.way_class == "trail")
            & ~seg.suspect & seg.slope.notna()]
    if modes is not None:
        return s[s.trace_id.isin(modes.loc[modes["mode"] == "walk",
                                           "trace_id"])]
    med = s.groupby("trace_id").speed_kmh.median()
    return s[s.trace_id.isin(med[med <= WALKER_MAX_KMH].index)]


def fit(s):
    """ln v = ln v0 - k |slope + s0|, s0 by grid; returns v0, k, s0."""
    x, y = s.slope.to_numpy(), np.log(s.speed_kmh.to_numpy())
    best = None
    for s0 in np.arange(-0.10, 0.20001, 0.005):
        A = np.c_[np.ones_like(x), -np.abs(x + s0)]
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = float(np.sum((A @ coef - y) ** 2))
        if best is None or sse < best[0]:
            best = (sse, s0, coef)
    _, s0, (ln_v0, k) = best
    return float(np.exp(ln_v0)), float(k), float(s0)


def unit(s):
    """Resampling unit: the outing (one hike, all its phones) when the build
    has it, else the trace."""
    return "outing_id" if "outing_id" in s and s.outing_id.notna().all() \
        else "trace_id"


def boot(s, rng):
    """Bootstrap by OUTING / TRACE: points within a hike are correlated, and
    two phones on one hike are one sample (plan s.10)."""
    groups = {t: d for t, d in s.groupby(unit(s))}
    ids = list(groups)
    out = []
    for _ in range(N_BOOT):
        pick = rng.choice(ids, size=len(ids), replace=True)
        out.append(fit(pd.concat([groups[i] for i in pick])))
    return np.array(out)


def main():
    import argparse
    import gate1_audit as g
    global DATA
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--region", default="wm",
                    choices=sorted(regions.CANDIDATES))
    args = ap.parse_args()
    global LAYERS
    if args.sample:
        DATA = Path("data/t1_sample")
        LAYERS = ("white_mountains", g.REGIONS["white_mountains"])
    else:
        DATA = regions.data_dir(args.region)
        LAYERS = (regions.region_name(args.region),
                  regions.tiles(args.region))
    b.init_layers(*LAYERS)
    points = pd.read_parquet(DATA / "points.parquet")
    traces = pd.read_csv(DATA / "traces.csv")
    hikers = set(traces.loc[traces.hiking_trace, "trace_id"])
    modes = pd.read_csv(DATA / "modes.csv") if (DATA / "modes.csv").exists() \
        else None
    print("walkers:", "t1_modes.py" if modes is not None else
          f"median <= {WALKER_MAX_KMH} km/h")
    rng = np.random.default_rng(0)
    rows = []
    for rule in b.STOP_RULES:
        seg, removed = rebuild(points, rule)
        seg["hiking_trace"] = seg.trace_id.isin(hikers)
        seg.to_parquet(DATA / f"segments_L50__{rule}.parquet", index=False)
        s = walker_trail_segments(seg, hikers, modes)
        v0, k, s0 = fit(s)
        bs = boot(s, rng)
        lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
        rows.append({"rule": rule, "spec": str(b.STOP_RULES[rule]),
                     "time_removed_pct": 100 * removed,
                     "walker_traces": s.trace_id.nunique(),
                     "segments": len(s),
                     "median_speed_kmh": s.speed_kmh.median(),
                     "v0_kmh": v0, "v0_lo": lo[0], "v0_hi": hi[0],
                     "k": k, "k_lo": lo[1], "k_hi": hi[1],
                     "peak_slope_pct": -100 * s0,
                     "peak_lo": -100 * hi[2], "peak_hi": -100 * lo[2]})
        r = rows[-1]
        print(f"{rule:12s} removed {r['time_removed_pct']:5.1f}% | "
              f"{r['walker_traces']} traces, {r['segments']:,} segs | "
              f"v0 {v0:.2f} [{lo[0]:.2f}, {hi[0]:.2f}]  "
              f"k {k:.2f} [{lo[1]:.2f}, {hi[1]:.2f}]  "
              f"peak {-100 * s0:+.1f}%")
    pd.DataFrame(rows).to_csv(DATA / "stop_rule_sensitivity.csv",
                              index=False)
    print(f"saved {DATA / 'stop_rule_sensitivity.csv'}")


if __name__ == "__main__":
    main()
