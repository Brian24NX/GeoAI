#!/usr/bin/env python3
"""
T2 tier 2: understory vegetation from USGS 3DEP lidar POINT CLOUDS around
each walking segment, the measure the plan names (Campbell et al. 2018) and
STRIDE uses: normalized relative density (NRD) = returns between 0.85 and
1.20 m above ground / returns at or below 1.20 m (`stride` package,
dns_fun). 30 m canopy maps carried no signal (decision #87); this is the
fine-scale test.

Point clouds: the public Entwine Point Tiles on AWS
(s3-us-west-2.amazonaws.com/usgs-lidar-public/<project>/), read without an
account: ept.json -> the octree hierarchy -> only the LAZ blocks that touch
a buffer around walked trails (laspy + lazrs). Blocks are fetched 8 at a
time and cached in cache/ept/<project>/ (a re-run downloads nothing). The
project boundaries come from the index hobuinc/usgs-lidar
(cache/ept/resources.geojson).

Per segment, points within BUF_M of its matched path:
  nrd          STRIDE's understory density, 0.85-1.20 m
  nrd_center   the same within 1 m of the centerline (the tread itself)
  cover2m      share of first returns more than 2 m above ground
  hag_p95      95th percentile height above ground (canopy height)
  n_pts        points used
With --strata, also Campbell et al. (2018)'s thin strata, each normalized
by the returns that reached it (returns in the stratum / returns below its
top): nrd_05_15, nrd_15_25, nrd_25_35 (0.5-1.5, 1.5-2.5, 2.5-3.5 m).
Written to data/t2/lidarstrata_<region>.parquet; the default run's
files are untouched.
Height above ground = z minus the ground (class 2) height under the point,
interpolated from its 6 nearest ground returns within 2 m (inverse-distance
weights): no DEM or vertical datum involved, and on a slope the ground
under the point is not taken from one neighbour uphill or downhill.

Finding the points: a grid of 2 m cells covering every buffer drops the
points far from any trail first; the rest get their candidate segments from
a KD-tree of the paths' vertices (densified to <= 1.5 m) and an exact
distance to each candidate's polyline. Results are written per lidar
project and a stopped run resumes.

Run:  python t2_lidarveg.py --region wm --dry-run   (block and size count)
      python t2_lidarveg.py --region wm [--max-segments N] [--workers 8]
      python t2_lidarveg.py --region wm --strata       (adds the strata)
Output: data/t2/lidarveg_<region>.parquet (per-project parts in
        data/t2/lidarveg_parts/)
"""

import argparse
import io
import json
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import laspy
import numpy as np
import pandas as pd
import requests
from matplotlib.path import Path as MPath
from pyproj import Transformer
from scipy.spatial import cKDTree

INDEX = Path("cache/ept/resources.geojson")
CACHE = Path("cache/ept")
SEG = Path("data/t1_all/segments_L50.parquet")
OUT = Path("data/t2")
BUF_M = 3.0                       # buffer around the path (real metres)
CELL = 2.0                        # prefilter grid (mercator metres)
VERTEX = 1.5                      # path densified to this (mercator metres)
K_GROUND, R_GROUND = 6, 2.0       # ground interpolation (points, real m)
STRATA = {"nrd_05_15": (0.5, 1.5), "nrd_15_25": (1.5, 2.5),
          "nrd_25_35": (2.5, 3.5)}   # Campbell et al. 2018, with --strata
WITH_STRATA = False               # set by --strata
AGENT = {"User-Agent": "WashU-MVRL-travel-speed/0.3 (research)"}


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

    def block(self, key, cache):
        """One block's points (x, y, z, class, return number), cached."""
        f = cache / f"{key}.laz"
        if f.exists():
            data = f.read_bytes()
        else:
            data = get(f"{self.base}/ept-data/{key}.laz")
            tmp = f.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.rename(f)
        las = laspy.read(io.BytesIO(data))
        return (np.asarray(las.x), np.asarray(las.y), np.asarray(las.z),
                np.asarray(las.classification, dtype=np.uint8),
                np.asarray(las.return_number, dtype=np.uint8))


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


def densify(path, step):
    """Vertices along a polyline, at most `step` apart."""
    out = [path[:1]]
    for a, b in zip(path[:-1], path[1:]):
        n = max(int(np.ceil(np.hypot(*(b - a)) / step)), 1)
        t = np.arange(1, n + 1)[:, None] / n
        out.append(a + t * (b - a))
    return np.vstack(out)


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


