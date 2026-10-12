#!/usr/bin/env python3
"""
T2 tier 2 (pilot): understory vegetation from USGS 3DEP lidar POINT CLOUDS
around each walking segment, the measure the plan names (Campbell et al.
2018) and STRIDE uses: normalized relative density (NRD) = returns between
0.85 and 1.20 m above ground / returns at or below 1.20 m (`stride`
package, dns_fun). 30 m canopy maps carried no signal (decision #87); this
is the fine-scale test.

Point clouds: the public Entwine Point Tiles on AWS
(s3-us-west-2.amazonaws.com/usgs-lidar-public/<project>/), read without an
account: ept.json -> the octree hierarchy -> only the LAZ blocks that touch
a buffer around walked trails (laspy + lazrs). The project boundaries come
from the index hobuinc/usgs-lidar (cache/ept/resources.geojson).

Per segment, points within BUF_M of its matched path:
  nrd          STRIDE's understory density, 0.85-1.20 m
  nrd_center   the same within 1 m of the centerline (the tread itself)
  cover2m      share of first returns more than 2 m above ground
  hag_p95      95th percentile height above ground (canopy height)
  n_pts        points used
Height above ground = z - z of the nearest ground return (class 2) within
2 m, so no DEM or vertical datum is involved.

Run:  python t2_lidarveg.py --region wm --dry-run   (block and size count)
      python t2_lidarveg.py --region wm [--max-segments N]
Output: data/t2/lidarveg_<region>.parquet
"""

import argparse
import io
import json
import time
from pathlib import Path

import laspy
import numpy as np
import pandas as pd
import requests
from matplotlib.path import Path as MPath
from pyproj import Transformer
from scipy.spatial import cKDTree

INDEX = Path("cache/ept/resources.geojson")
SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t2")
BUF_M = 3.0
AGENT = {"User-Agent": "WashU-MVRL-travel-speed/0.2 (research)"}


def get(url, tries=4):
    for k in range(tries):
        try:
            r = requests.get(url, headers=AGENT, timeout=120)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if k == tries - 1:
                raise
            time.sleep(10 * (k + 1))


def polygons(geom):
    """Exterior rings of a (Multi)Polygon as matplotlib paths."""
    rings = ([geom["coordinates"][0]] if geom["type"] == "Polygon"
             else [p[0] for p in geom["coordinates"]])
    return [MPath(np.asarray(r)[:, :2]) for r in rings]


class EPT:
    def __init__(self, url):
        self.base = url.rsplit("/", 1)[0]
        self.meta = json.loads(get(url))
        b = self.meta["bounds"]
        self.x0, self.y0, self.size = b[0], b[1], b[3] - b[0]
        self.hier = {}
        self._load("0-0-0-0")

    def _load(self, key):
        h = json.loads(get(f"{self.base}/ept-hierarchy/{key}.json"))
        self.hier.update(h)

    def nodes(self, boxes):
        """Keys (with point counts) of every node touching any box
        (xmin, ymin, xmax, ymax, in the EPT's EPSG:3857 metres)."""
        boxes = np.asarray(boxes)
        out, todo = [], ["0-0-0-0"]
        while todo:
            key = todo.pop()
            if self.hier.get(key) == -1:          # subtree in its own file
                self._load(key)
            n = self.hier.get(key)
            if n is None:
                continue
            d, x, y, z = map(int, key.split("-"))
            s = self.size / 2 ** d
            nx0, ny0 = self.x0 + x * s, self.y0 + y * s
            hit = ((boxes[:, 0] < nx0 + s) & (boxes[:, 2] > nx0)
                   & (boxes[:, 1] < ny0 + s) & (boxes[:, 3] > ny0))
            if not hit.any():
                continue
            if n > 0:
                out.append((key, n))
            for dx in (0, 1):
                for dy in (0, 1):
                    for dz in (0, 1):
                        todo.append(f"{d + 1}-{2 * x + dx}-{2 * y + dy}-"
                                    f"{2 * z + dz}")
        return out


def seg_paths(key):
    s = pd.read_parquet(SEG, columns=["region", "analysis_walk", "segment_id",
                                      "outing_id", "geometry_wkt", "lat0",
                                      "lon0", "lat1", "lon1"],
                        filters=[("region", "==", key)])
    s = s[s.analysis_walk].reset_index(drop=True)
    to = Transformer.from_crs(4326, 3857, always_xy=True)
    paths = []
    for wkt in s.geometry_wkt:
        body = wkt[wkt.index("(") + 1: wkt.rindex(")")]
        lon, lat = np.array([p.split() for p in body.split(",")],
                            dtype=float).T
        x, y = to.transform(lon, lat)
        paths.append(np.c_[x, y])
    s["mlon"] = (s.lon0 + s.lon1) / 2
    s["mlat"] = (s.lat0 + s.lat1) / 2
    return s, paths


def dist_to_path(px, py, path):
    """Distance from points to a polyline (vectorized, mercator metres)."""
    a, b = path[:-1], path[1:]
    if len(a) == 0:
        return np.hypot(px - path[0, 0], py - path[0, 1])
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-9)
    t = np.clip(((px[:, None] - a[:, 0]) * ab[:, 0]
                 + (py[:, None] - a[:, 1]) * ab[:, 1]) / L2, 0, 1)
    cx, cy = a[:, 0] + t * ab[:, 0], a[:, 1] + t * ab[:, 1]
    return np.sqrt((px[:, None] - cx) ** 2
                   + (py[:, None] - cy) ** 2).min(axis=1)


