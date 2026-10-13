#!/usr/bin/env python3
"""
The weather on each hike's day and place, from Daymet (ORNL DAAC, Version 4
R1: daily 1 km surface weather for North America; Thornton et al. 2022,
doi 10.3334/ORNLDAAC/2129). Single-pixel API, no account: one request per
outing, 1 s apart, every reply cached.

Per outing: the local date of its first walking segment and the mean
position of its walking segments, rounded to 0.01 degrees (~1 km, Daymet's
grid), so no exact GPS position is sent. Daymet covers 1980-2025: 2026 hikes
and doubtful dates get none. Values for that day:
  tmax, tmin  daily max / min air temperature (deg C)
  prcp        precipitation (mm/day)
  swe         snow water equivalent on the ground (kg/m2), from Daymet's
              snow model; checked below (high pixels can keep model snow
              into summer)
  vp          water vapour pressure (Pa): humidity

Then, as for season (t3_season_time.py): each outing's mean residual of
ln(speed) after the pooled slope curve, relative to its region's average,
by temperature, rain, snow on the ground and humidity (95% intervals
resampling outings).

Output: cache/daymet/<lat>_<lon>_<date>.csv (raw replies)
        data/t2/weather_<region>.parquet (segment_id, tmax, tmin, prcp,
        swe, vp)
        results/t2_weather/ by_weather.csv, summary.json
Run (cluster): python t2_weather.py      (then refresh_harness.sh weather,
               weatherterrain)
"""

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import t1_findings as tf

CACHE = Path("cache/daymet")
OUT = Path("results/t2_weather")
URL = "https://daymet.ornl.gov/single-pixel/api/data"
UA = {"User-Agent": "travel-speed-research/0.1 (WashU MVRL; hiking speed "
                    "study)"}
VARS = ["tmax", "tmin", "prcp", "swe", "vp"]
B = 1000


def fetch(lat, lon, date):
    """Daymet values for one pixel and day (cached); None if unavailable."""
    f = CACHE / f"{lat:.2f}_{lon:.2f}_{date}.csv"
    if not f.exists():
        for attempt in range(4):
            try:
                r = requests.get(URL, params={
                    "lat": f"{lat:.2f}", "lon": f"{lon:.2f}",
                    "vars": ",".join(VARS), "start": date, "end": date},
                    headers=UA, timeout=60)
                if r.status_code == 200:
                    f.write_text(r.text)
                    break
                if r.status_code in (400, 404):
                    f.write_text("")            # outside coverage / date
                    break
            except requests.RequestException:
                pass
            time.sleep(10 * (attempt + 1))
        time.sleep(1.0)
        if not f.exists():
            return None
    lines = f.read_text().splitlines()
    try:
        i = next(k for k, l in enumerate(lines) if l.startswith("year,"))
        head = [h.split(" (")[0] for h in lines[i].split(",")]
        vals = dict(zip(head, lines[i + 1].split(",")))
        return {v: float(vals[v]) for v in VARS}
    except (StopIteration, IndexError, KeyError, ValueError):
        return None


def outings():
    cols = ["region", "segment_id", "outing_id", "slope", "speed_kmh",
            "analysis_walk", "lat0", "lon0", "lat1", "lon1", "local_time",
            "date_suspect", "t_start"]
    w = pd.read_parquet("data/t1_all/segments_L50.parquet", columns=cols)
    w = w[w.analysis_walk & (w.speed_kmh > 0)
          & w.slope.between(-0.6, 0.6)].reset_index(drop=True)
    p = json.loads(Path("results/t1_findings/numbers.json").read_text()
                   )["forms_cv"]["smooth_asym"]["params_all"]
    w["res"] = np.log(w.speed_kmh) - tf.FORMS["smooth_asym"][0](
        p, w.slope.to_numpy())
    w["lat"], w["lon"] = (w.lat0 + w.lat1) / 2, (w.lon0 + w.lon1) / 2
    first = w.sort_values("t_start").groupby("outing_id").first()
    o = w.groupby("outing_id").agg(region=("region", "first"),
                                   lat=("lat", "mean"), lon=("lon", "mean"),
                                   res=("res", "mean"),
                                   suspect=("date_suspect", "max"))
    o["date"] = first.local_time.str[:10]
    o["year"] = o.date.str[:4].astype(int)
    return w, o


def boot_mean(v, rng):
    v = np.asarray(v, float)
    m = rng.choice(v, (B, len(v))).mean(1)
    return float(v.mean()), *[float(x) for x in np.percentile(m, [2.5, 97.5])]


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    w, o = outings()
    ok = ~o.suspect & o.year.between(1980, 2025)
    rows, t0 = {}, time.time()
    for k, (oid, r) in enumerate(o[ok].iterrows()):
        v = fetch(round(r.lat, 2), round(r.lon, 2), r.date)
        if v:
            rows[oid] = v
        if k % 200 == 0:
            print(f"{k}/{int(ok.sum())} outings, {time.time() - t0:.0f} s",
                  flush=True)
    wx = pd.DataFrame.from_dict(rows, orient="index")
    o = o.join(wx)
    seg = w[["region", "segment_id", "outing_id"]].join(
        o[VARS], on="outing_id")
    for reg, d in seg.groupby("region"):
        d[["segment_id", *VARS]].to_parquet(
            Path("data/t2") / f"weather_{reg}.parquet", index=False)

    # sanity: model snow in summer?
    o["month"] = o.date.str[5:7].astype(int)
    snow_by_month = (o.dropna(subset=["swe"]).groupby("month").swe
                     .apply(lambda x: float((x > 10).mean())).round(3))

    # speed by weather, relative to the region's average hike
    rng = np.random.default_rng(0)
    o["res_r"] = o.res - o.groupby("region").res.transform("mean")
    d = o.dropna(subset=["tmax"])
    groups = [
        ("tmax", "below 5 C", d.tmax < 5), ("tmax", "5-15 C",
                                             d.tmax.between(5, 15)),
        ("tmax", "15-25 C", d.tmax.between(15, 25, inclusive="right")),
        ("tmax", "above 25 C", d.tmax > 25),
        ("prcp", "dry (< 1 mm)", d.prcp < 1),
        ("prcp", "rain (>= 1 mm)", d.prcp >= 1),
        ("swe", "no snow (swe < 10)", d.swe < 10),
        ("swe", "snow on ground (swe >= 10)", d.swe >= 10),
        ("vp", "dry air (lowest third)", d.vp <= d.vp.quantile(1 / 3)),
        ("vp", "humid air (highest third)", d.vp > d.vp.quantile(2 / 3))]
    out = []
    for var, label, mask in groups:
        x = d[mask]
        if len(x) >= 20:
            m, lo, hi = boot_mean(x.res_r, rng)
            pct = lambda z: 100 * (np.exp(z) - 1)            # noqa: E731
            out.append({"variable": var, "group": label, "outings": len(x),
                        "speed_pct": pct(m), "lo": pct(lo), "hi": pct(hi)})
    by = pd.DataFrame(out)
    by.to_csv(OUT / "by_weather.csv", index=False)
    summary = {
        "outings": int(len(o)), "queried": int(ok.sum()),
        "with_weather": int(o.tmax.notna().sum()),
        "segments_with_weather": float(seg.tmax.notna().mean()),
        "tmax_range": [float(d.tmax.min()), float(d.tmax.max())],
        "share_rain": float((d.prcp >= 1).mean()),
        "share_snow_on_ground": float((d.swe >= 10).mean()),
        "snow_share_by_month": snow_by_month.to_dict(),
        "minutes": round((time.time() - t0) / 60, 1)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    print(by.round(1).to_string(index=False))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