def metrics(x, y, z, cls, rn, dist, scale):
    """Per-segment vegetation numbers from its buffered points (x, y in
    mercator metres relative to the segment, z in metres)."""
    g = cls == 2
    if g.sum() < 10 or len(z) < 50:
        return None
    tree = cKDTree(np.c_[x[g], y[g]])
    dd, ii = tree.query(np.c_[x, y], k=min(K_GROUND, int(g.sum())),
                        distance_upper_bound=R_GROUND * scale)
    dd, ii = np.atleast_2d(dd), np.atleast_2d(ii)
    if dd.shape[0] != len(z):
        dd, ii = dd.T, ii.T
    ok = np.isfinite(dd)
    w = np.where(ok, 1 / np.maximum(dd, 0.05 * scale) ** 2, 0)
    zg_all = np.r_[z[g], np.nan]
    zg = np.nansum(w * np.where(ok, zg_all[np.minimum(ii, g.sum())], 0), 1)
    has = w.sum(1) > 0
    hag = np.full(len(z), np.nan)
    hag[has] = z[has] - zg[has] / w.sum(1)[has]
    low = has & (hag <= 1.20)
    band = low & (hag >= 0.85)
    c = low & (dist <= 1.0 * scale)
    first = has & (rn == 1)
    out = {"nrd": band.sum() / max(low.sum(), 1),
           "nrd_center": (band & c).sum() / max(c.sum(), 1),
           "cover2m": float((hag[first] > 2.0).mean())
           if first.any() else np.nan,
           "hag_p95": float(np.nanpercentile(hag[has], 95)),
           "n_pts": int(has.sum())}
    if WITH_STRATA:      # returns in the stratum / returns that reached it
        for key, (lo, hi) in STRATA.items():
            below = has & (hag < hi)
            out[key] = (below & (hag >= lo)).sum() / max(below.sum(), 1)
    return out


