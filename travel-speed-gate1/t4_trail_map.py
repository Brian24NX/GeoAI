#!/usr/bin/env python3
"""
Application figure: predicted walking pace on EVERY trail of a region,
including trails nobody in our data walked. The terrain-adjusted hiking
function (t4_terrain_curve.py form) is fitted on the OTHER 16 regions only,
as in leave-one-region-out, and compared with Tobler's 1993 function.

1. OSM trail ways of the region (Overpass cache, way_class "trail"), cut
   into 50 m pieces in UTM.
2. Each piece: elevation every 1 m from the 5 m USGS grids (as in
   t2_terrain5m.py) -> slope s and steppiness z (SD of 5 m pitches / 0.10).
3. Pace (min/km) in both walking directions, from the fitted function and
   from Tobler; the map shows the mean of the two directions.
4. Which pieces our hikers walked (a walking segment within 25 m).

Output: results/t4_trail_map/<region>_pieces.parquet, fig_<region>_pace.png
Run (cluster): python t4_trail_map.py --region wm
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from pyproj import Transformer
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

import gate1_audit as g
import regions
from t2_terrain1m import profile_metrics
from t2_terrain5m import Pieces

OUT = Path("results/t4_trail_map")
SEG_M, SCALE = 50.0, 0.10


def model(p, s, z):
    a0, a1, k0, k1, s0 = p
    return a0 + a1 * z - (k0 + k1 * z) * np.abs(s + s0)


def fit_other_regions(key):
    s = pd.read_parquet("data/t1_all/segments_L50.parquet",
                        columns=["region", "segment_id", "slope", "speed_kmh",
                                 "analysis_walk"])
    s = s[s.analysis_walk & (s.region != key) & (s.speed_kmh > 0)
          & s.slope.between(-0.6, 0.6)]
    t = pd.concat(pd.read_parquet(f, columns=["segment_id", "pitch_sd_5m"])
                  for f in sorted(Path("data/t2").glob("terrain5m_*.parquet")))
    s = s.merge(t, on="segment_id").dropna(subset=["pitch_sd_5m"])
    z, x, y = s.pitch_sd_5m.to_numpy() / SCALE, s.slope.to_numpy(), \
        np.log(s.speed_kmh.to_numpy())
    p = least_squares(lambda q: model(q, x, z) - y,
                      [1.45, -0.1, 1.8, 0.2, 0.05], loss="soft_l1",
                      f_scale=0.3).x
    return p, len(s)


def trail_ways(key):
    ways = {}
    for f in sorted(Path("cache", regions.region_name(key)).glob(
            "*_ways.json")):
        for w in json.loads(f.read_text())["elements"]:
            geom = [q for q in (w.get("geometry") or []) if q]
            if (w.get("type") == "way" and len(geom) >= 2
                    and g.way_class(w.get("tags", {})) == "trail"):
                ways[w["id"]] = (geom, w.get("tags", {}))
    return ways


def pieces_of(geom, to_utm):
    lon = np.array([q["lon"] for q in geom])
    lat = np.array([q["lat"] for q in geom])
    x, y = to_utm.transform(lon, lat)
    d = np.r_[0.0, np.cumsum(np.hypot(np.diff(x), np.diff(y)))]
    out = []
    for a in np.arange(0, d[-1] - 20 + 1e-9, SEG_M):
        b = min(a + SEG_M, d[-1])
        t = np.arange(a, b + 1e-9, 1.0)
        out.append((np.interp(t, d, x), np.interp(t, d, y), b - a))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="wm")
    key = ap.parse_args().region
    OUT.mkdir(parents=True, exist_ok=True)
    p, n_fit = fit_other_regions(key)
    print(f"function fitted on {n_fit:,} walking segments of the other "
          f"regions: {np.round(p, 3).tolist()}", flush=True)
    epsg = regions.utm_epsg(key)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    to_geo = Transformer.from_crs(epsg, 4326, always_xy=True)
    grids = Pieces(key)
    rows = []
    for wid, (geom, tags) in trail_ways(key).items():
        for x, y, L in pieces_of(geom, to_utm):
            lon, lat = to_geo.transform(x, y)
            z = grids.sample(np.asarray(lon), np.asarray(lat), "z")
            if np.isfinite(z).mean() < 0.9:
                continue
            zz = pd.Series(z).interpolate(limit_direction="both").to_numpy()
            pm = profile_metrics(zz, L)
            rows.append({"way_id": wid, "x0": x[0], "y0": y[0], "x1": x[-1],
                         "y1": y[-1], "length_m": L, "slope": pm["slope_1m"],
                         "steppiness": pm.get("pitch_sd", np.nan),
                         "sac_scale": tags.get("sac_scale"),
                         "name": tags.get("name")})
    pc = pd.DataFrame(rows).dropna(subset=["slope", "steppiness"])
    pc = pc[pc.slope.abs() <= 0.6]
    z = pc.steppiness.to_numpy() / SCALE
    for name, f in [("terrain", lambda s: np.exp(model(p, s, z))),
                    ("tobler", lambda s: 6 * np.exp(-3.5 * np.abs(s + 0.05)))]:
        v_f, v_b = f(pc.slope.to_numpy()), f(-pc.slope.to_numpy())
        pc[f"pace_{name}"] = (60 / v_f + 60 / v_b) / 2      # min per km
    # walked by our hikers?
    s = pd.read_parquet("data/t1_all/segments_L50.parquet",
                        columns=["region", "lat0", "lon0", "lat1", "lon1",
                                 "analysis_walk"],
                        filters=[("region", "==", key)])
    s = s[s.analysis_walk]
    wx, wy = to_utm.transform(((s.lon0 + s.lon1) / 2).to_numpy(),
                              ((s.lat0 + s.lat1) / 2).to_numpy())
    dd, _ = cKDTree(np.c_[wx, wy]).query(
        np.c_[(pc.x0 + pc.x1) / 2, (pc.y0 + pc.y1) / 2],
        distance_upper_bound=25)
    pc["walked"] = np.isfinite(dd)
    pc.to_parquet(OUT / f"{key}_pieces.parquet", index=False)
    km = pc.length_m.sum() / 1000
    wk = pc.loc[pc.walked, "length_m"].sum() / 1000
    summary = {"trail_km": round(km, 1), "walked_km": round(wk, 1),
               "walked_share": round(wk / km, 3),
               "pace_terrain_median": round(float(pc.pace_terrain.median()), 1),
               "pace_tobler_median": round(float(pc.pace_tobler.median()), 1),
               "pace_terrain_p10_p90": [round(float(q), 1) for q in
                                        np.percentile(pc.pace_terrain,
                                                      [10, 90])],
               "fitted_on_segments": n_fit, "params": np.round(p, 4).tolist()}
    (OUT / f"{key}_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6), sharex=True, sharey=True)
    segs = np.stack([np.c_[pc.x0, pc.y0], np.c_[pc.x1, pc.y1]], axis=1) / 1000
    for a, col, title, cmap, lim in [
            (ax[0], pc.pace_tobler, "Tobler 1993", "viridis_r", (10, 30)),
            (ax[1], pc.pace_terrain,
             "Terrain-adjusted function\n(fitted on the other 16 regions)",
             "viridis_r", (10, 30)),
            (ax[2], pc.pace_terrain - pc.pace_tobler,
             "Difference: terrain minus Tobler", "RdBu_r", (-8, 8))]:
        lc = LineCollection(segs, array=col.to_numpy(), cmap=cmap, lw=0.9)
        lc.set_clim(*lim)
        a.add_collection(lc)
        a.set_title(title, fontsize=10)
        a.set_aspect("equal")
        a.autoscale()
        fig.colorbar(lc, ax=a, shrink=0.85, pad=0.02,
                     label="min per km (both directions)"
                     if a is not ax[2] else "min per km")
    ax[0].set_ylabel("UTM north (km)")
    for a in ax:
        a.set_xlabel("UTM east (km)")
    fig.suptitle(f"Walking pace on every trail of {regions.CANDIDATES[key][0]}"
                 f": {km:,.0f} km of OSM trail, {wk / km:.0%} walked in our "
                 f"data", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT / f"fig_{key}_pace.png", dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    main()
