#!/usr/bin/env python3
"""
Track B of the imagery arm, step 1 (decision #126; docs/T3_naip_imagery_design.md):
the trail spots to photograph and the NAIP photo for each.

A spot is a walking segment's midpoint snapped to a 25 m grid, so segments
that share a stretch of trail share one chip. Each spot takes the newest NAIP
photo (2019 or later) on Microsoft Planetary Computer whose footprint holds it,
preferring the one where it sits deepest inside, so its 96 m chip stays clear
of the photo's edge.

Input:  data/t1_all/segments_L50.parquet (walking rows, `analysis_walk`)
Output: data/t3/naip_spots.parquet: region, spot, lat, lon, segments, item,
        year, gsd, href (spots outside every photo keep an empty item)
        data/t3/naip_spot_of_segment.parquet: region, segment_id, spot
Run on ENGR:  python t3_naip_spots.py
The North Shore (Canada) has no NAIP. Planetary Computer's catalogue is read
through its public STAC search API; no imagery is downloaded here.
"""
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

SEGMENTS = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t3")
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
UA = {"Content-Type": "application/json", "User-Agent": "travel-speed-research-script"}
GRID_M = 25.0
YEARS = "2019-01-01/2025-12-31"


def post(body, tries=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(STAC, data=json.dumps(body).encode(), headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=120))
        except Exception as e:                       # a slow page: wait and retry
            if k == tries - 1:
                raise
            print(f"  retry {k + 1}: {e}", flush=True)
            time.sleep(5 * (k + 1))


def items_in(bbox):
    """Every NAIP item from 2019 on that touches bbox (lon/lat), all pages."""
    body = {"collections": ["naip"], "bbox": bbox, "datetime": YEARS, "limit": 1000}
    out = []
    while body:
        r = post(body)
        for f in r["features"]:
            p = f["properties"]
            out.append({"item": f["id"], "year": p["naip:year"], "gsd": p["gsd"],
                        "href": f["assets"]["image"]["href"],
                        "w": f["bbox"][0], "s": f["bbox"][1], "e": f["bbox"][2], "n": f["bbox"][3]})
        nxt = [l for l in r.get("links", []) if l.get("rel") == "next"]
        body = nxt[0].get("body") if nxt else None
    return pd.DataFrame(out)


def main():
    s = pd.read_parquet(SEGMENTS, columns=["region", "segment_id", "lat0", "lon0",
                                           "lat1", "lon1", "analysis_walk"])
    s = s[s.analysis_walk.astype(bool) & (s.region != "northshore")].reset_index(drop=True)
    lat = ((s.lat0 + s.lat1) / 2).to_numpy()
    lon = ((s.lon0 + s.lon1) / 2).to_numpy()
    spots, links = [], []
    for region, idx in s.groupby("region").indices.items():
        dlat = GRID_M / 110540
        dlon = GRID_M / (111320 * np.cos(np.radians(lat[idx].mean())))
        i, j = np.round(lat[idx] / dlat).astype(int), np.round(lon[idx] / dlon).astype(int)
        key = pd.Series(list(zip(i, j)))
        codes, uniq = pd.factorize(key)
        sp = pd.DataFrame({"region": region, "spot": np.arange(len(uniq)),
                           "lat": [a * dlat for a, _ in uniq], "lon": [b * dlon for _, b in uniq],
                           "segments": np.bincount(codes)})
        links.append(pd.DataFrame({"region": region, "segment_id": s.segment_id.to_numpy()[idx],
                                   "spot": codes}))
        it = items_in([float(sp.lon.min()) - 0.01, float(sp.lat.min()) - 0.01,
                       float(sp.lon.max()) + 0.01, float(sp.lat.max()) + 0.01])
        # margin of each spot inside each photo's footprint (degrees; < 0 = outside)
        m = np.minimum.reduce([sp.lon.to_numpy()[:, None] - it.w.to_numpy()[None],
                               it.e.to_numpy()[None] - sp.lon.to_numpy()[:, None],
                               sp.lat.to_numpy()[:, None] - it.s.to_numpy()[None],
                               it.n.to_numpy()[None] - sp.lat.to_numpy()[:, None]])
        score = np.where(m > 0.0008, it.year.to_numpy()[None] * 10 + np.minimum(m, 0.05) * 100, -np.inf)
        best = score.argmax(1)
        ok = np.isfinite(score[np.arange(len(sp)), best])
        for c in ["item", "year", "gsd", "href"]:
            sp[c] = np.where(ok, it[c].to_numpy()[best], None)
        spots.append(sp)
        print(f"{region}: {len(idx):,} segments, {len(sp):,} spots, {len(it)} photos from 2019 on; "
              f"spots without a photo {(~ok).sum()}; years {sp.year.value_counts().to_dict()}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    spots = pd.concat(spots, ignore_index=True)
    spots.to_parquet(OUT / "naip_spots.parquet", index=False)
    pd.concat(links, ignore_index=True).to_parquet(OUT / "naip_spot_of_segment.parquet", index=False)
    print(f"total {len(s):,} segments, {len(spots):,} spots, {spots.item.nunique()} photos; "
          f"gsd {spots.gsd.value_counts().to_dict()}", flush=True)


if __name__ == "__main__":
    main()
