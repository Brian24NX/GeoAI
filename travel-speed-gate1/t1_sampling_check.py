#!/usr/bin/env python3
"""
Why do sparse traces read slow? Decision #101: walking traces with more than
10 s between GPS points are ~10% slower on flat ground than traces logged
every 2-10 s, and show fewer stops. Two suspects, both in how T1 measures
moving speed:
  - hidden stops: the stop rule (a step is stopped if the point 60 s later
    is < 10 m away) sees fewer stopped seconds when points are far apart,
    so short pauses count as moving time;
  - cut corners: distance is the straight line between consecutive matched
    points, which cuts switchbacks when points are far apart.
Test: take dense walking traces (device interval <= 5 s; T1 keeps points
>= 5 s apart), thin them to 10, 20 and 30 s, and recompute moving time and
matched distance with T1's own stop rule. Same walks; only the sampling
changes, so any change in speed is a measurement effect.

Then the real traces: flat-ground speed by the trace's own interval,
relative to traces logged every <= 5 s in the same region, next to the
simulated ratios; and the slope curve fitted with and without traces logged
every > 10 s.

Input:  data/t1_<region>/points.parquet, traces.csv, modes.csv;
        data/t1_all/segments_L50.parquet
Output: results/t1_sampling_check/ by_trace.csv, summary.json,
        observed_by_interval.csv, fig_sampling.png
Run (cluster): python t1_sampling_check.py   (--observed-only: second part;
               --figure: only redraw the figure from the results)
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import gate1_audit as g
import regions
import t1_build_dataset as b

OUT = Path("results/t1_sampling_check")
RATES = [5, 10, 20, 30]           # s between kept points; 5 = T1 as built
MAX_NATIVE = 5.0                  # dense: the device logged every <= 5 s
B = 1000


def measure(p, rate):
    """Moving distance (matched, stopped steps excluded), moving and stopped
    time of one matched piece kept at >= rate s between points."""
    t = p.t.to_numpy()
    idx = np.arange(len(t)) if rate <= 5 else \
        np.unique(np.r_[g.thin(t, rate), len(t) - 1])
    if len(idx) < 3:
        return None
    t = t[idx]
    lat, lon = p.lat.to_numpy()[idx], p.lon.to_numpy()[idx]
    mlat, mlon = p.mlat.to_numpy()[idx], p.mlon.to_numpy()[idx]
    stopped = b.stop_mask(lat, lon, t, rule=b.DEFAULT_STOP_RULE)
    dt = np.diff(t)
    d = g.haversine_m(mlat[:-1], mlon[:-1], mlat[1:], mlon[1:])
    return {"dist_m": float(d[~stopped].sum()), "chord_m": float(d.sum()),
            "moving_s": float(dt[~stopped].sum()),
            "stopped_s": float(dt[stopped].sum())}


def dense_walkers(key):
    d = regions.data_dir(key)
    if not (d / "points.parquet").exists() or not (d / "modes.csv").exists():
        return None
    tr = pd.read_csv(d / "traces.csv")
    md = pd.read_csv(d / "modes.csv")
    walk = set(md.loc[md["mode"] == "walk", "trace_id"]) & set(
        tr.loc[tr.hiking_trace, "trace_id"])
    pts = pd.read_parquet(d / "points.parquet",
                          columns=["trace_id", "piece", "t", "lat", "lon",
                                   "mlat", "mlon", "native_dt"])
    pts = pts[pts.trace_id.isin(walk) & pts.mlat.notna()]
    nat = pts.groupby("trace_id").native_dt.median()
    return pts[pts.trace_id.isin(nat[nat <= MAX_NATIVE].index)]


IV_BINS = [0, 5, 10, 15, 25, 40, np.inf]


def figure():
    """Measured speed vs seconds between GPS points: the same dense walks
    thinned (line) and the real traces at each interval (dots)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    s = json.loads((OUT / "summary.json").read_text())
    obs = pd.read_csv(OUT / "observed_by_interval.csv")
    rates = sorted(int(r) for r in s["rates"])
    sim = [100 * (s["rates"][str(r)]["speed_ratio"] - 1) for r in rates]
    lo = [100 * (s["rates"][str(r)]["speed_ratio_ci"][0] - 1) for r in rates]
    hi = [100 * (s["rates"][str(r)]["speed_ratio_ci"][1] - 1) for r in rates]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.fill_between(rates, lo, hi, color="#2a78d6", alpha=0.2, lw=0)
    ax.plot(rates, sim, "o-", color="#2a78d6", lw=2,
            label="same dense walks, thinned (simulated)")
    ax.scatter(obs.median_interval_s, 100 * (obs.flat_speed_ratio - 1),
               s=12 + obs.traces / 6, color="#eb6834", zorder=3,
               label="real traces at that interval (flat ground)")
    for r in obs.itertuples():
        ax.annotate(f"{r.traces}", (r.median_interval_s,
                                    100 * (r.flat_speed_ratio - 1)),
                    xytext=(7, -3), textcoords="offset points", fontsize=7,
                    color="#52514e", va="top")
    ax.axhline(0, color="#52514e", lw=0.8)
    ax.set_xscale("log")
    ax.minorticks_off()
    ax.set_xticks([2, 5, 10, 20, 30, 70], ["2", "5", "10", "20", "30", "70"])
    ax.set_xlabel("seconds between GPS points (log scale)")
    ax.set_ylabel("measured speed vs dense traces (%)")
    ax.set_title("Sparse traces read slow: how speed is measured\n"
                 "(dot labels: traces)", fontsize=9)
    ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    ax.grid(color="#e4e3df")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_sampling.png", dpi=170)


