#!/usr/bin/env python3
"""
Which elevation source sits under each region's walked trails?

The 5 m grids come from USGS 3DEP's dynamic service, which mosaics the best
DEM it has: 1 m lidar in most places, but 1/3 arc-second (~10 m) or coarser
elsewhere. A coarse source blurs slopes, and slope noise flattens the fitted
curve (lower k), so regional differences in k mean little until we know
this. For up to N random walking segments per region, ask USGS (getSamples)
the resolution of the best source at the segment's midpoint.

Output: results/t1_dem_quality.csv (one row per region), printed too.
Run after the builds:  python t1_dem_quality.py [--n 300]
"""

import argparse
import json

import numpy as np
import pandas as pd

import regions
import region_layers as rl
import t1_variants as v

BATCH = 100                      # points per getSamples request


def resolutions(lat, lon):
    """Best-source resolution (m) at each point (NaN where no data)."""
    out = []
    for a in range(0, len(lat), BATCH):
        pts = [[round(x, 6), round(y, 6)] for x, y in
               zip(lon[a:a + BATCH], lat[a:a + BATCH])]
        raw = rl._post(rl.ELEVATION_URL, {
            "geometry": json.dumps({"points": pts,
                                    "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "f": "json"})
        got = {}
        for smp in json.loads(raw).get("samples", []):
            try:
                res = float(smp["resolution"])
            except (KeyError, TypeError, ValueError):
                continue
            if res < 0.01:
                res *= 111_320.0                 # degrees -> meters
            got[smp.get("locationId", len(got))] = res
        out += [got.get(i, np.nan) for i in range(len(pts))]
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    n = ap.parse_args().n
    rng = np.random.default_rng(0)
    rows = []
    for key in regions.CANDIDATES:
        d = regions.data_dir(key)
        if not (d / "modes.csv").exists():
            continue
        seg = pd.read_parquet(d / "segments_L50.parquet")
        tr = pd.read_csv(d / "traces.csv")
        w = v.walker_trail_segments(seg, set(tr.loc[tr.hiking_trace,
                                                    "trace_id"]),
                                    pd.read_csv(d / "modes.csv"))
        if not len(w):
            continue
        pick = w.iloc[rng.choice(len(w), min(n, len(w)), replace=False)]
        res = resolutions(((pick.lat0 + pick.lat1) / 2).to_numpy(),
                          ((pick.lon0 + pick.lon1) / 2).to_numpy())
        ok = res[np.isfinite(res)]
        rows.append({"region": key, "segments_sampled": len(pick),
                     "share_1m_pct": 100 * np.mean(ok <= 1.5),
                     "share_le_3m_pct": 100 * np.mean(ok <= 3.5),
                     "share_10m_or_coarser_pct": 100 * np.mean(ok >= 9),
                     "median_resolution_m": float(np.median(ok))
                     if len(ok) else np.nan})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv("results/t1_dem_quality.csv", index=False)


if __name__ == "__main__":
    main()