def metrics(pts, dist, scale):
    """Per-segment vegetation numbers from its buffered points."""
    x, y, z, cls, rn = pts
    g = cls == 2
    if g.sum() < 10 or len(z) < 50:
        return None
    tree = cKDTree(np.c_[x[g], y[g]])
    dd, ii = tree.query(np.c_[x, y], distance_upper_bound=2.0 * scale)
    ok = np.isfinite(dd)
    hag = np.full(len(z), np.nan)
    hag[ok] = z[ok] - z[g][ii[ok]]
    low = ok & (hag <= 1.20)
    band = low & (hag >= 0.85)
    c = low & (dist <= 1.0 * scale)
    first = ok & (rn == 1)
    return {"nrd": band.sum() / max(low.sum(), 1),
            "nrd_center": (band & c).sum() / max(c.sum(), 1),
            "cover2m": (hag[first] > 2.0).mean() if first.any() else np.nan,
            "hag_p95": float(np.nanpercentile(hag[ok], 95)),
            "n_pts": int(ok.sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-segments", type=int, default=0,
                    help="pilot on a spatially compact subset")
    a = ap.parse_args()
    s, paths = seg_paths(a.region)
    feats = json.loads(INDEX.read_text())["features"]
    pts_ll = np.c_[s.mlon, s.mlat]
    owner = np.full(len(s), -1)
    for i, f in enumerate(feats):          # first project holding each seg
        free = owner < 0
        if not free.any():
            break
        inside = np.zeros(len(s), bool)
        for poly in polygons(f["geometry"]):
            inside |= poly.contains_points(pts_ll)
        owner[free & inside] = i
    use = np.nonzero(owner >= 0)[0]
    if a.max_segments and len(use) > a.max_segments:
        # a compact pilot: the 10 km cell walked by the most different
        # outings, then its segments nearest the cell center
        to = Transformer.from_crs(4326, 3857, always_xy=True)
        mx, my = to.transform(s.mlon.to_numpy()[use], s.mlat.to_numpy()[use])
        cells = pd.DataFrame({"cx": np.floor(mx / 10000),
                              "cy": np.floor(my / 10000),
                              "o": s.outing_id.to_numpy()[use]})
        c = cells.groupby(["cx", "cy"]).o.nunique().idxmax()
        cx, cy = (c[0] + 0.5) * 10000, (c[1] + 0.5) * 10000
        use = use[np.argsort(np.hypot(mx - cx, my - cy))[:a.max_segments]]
    print(f"{a.region}: {len(s):,} walking segments, {len(use):,} used "
          f"({s.outing_id.iloc[use].nunique():,} outings), in "
          f"{len(set(owner[use]))} lidar projects", flush=True)
    rows, t0 = [], time.time()
    for pi in sorted(set(owner[use])):
        f = feats[pi]
        idx = use[owner[use] == pi]
        lat = s.mlat.to_numpy()[idx]
        scale = 1 / np.cos(np.radians(lat.mean()))   # mercator m per real m
        boxes = np.array([[p[:, 0].min() - BUF_M * scale,
                           p[:, 1].min() - BUF_M * scale,
                           p[:, 0].max() + BUF_M * scale,
                           p[:, 1].max() + BUF_M * scale]
                          for p in (paths[i] for i in idx)])
        ept = EPT(f["properties"]["url"])
        nodes = ept.nodes(boxes)
        npts = sum(n for _, n in nodes)
        print(f"  {f['properties']['name']}: {len(idx):,} segments, "
              f"{len(nodes):,} blocks, {npts / 1e6:,.0f} M points "
              f"(~{npts * 9 / 1e9:.1f} GB as LAZ)", flush=True)
        if a.dry_run:
            continue
        acc = {i: [] for i in idx}
        for k, (key, _) in enumerate(nodes):
            las = laspy.read(io.BytesIO(get(f"{ept.base}/ept-data/{key}.laz")))
            x, y, z = (np.asarray(las.x), np.asarray(las.y),
                       np.asarray(las.z))
            cls = np.asarray(las.classification)
            rn = np.asarray(las.return_number)
            d, xi, yi, _ = map(int, key.split("-"))
            sz = ept.size / 2 ** d
            nx0, ny0 = ept.x0 + xi * sz, ept.y0 + yi * sz
            hit = np.nonzero((boxes[:, 0] < nx0 + sz) & (boxes[:, 2] > nx0)
                             & (boxes[:, 1] < ny0 + sz)
                             & (boxes[:, 3] > ny0))[0]
            for j in hit:
                b = boxes[j]
                m = (x >= b[0]) & (x <= b[2]) & (y >= b[1]) & (y <= b[3])
                if not m.any():
                    continue
                dist = dist_to_path(x[m], y[m], paths[idx[j]])
                keep = dist <= BUF_M * scale
                if keep.any():
                    acc[idx[j]].append((x[m][keep], y[m][keep], z[m][keep],
                                        cls[m][keep], rn[m][keep],
                                        dist[keep]))
            if k % 200 == 0:
                print(f"    {k:,}/{len(nodes):,} blocks, "
                      f"{time.time() - t0:.0f} s", flush=True)
        for i, parts in acc.items():
            row = {"segment_id": s.segment_id.iat[i]}
            if parts:
                cat = [np.concatenate([p[c] for p in parts])
                       for c in range(6)]
                m = metrics(cat[:5], cat[5], scale)
                if m:
                    row.update(m)
            rows.append(row)
    if a.dry_run:
        return
    out = pd.DataFrame(rows)
    for c in ("nrd", "nrd_center", "cover2m", "hag_p95", "n_pts"):
        if c not in out:
            out[c] = np.nan
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"lidarveg_{a.region}.parquet"
    out.to_parquet(f, index=False)
    print(f"wrote {f}: {len(out):,} segments, vegetation for "
          f"{out.nrd.notna().mean():.0%}, {time.time() - t0:.0f} s")
    print(out.describe().T.round(3).to_string())


if __name__ == "__main__":
    main()
