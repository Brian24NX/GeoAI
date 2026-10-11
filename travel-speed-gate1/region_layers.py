#!/usr/bin/env python3
"""
Region layers: the non-trace columns of the region comparison table.

Semester plan, section 7: the region needs real relief, forest cover and 3DEP
1 m coverage ("verify 3DEP 1 m coverage against your exact footprint in week
1 -- it's acquired project-by-project and is not seamless"). This script
checks all three for every Gate 1 box, using public services that need no
account:

  1. 1 m coverage. Sample the USGS 3DEP elevation service on a 30 x 30 grid
     over the box. Each sample says the resolution of the best DEM at that
     spot, so the share of samples at 1 m is the 1 m coverage.
  2. Relief. Highest minus lowest of those 900 elevation samples.
  3. Lidar projects. The USGS lidar index (WESM) lists every acquisition that
     overlaps the box: quality level (QL1 = 8+ pulses per m2, QL2 = 2+; pulse
     density matters for understory, plan sec. 7), collection dates (leaf-off
     vs leaf-on matters too) and whether the point cloud is published.
  4. Tree canopy. NLCD 2021 Tree Canopy Cover (30 m) from MRLC: the box
     average, and the average along the OSM trail network (taken from the
     ways that gate1_audit.py cached).

Every answer is cached in cache/layers/, so re-runs are instant.

Run:  python region_layers.py      (after gate1_audit.py, for trail canopy)
Needs: requests, numpy, pandas, tifffile
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from gate1_audit import REGIONS, way_class

AGENT = {"User-Agent": "WashU-MVRL-travel-speed/0.2 (research)"}
ELEVATION_URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/"
                 "3DEPElevation/ImageServer/getSamples")
LIDAR_INDEX_URL = ("https://index.nationalmap.gov/arcgis/rest/services/"
                   "3DEPElevationIndex/MapServer/24/query")
CANOPY_URL = "https://www.mrlc.gov/geoserver/mrlc_download/wcs"
CANOPY_COVERAGE = "mrlc_download:nlcd_tcc_conus_2021_v2021-4"
GRID = 30            # elevation samples per side of a box
CANOPY_PX = 300      # canopy raster size per side (~30 m pixels)
DELAY_S = 1.0


def cached(path, fetch):
    """Return the cached answer at path, or fetch it once and save it."""
    path = Path(path)
    if path.exists():
        return path.read_bytes()
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    time.sleep(DELAY_S)
    return data


def _request(method, url, tries=3, **kwargs):
    """GET/POST with a few patient retries -- these servers time out often."""
    import requests
    for attempt in range(tries):
        try:
            r = requests.request(method, url, headers=AGENT, timeout=180,
                                 **kwargs)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(15 * (attempt + 1))


def _post(url, data):
    return _request("POST", url, data=data)


def _get(url, params):
    return _request("GET", url, params=params)


def elevation_samples(cache, box):
    """Elevation (m) and source resolution (m) on a GRID x GRID grid."""
    name, w, s, e, n = box
    xs, ys = np.meshgrid(np.linspace(w, e, GRID), np.linspace(s, n, GRID))
    pts = [[round(x, 6), round(y, 6)] for x, y in zip(xs.ravel(), ys.ravel())]
    geom = json.dumps({"points": pts, "spatialReference": {"wkid": 4326}})
    raw = cached(cache / f"{name}_elevation.json", lambda: _post(
        ELEVATION_URL, {"geometry": geom,
                        "geometryType": "esriGeometryMultipoint",
                        "returnFirstValueOnly": "true", "f": "json"}))
    out = []
    for smp in json.loads(raw).get("samples", []):
        try:
            z, res = float(smp["value"]), float(smp["resolution"])
        except (KeyError, TypeError, ValueError):
            continue                              # NoData
        # Resolution comes in the DEM's own units: meters for the 1 m DEMs
        # (UTM), degrees for the seamless 1/9 and 1/3 arc-second DEMs.
        if res < 0.01:
            res *= 111_320.0                      # degrees -> meters
        out.append((z, res))
    return np.array(out).reshape(-1, 2)


def lidar_projects(cache, box):
    """USGS lidar work units (WESM) that overlap the box."""
    name, w, s, e, n = box
    raw = cached(cache / f"{name}_lidar_index.json", lambda: _get(
        LIDAR_INDEX_URL, {"geometry": f"{w},{s},{e},{n}",
                          "geometryType": "esriGeometryEnvelope",
                          "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
                          "outFields": "*", "returnGeometry": "false",
                          "f": "json"}))
    units = []
    for f in json.loads(raw).get("features", []):
        a = f["attributes"]
        units.append({
            "project": a.get("project"),
            "workunit": a.get("workunit"),
            "ql": a.get("ql"),
            "collected": f"{_month(a.get('collect_start'))} to "
                         f"{_month(a.get('collect_end'))}",
            "leaf": _leaf(a.get("collect_start"), a.get("collect_end")),
            "one_meter": a.get("onemeter_category"),
            "point_cloud_link": a.get("lpc_link") or None,
        })
    return units


def _ql_rank(ql):
    """Sort key: QL 0 (best) ... QL 3, then anything else ("Other")."""
    digits = "".join(ch for ch in str(ql) if ch.isdigit())
    return int(digits) if str(ql).upper().startswith("QL") and digits else 9


def _month(ms):
    if ms is None:
        return "?"
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m")


def _leaf(start, end):
    """Rough guess: collected entirely in Nov-Apr = leaf-off."""
    if start is None or end is None:
        return "?"
    a = datetime.fromtimestamp(start / 1000, timezone.utc)
    b = datetime.fromtimestamp(end / 1000, timezone.utc)
    if (b - a).days > 200:
        return "mixed (long campaign)"
    months = pd.date_range(a.replace(day=1), b, freq="MS").month
    if all(m in (11, 12, 1, 2, 3, 4) for m in months):
        return "leaf-off"
    if all(m in (5, 6, 7, 8, 9, 10) for m in months):
        return "leaf-on"
    return "mixed"


def canopy_raster(cache, box):
    """NLCD 2021 tree canopy cover (%) as a CANOPY_PX x CANOPY_PX array."""
    import logging
    import tifffile
    logging.getLogger("tifffile").setLevel(logging.ERROR)  # harmless tag note
    name, w, s, e, n = box
    raw = cached(cache / f"{name}_canopy.tif", lambda: _get(CANOPY_URL, {
        "service": "WCS", "version": "1.0.0", "request": "GetCoverage",
        "coverage": CANOPY_COVERAGE, "crs": "EPSG:4326",
        "bbox": f"{w},{s},{e},{n}", "width": CANOPY_PX, "height": CANOPY_PX,
        "format": "GeoTIFF"}))
    path = cache / f"{name}_canopy.tif"
    a = tifffile.imread(path).astype(float)
    a[a > 100] = np.nan                      # 254/255 = no data
    return a


def trail_vertices(gate1_cache, region, box, spacing_m=25.0):
    """Points every ~25 m along the OSM trails in the box (from Gate 1)."""
    name, w, s, e, n = box
    path = Path(gate1_cache) / region / f"{name}_ways.json"
    if not path.exists():
        return None
    kx = 111_320.0 * np.cos(np.radians((s + n) / 2))
    ky = 111_132.0
    lats, lons = [], []
    for way in json.loads(path.read_text())["elements"]:
        if way_class(way.get("tags", {})) != "trail":
            continue
        g = [p for p in way.get("geometry") or [] if p]
        for p, q in zip(g[:-1], g[1:]):
            d = np.hypot((q["lon"] - p["lon"]) * kx, (q["lat"] - p["lat"]) * ky)
            k = max(1, int(d // spacing_m))
            f = np.arange(k) / k
            lats.append(p["lat"] + f * (q["lat"] - p["lat"]))
            lons.append(p["lon"] + f * (q["lon"] - p["lon"]))
    if not lats:
        return None
    lat, lon = np.concatenate(lats), np.concatenate(lons)
    inside = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
    return lat[inside], lon[inside]


def sample_raster(a, box, lat, lon):
    name, w, s, e, n = box
    rows = np.clip(((n - lat) / (n - s) * a.shape[0]).astype(int), 0,
                   a.shape[0] - 1)
    cols = np.clip(((lon - w) / (e - w) * a.shape[1]).astype(int), 0,
                   a.shape[1] - 1)
    return a[rows, cols]


def box_row(region, box, cache, gate1_cache):
    name = box[0]
    row = {"region": region, "box": name}
    elev = elevation_samples(cache, box)
    if len(elev):
        z, res = elev[:, 0], elev[:, 1]
        row.update(elev_min_m=z.min(), elev_max_m=z.max(),
                   relief_m=z.max() - z.min(),
                   one_meter_share=float(np.mean(res <= 1.5)),
                   dem_resolutions_m=", ".join(
                       f"{r:.0f} m: {np.mean(np.isclose(res, r, rtol=0.1)):.0%}"
                       for r in sorted(set(np.round(res, 1)))))
    units = lidar_projects(cache, box)
    row["lidar_projects"] = "; ".join(
        f"{u['project']} ({u['ql']}, {u['collected']}, {u['leaf']}"
        f"{', point cloud online' if u['point_cloud_link'] else ''})"
        for u in units) or "none"
    qls = sorted({u["ql"] for u in units if u["ql"]}, key=_ql_rank)
    row["best_ql"] = qls[0] if qls else None     # QL 0 > QL 1 > QL 2 > other
    row["all_ql"] = ", ".join(qls)
    canopy = canopy_raster(cache, box)
    row["canopy_box_mean_pct"] = float(np.nanmean(canopy))
    verts = trail_vertices(gate1_cache, region, box)
    if verts is not None:
        c = sample_raster(canopy, box, *verts)
        row["canopy_trail_mean_pct"] = float(np.nanmean(c))
        row["trail_share_under_50pct_canopy"] = float(np.nanmean(c > 50))
    return row, units


def main():
    gate1_cache = Path("cache")
    cache = gate1_cache / "layers"
    rows, all_units = [], {}
    for region, boxes in REGIONS.items():
        print(f"=== {region}")
        for box in boxes:
            try:
                row, units = box_row(region, box, cache, gate1_cache)
            except Exception as err:          # keep going; report the gap
                print(f"  {box[0]}: FAILED ({err})")
                rows.append({"region": region, "box": box[0],
                             "error": str(err)})
                continue
            rows.append(row)
            all_units[box[0]] = units
            print(f"  {box[0]:28s} 1 m DEM {100 * row.get('one_meter_share', 0):4.0f}%"
                  f"  relief {row.get('relief_m', float('nan')):5.0f} m"
                  f"  canopy box {row['canopy_box_mean_pct']:3.0f}% / trails "
                  f"{row.get('canopy_trail_mean_pct', float('nan')):3.0f}%"
                  f"  best lidar {row['best_ql']}")
    table = pd.DataFrame(rows)
    out = Path("results")
    out.mkdir(exist_ok=True)
    table.to_csv(out / "region_layers.csv", index=False)
    with open(out / "region_lidar_projects.json", "w") as f:
        json.dump(all_units, f, indent=2)

    by_region = table.groupby("region").agg(
        one_meter_share=("one_meter_share", "mean"),
        min_elev_m=("elev_min_m", "min"),
        max_elev_m=("elev_max_m", "max"),
        max_box_relief_m=("relief_m", "max"),
        canopy_box_mean_pct=("canopy_box_mean_pct", "mean"),
        canopy_trail_mean_pct=("canopy_trail_mean_pct", "mean"),
        best_ql=("best_ql", lambda q: sorted(q.dropna(), key=_ql_rank)[0]
                 if q.notna().any() else None),
    ).reset_index()
    by_region["region_relief_m"] = by_region["max_elev_m"] - \
        by_region["min_elev_m"]
    by_region.to_csv(out / "region_layers_by_region.csv", index=False)
    print("\n=== Region comparison (non-trace columns) ===")
    print(by_region.round(2).to_string(index=False))
    print(f"\nsaved: {out}/region_layers.csv, region_layers_by_region.csv, "
          "region_lidar_projects.json")


if __name__ == "__main__":
    main()