def observed():
    """Real traces by recording interval, and the curve without the
    sparse ones."""
    import t1_findings as tf
    s = pd.read_parquet("data/t1_all/segments_L50.parquet",
                        columns=["analysis_walk", "region", "trace_id",
                                 "slope", "speed_kmh", "native_interval_s"])
    w = s[s.analysis_walk & (s.speed_kmh > 0)
          & s.slope.between(-0.6, 0.6)].copy()
    w["iv"] = pd.cut(w.native_interval_s, IV_BINS)
    f = w[w.slope.abs() < 0.05]
    med = f.groupby(["region", "iv"], observed=True).agg(
        median=("speed_kmh", "median"), segments=("speed_kmh", "size"),
        traces=("trace_id", "nunique"),
        interval=("native_interval_s", "median")).reset_index()
    first = med.iv.cat.categories[0]
    ref = med[med.iv == first].set_index("region")["median"]
    med["ratio"] = med["median"] / med.region.map(ref)
    med = med.dropna(subset=["ratio"])
    rows = []
    for iv, d in med.groupby("iv", observed=True):
        rows.append({"interval_bin_s": str(iv),
                     "median_interval_s": float(np.average(
                         d.interval, weights=d.segments)),
                     "regions": int(len(d)), "traces": int(d.traces.sum()),
                     "flat_segments": int(d.segments.sum()),
                     "flat_speed_ratio": float(np.average(
                         d.ratio, weights=d.segments))})
    obs = pd.DataFrame(rows)
    obs.to_csv(OUT / "observed_by_interval.csv", index=False)
    print(obs.round(3).to_string(index=False))
    curve = {}
    for name, d in [("all", w), ("interval_le10s", w[w.native_interval_s
                                                    <= 10])]:
        p = tf.fit_form("smooth_asym", d.slope.to_numpy(),
                        np.log(d.speed_kmh.to_numpy()))
        curve[name] = {"segments": int(len(d)),
                       "peak_kmh": float(np.exp(p[0])),
                       "peak_slope_pct": float(-100 * p[3]),
                       "k_up": float(p[1]), "k_down": float(p[2]),
                       "flat_median_kmh": float(d.speed_kmh[
                           d.slope.abs() < 0.05].median())}
    print(json.dumps(curve, indent=1))
    return obs, curve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--observed-only", action="store_true")
    ap.add_argument("--figure", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.figure:
        figure()
        return
    if args.observed_only:
        obs, curve = observed()
        f = OUT / "summary.json"
        summ = json.loads(f.read_text()) if f.exists() else {}
        summ.update({"observed": obs.round(4).to_dict("records"),
                     "curve": curve})
        f.write_text(json.dumps(summ, indent=1))
        return
    rows = []
    for key in regions.CANDIDATES:
        pts = dense_walkers(key)
        if pts is None or not len(pts):
            continue
        for (tid, piece), p in pts.sort_values("t").groupby(
                ["trace_id", "piece"], sort=False):
            for rate in RATES:
                m = measure(p, rate)
                if m:
                    rows.append({"region": key, "trace_id": tid,
                                 "piece": piece, "rate_s": rate, **m})
        print(f"{key}: {pts.trace_id.nunique()} dense walking traces",
              flush=True)
    r = pd.DataFrame(rows)
    # per trace and rate; keep traces measured at every rate
    t = r.groupby(["region", "trace_id", "rate_s"])[
        ["dist_m", "chord_m", "moving_s", "stopped_s"]].sum().reset_index()
    full = t.groupby("trace_id").rate_s.nunique() == len(RATES)
    t = t[t.trace_id.isin(full[full].index)]
    t["speed_kmh"] = 3.6 * t.dist_m / t.moving_s
    t["stopped_share"] = t.stopped_s / (t.moving_s + t.stopped_s)
    t.to_csv(OUT / "by_trace.csv", index=False)

    base = t[t.rate_s == 5].set_index("trace_id")
    ids = base.index.to_numpy()
    rng = np.random.default_rng(0)
    pick = rng.integers(0, len(ids), (B, len(ids)))
    summ = {"traces": int(len(ids)), "regions": int(t.region.nunique()),
            "km_at_5s": round(float(base.dist_m.sum() / 1000), 1),
            "rates": {}}
    for rate in RATES:
        x = t[t.rate_s == rate].set_index("trace_id").loc[ids]

        def pooled(col, idx=slice(None)):
            return float(x[col].to_numpy()[idx].sum()
                         / base[col].to_numpy()[idx].sum())

        def speed(idx=slice(None)):
            return float((x.dist_m.to_numpy()[idx].sum()
                          / x.moving_s.to_numpy()[idx].sum())
                         / (base.dist_m.to_numpy()[idx].sum()
                            / base.moving_s.to_numpy()[idx].sum()))
        boots = np.array([speed(i) for i in pick])
        summ["rates"][str(rate)] = {
            "speed_ratio": round(speed(), 4),
            "speed_ratio_ci": [round(float(q), 4) for q in
                               np.percentile(boots, [2.5, 97.5])],
            "speed_ratio_median_trace": round(float(np.median(
                x.speed_kmh / base.speed_kmh)), 4),
            "distance_ratio": round(pooled("chord_m"), 4),
            "moving_time_ratio": round(pooled("moving_s"), 4),
            "stopped_share": round(float(x.stopped_s.sum() / (
                x.stopped_s.sum() + x.moving_s.sum())), 4)}
    obs, curve = observed()
    summ.update({"observed": obs.round(4).to_dict("records"),
                 "curve": curve})
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
