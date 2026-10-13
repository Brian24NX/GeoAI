#!/usr/bin/env python3
"""
Season and time of day: do they change walking speed, and do they help
predict it in regions a model never saw? Huang et al. (2026) found weather
matters on Hong Kong trails. We have no weather yet, but every hike has a
date and a local time.

1. Describe, with the residual of ln(speed) after the pooled slope curve
   (t1_findings smooth_asym):
   - season, between hikes: each outing's mean residual by month (one vote
     per outing, 95% intervals resampling outings), all regions; and by
     region and season, relative to the region's own average;
   - time of day, within hikes: each segment's residual minus its outing's
     mean, by local hour (the hiker and the day are held fixed), next to
     hours since the start (fatigue);
   - start time, between hikes: the outing's mean residual by start hour.
2. Context covariates for the harness, per region:
   data/t2/context_<region>.parquet (segment_id, doy = day of year, hour =
   local decimal hour; doubtful dates left empty). Score them with
   cluster/refresh_harness.sh context and contextterrain (they show up as
   the "rs" arms).

Input:  data/t1_all/segments_L50.parquet, results/t1_findings/numbers.json
Output: results/t3_season_time/ by_month.csv, by_season_region.csv,
        by_hour.csv, by_start_hour.csv, summary.json, fig_season_time.png;
        data/t2/context_<region>.parquet
Run (cluster): python t3_season_time.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import t1_findings as tf

OUT = Path("results/t3_season_time")
B = 1000
SEASON = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring",
          5: "spring", 6: "summer", 7: "summer", 8: "summer", 9: "autumn",
          10: "autumn", 11: "autumn"}
MIN_OUT = 8


def pct(x):
    return 100 * (np.exp(x) - 1)


def load():
    cols = ["region", "segment_id", "outing_id", "slope", "speed_kmh",
            "analysis_walk", "local_time", "date_suspect", "t_start"]
    w = pd.read_parquet("data/t1_all/segments_L50.parquet", columns=cols)
    w = w[w.analysis_walk & (w.speed_kmh > 0)
          & w.slope.between(-0.6, 0.6)].reset_index(drop=True)
    p = json.loads(Path("results/t1_findings/numbers.json").read_text()
                   )["forms_cv"]["smooth_asym"]["params_all"]
    w["res"] = np.log(w.speed_kmh) - tf.FORMS["smooth_asym"][0](
        p, w.slope.to_numpy())
    w["rd"] = w.res - w.groupby("outing_id").res.transform("mean")
    lt = pd.to_datetime(w.local_time, errors="coerce")
    w["month"] = lt.dt.month
    w["doy"] = lt.dt.dayofyear.astype(float)
    w["hour"] = lt.dt.hour + lt.dt.minute / 60
    w.loc[w.date_suspect, ["month", "doy"]] = np.nan
    t0 = w.groupby("outing_id").t_start.transform("min")
    w["h_since"] = (w.t_start - t0) / 3600
    return w


def boot_mean(v, rng):
    """Mean and 95% interval (resampling the values: one per outing)."""
    v = np.asarray(v, float)
    m = rng.choice(v, (B, len(v))).mean(1)
    return float(v.mean()), *[float(x) for x in np.percentile(m, [2.5, 97.5])]


def boot_by_outing(d, rng):
    """Mean of rd over segments, 95% interval resampling outings."""
    g = d.groupby("outing_id").rd.agg(["sum", "size"])
    s, n = g["sum"].to_numpy(), g["size"].to_numpy()
    idx = rng.integers(0, len(g), (B, len(g)))
    m = s[idx].sum(1) / n[idx].sum(1)
    return (float(s.sum() / n.sum()),
            *[float(x) for x in np.percentile(m, [2.5, 97.5])])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    w = load()
    first = w.sort_values("t_start").groupby("outing_id").first()
    o = w.groupby("outing_id").agg(region=("region", "first"),
                                   res=("res", "mean"), n=("res", "size"))
    o["month"] = first.month
    o["start_hour"] = np.floor(first.hour)
    o["res_c"] = o.res - o.res.mean()
    o["res_r"] = o.res - o.groupby("region").res.transform("mean")

    # season, between hikes
    rows = []
    for m, d in o.dropna(subset=["month"]).groupby("month"):
        mean, lo, hi = boot_mean(d.res_r, rng)
        rows.append({"month": int(m), "outings": len(d),
                     "speed_pct": pct(mean), "lo": pct(lo), "hi": pct(hi)})
    by_month = pd.DataFrame(rows)
    by_month.to_csv(OUT / "by_month.csv", index=False)
    o["season"] = o.month.map(SEASON)
    rows = []
    for (reg, s), d in o.dropna(subset=["season"]).groupby(
            ["region", "season"]):
        if len(d) >= MIN_OUT:
            mean, lo, hi = boot_mean(d.res_r, rng)
            rows.append({"region": reg, "season": s, "outings": len(d),
                         "speed_pct": pct(mean), "lo": pct(lo),
                         "hi": pct(hi)})
    by_sr = pd.DataFrame(rows)
    by_sr.to_csv(OUT / "by_season_region.csv", index=False)

    # time of day within hikes, and hours since the start
    rows = []
    for h in range(5, 21):
        d = w[np.floor(w.hour) == h]
        if d.outing_id.nunique() >= 20:
            mean, lo, hi = boot_by_outing(d, rng)
            rows.append({"kind": "hour_of_day", "x": h,
                         "segments": len(d), "outings": d.outing_id.nunique(),
                         "speed_pct": pct(mean), "lo": pct(lo),
                         "hi": pct(hi)})
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 6), (6, 8), (8, 12)]:
        d = w[(w.h_since >= a) & (w.h_since < b)]
        if d.outing_id.nunique() >= 20:
            mean, lo, hi = boot_by_outing(d, rng)
            rows.append({"kind": "hours_since_start", "x": (a + b) / 2,
                         "segments": len(d), "outings": d.outing_id.nunique(),
                         "speed_pct": pct(mean), "lo": pct(lo),
                         "hi": pct(hi)})
    by_hour = pd.DataFrame(rows)
    by_hour.to_csv(OUT / "by_hour.csv", index=False)

    # start time, between hikes
    rows = []
    o["start_bin"] = o.start_hour.clip(6, 14)
    for h, d in o.dropna(subset=["start_bin"]).groupby("start_bin"):
        if len(d) >= 20:
            mean, lo, hi = boot_mean(d.res_r, rng)
            rows.append({"start_hour": int(h), "outings": len(d),
                         "speed_pct": pct(mean), "lo": pct(lo),
                         "hi": pct(hi)})
    by_start = pd.DataFrame(rows)
    by_start.to_csv(OUT / "by_start_hour.csv", index=False)

    # headline contrasts, with intervals resampling outings
    def contrast_outings(a, b):
        va, vb = a.res_r.to_numpy(), b.res_r.to_numpy()
        ia = rng.integers(0, len(va), (B, len(va)))
        ib = rng.integers(0, len(vb), (B, len(vb)))
        dd = va[ia].mean(1) - vb[ib].mean(1)
        return {"pct": pct(va.mean() - vb.mean()),
                "ci": [pct(x) for x in np.percentile(dd, [2.5, 97.5])],
                "outings": [len(va), len(vb)]}

    def contrast_within(a_mask, b_mask):
        g = pd.concat([w[a_mask].assign(side=1), w[b_mask].assign(side=0)]
                      ).groupby(["outing_id", "side"]).rd.agg(
            ["sum", "size"]).unstack("side", fill_value=0)
        s1, n1 = g[("sum", 1)].to_numpy(), g[("size", 1)].to_numpy()
        s0, n0 = g[("sum", 0)].to_numpy(), g[("size", 0)].to_numpy()
        idx = rng.integers(0, len(g), (B, len(g)))
        dd = s1[idx].sum(1) / n1[idx].sum(1) - s0[idx].sum(1) / n0[idx].sum(1)
        return {"pct": pct(s1.sum() / n1.sum() - s0.sum() / n0.sum()),
                "ci": [pct(x) for x in np.percentile(dd, [2.5, 97.5])]}

    win, summ = o[o.season == "winter"], o[o.season == "summer"]
    summary = {
        "outings": int(len(o)),
        "winter_vs_summer": contrast_outings(win, summ),
        "afternoon_vs_morning_within_hike": contrast_within(
            (w.hour >= 14) & (w.hour < 18), (w.hour >= 8) & (w.hour < 12)),
        "month_range_pct": [float(by_month.speed_pct.min()),
                            float(by_month.speed_pct.max())],
        "winter_vs_summer_by_region": {
            r: round(float(d.set_index("season").speed_pct.get("winter",
                                                               np.nan)
                           - d.set_index("season").speed_pct.get("summer",
                                                                 np.nan)), 1)
            for r, d in by_sr.groupby("region")}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(by_month.round(1).to_string(index=False))
    print(by_hour.round(1).to_string(index=False))
    print(by_start.round(1).to_string(index=False))
    print(json.dumps(summary, indent=1))

    # context covariates for the harness
    for reg, d in w.groupby("region"):
        d[["segment_id", "doy", "hour"]].to_parquet(
            Path("data/t2") / f"context_{reg}.parquet", index=False)
    figure(by_month, by_hour, by_start)


def figure(by_month, by_hour, by_start):
    BLUE, GRAY = "#2a78d6", "#9a9893"
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.6))
    ax[0].fill_between(by_month.month, by_month.lo, by_month.hi, color=BLUE,
                       alpha=0.15, lw=0)
    ax[0].plot(by_month.month, by_month.speed_pct, "o-", color=BLUE, ms=4)
    ax[0].set_xticks(range(1, 13), list("JFMAMJJASOND"))
    ax[0].set_title("Season: hikes by month\n(vs the region's average hike)",
                    fontsize=9)
    h = by_hour[by_hour.kind == "hour_of_day"]
    ax[1].fill_between(h.x, h.lo, h.hi, color=BLUE, alpha=0.15, lw=0)
    ax[1].plot(h.x, h.speed_pct, "o-", color=BLUE, ms=4)
    ax[1].set_xlabel("local hour")
    ax[1].set_title("Time of day, within the same hike", fontsize=9)
    ax[2].fill_between(by_start.start_hour, by_start.lo, by_start.hi,
                       color=GRAY, alpha=0.2, lw=0)
    ax[2].plot(by_start.start_hour, by_start.speed_pct, "o-", color=GRAY,
               ms=4)
    ax[2].set_xlabel("start hour (6 = 6 or earlier, 14 = 14 or later)")
    ax[2].set_title("Start time, between hikes", fontsize=9)
    for a in ax:
        a.axhline(0, color="#52514e", lw=0.8)
        a.grid(color="#e4e3df")
        a.spines[["top", "right"]].set_visible(False)
    ax[0].set_ylabel("speed vs slope curve (%)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_season_time.png", dpi=170)


if __name__ == "__main__":
    main()