def project_segments(s, paths, idx, ept, nodes, workers, cache, label):
    """Vegetation metrics for the segments idx of one lidar project."""
    lat = s.mlat.to_numpy()[idx]
    scale = 1 / np.cos(np.radians(lat.mean()))      # mercator m per real m
    buf = BUF_M * scale
    # candidate structures: densified vertices -> segment, buffer cells
    vx = [densify(paths[i], VERTEX) for i in idx]
    vseg = np.concatenate([np.full(len(v), j) for j, v in enumerate(vx)])
    vxy = np.vstack(vx)
    tree = cKDTree(vxy)
    reach = int(np.ceil((buf + VERTEX) / CELL))
    cx, cy = np.floor(vxy[:, 0] / CELL).astype(np.int64), \
        np.floor(vxy[:, 1] / CELL).astype(np.int64)
    off = np.arange(-reach, reach + 1)
    cells = np.unique(((cx[:, None, None] + off[None, :, None]) * 4_000_000
                       + (cy[:, None, None] + off[None, None, :]))
                      .ravel())
    origin = np.array([p[0] for p in (paths[i] for i in idx)])
    acc = [[] for _ in idx]
    t0, done, kept = time.time(), 0, 0
    keys = iter(key for key, _ in nodes)
    with ThreadPoolExecutor(workers) as pool:
        window = deque(pool.submit(ept.block, k, cache)
                       for _, k in zip(range(3 * workers), keys))
        while window:                        # a few blocks in flight only
            x, y, z, cls, rn = window.popleft().result()
            k = next(keys, None)
            if k is not None:
                window.append(pool.submit(ept.block, k, cache))
            done += 1
            cid = (np.floor(x / CELL).astype(np.int64) * 4_000_000
                   + np.floor(y / CELL).astype(np.int64))
            pos = np.minimum(np.searchsorted(cells, cid), len(cells) - 1)
            near = np.nonzero(cells[pos] == cid)[0]
            if len(near):
                cand = tree.query_ball_point(np.c_[x[near], y[near]],
                                             r=buf + VERTEX)
                n = np.fromiter((len(c) for c in cand), int, len(cand))
                if n.sum():
                    pi = np.repeat(np.arange(len(near)), n)
                    sj = vseg[np.concatenate([c for c in cand if c])]
                    pair = np.unique(pi * len(idx) + sj)
                    pi, sj = pair // len(idx), pair % len(idx)
                    order = np.argsort(sj, kind="stable")
                    pi, sj = pi[order], sj[order]
                    cut = np.nonzero(np.diff(sj))[0] + 1
                    for p_, j in zip(np.split(pi, cut), sj[np.r_[0, cut]]):
                        q = near[p_]
                        d = dist_to_path(x[q], y[q], paths[idx[j]])
                        m = d <= buf
                        if m.any():
                            q = q[m]
                            acc[j].append((
                                (x[q] - origin[j, 0]).astype(np.float32),
                                (y[q] - origin[j, 1]).astype(np.float32),
                                z[q].astype(np.float32), cls[q], rn[q],
                                d[m].astype(np.float32)))
                            kept += int(m.sum())
            if done % 500 == 0 or done == len(nodes):
                el = time.time() - t0
                print(f"    {label}: {done:,}/{len(nodes):,} blocks, "
                      f"{kept / 1e6:.1f} M points kept, {el / 60:.1f} min, "
                      f"~{el / done * (len(nodes) - done) / 60:.0f} min "
                      "left", flush=True)
    rows = []
    for j, i in enumerate(idx):
        row = {"segment_id": s.segment_id.iat[i]}
        if acc[j]:
            cat = [np.concatenate([p[c] for p in acc[j]]) for c in range(6)]
            m = metrics(*cat[:5], cat[5], scale)
            if m:
                row.update(m)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-segments", type=int, default=0,
                    help="pilot on a spatially compact subset")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--strata", action="store_true",
                    help="add Campbell et al. 2018's three strata; writes "
                         "lidarstrata_<region>.parquet")
    a = ap.parse_args()
    global WITH_STRATA
    WITH_STRATA = a.strata
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
    tag = ""
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
        tag = f"_pilot{a.max_segments}"
    if a.strata:
        tag += "_strata"
    print(f"{a.region}: {len(s):,} walking segments, {len(use):,} used "
          f"({s.outing_id.iloc[use].nunique():,} outings), in "
          f"{len(set(owner[use]))} lidar projects", flush=True)
    (OUT / "lidarveg_parts").mkdir(parents=True, exist_ok=True)
    parts, t0 = [], time.time()
    for pi in sorted(set(owner[use])):
        f = feats[pi]
        name = f["properties"]["name"]
        idx = use[owner[use] == pi]
        part = OUT / "lidarveg_parts" / f"{a.region}{tag}_{name}.parquet"
        if part.exists() and not a.dry_run:
            print(f"  {name}: done before ({part})", flush=True)
            parts.append(pd.read_parquet(part))
            continue
        lat = s.mlat.to_numpy()[idx]
        scale = 1 / np.cos(np.radians(lat.mean()))
        boxes = np.array([[p[:, 0].min() - BUF_M * scale,
                           p[:, 1].min() - BUF_M * scale,
                           p[:, 0].max() + BUF_M * scale,
                           p[:, 1].max() + BUF_M * scale]
                          for p in (paths[i] for i in idx)])
        ept = EPT(f["properties"]["url"])
        nodes = ept.nodes(boxes)
        npts = sum(n for _, n in nodes)
        print(f"  {name}: {len(idx):,} segments, {len(nodes):,} blocks, "
              f"{npts / 1e6:,.0f} M points (~{npts * 9 / 1e9:.1f} GB as "
              "LAZ)", flush=True)
        if a.dry_run:
            continue
        cache = CACHE / name
        cache.mkdir(parents=True, exist_ok=True)
        out = project_segments(s, paths, idx, ept, nodes, a.workers, cache,
                               name)
        out.to_parquet(part, index=False)
        parts.append(out)
    if a.dry_run:
        return
    out = pd.concat(parts, ignore_index=True)
    for c in ("nrd", "nrd_center", "cover2m", "hag_p95", "n_pts",
              *(STRATA if a.strata else ())):
        if c not in out:
            out[c] = np.nan
    f = (OUT / f"lidarstrata_{a.region}.parquet" if a.strata
         and not a.max_segments else OUT / f"lidarveg_{a.region}{tag}.parquet")
    out.to_parquet(f, index=False)
    print(f"wrote {f}: {len(out):,} segments, vegetation for "
          f"{out.nrd.notna().mean():.0%}, {(time.time() - t0) / 60:.0f} min")
    print(out.describe().T.round(3).to_string())


if __name__ == "__main__":
    main()
