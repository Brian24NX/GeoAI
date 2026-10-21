#!/usr/bin/env python3
"""
T1 v2 test: does measuring distance ALONG THE TRAIL between matched GPS
points, instead of the straight line (T1 v1), remove the sparse-trace bias?
Decision #104: thinning dense walks to 30 s loses 5.8% of the distance,
because straight lines between points cut the corners of switchbacks.

For one region's matched points (data/t1_<region>/points.parquet):
  - every matched point is projected onto its OSM way (in UTM), giving its
    position along the way; the projection distance checks that the points
    and the cached ways still agree (it should be ~0 m);
  - between consecutive points on the same way, the route length is the
    difference of positions (the shorter way round on a closed way, e.g. a
    loop trail); across ways, the shortest path through the trail network
    (Dijkstra, cut off at 3 x the straight line + 100 m; no path within
    that, or a way index that does not fit: the straight line);
  - a route longer than 2 x the straight line + 10 m is a matching artifact
    (nobody walks that between two points seconds apart): the straight line
    is kept. First run: 26 same-way pairs of ~180,000 added 60 km.
Then, as in t1_sampling_check.py:
  - dense walking traces (device every <= 5 s) thinned to 10 / 20 / 30 s:
    distance by straight lines and by route, each vs the full-rate
    straight-line distance;
  - all walking traces: route / straight-line distance by recording
    interval (what a T1 v2 would add to each).

Output: results/t1_route_check/<region>_summary.json
Run (cluster): python t1_route_check.py --region wm
"""

import argparse
import heapq
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

import gate1_audit as g
import regions
import t1_build_dataset as b

OUT = Path("results/t1_route_check")
RATES = [10, 20, 30]
IV_BINS = [0, 5, 10, 15, 25, 40, np.inf]


class Network:
    """The region's walkable OSM ways in UTM, as polylines and a graph."""

    def __init__(self, ways, epsg):
        to = Transformer.from_crs(4326, epsg, always_xy=True)
        self.to, self.xy, self.cum, self.ids = to, {}, {}, {}
        node_of, self.adj = {}, defaultdict(list)
        for k, way in enumerate(ways):
            if g.way_class(way.get("tags", {})) not in b.WALKABLE:
                continue
            pts = [p for p in way.get("geometry") or [] if p]
            if len(pts) < 2:
                continue
            lat = np.array([p["lat"] for p in pts])
            lon = np.array([p["lon"] for p in pts])
            xy = np.c_[to.transform(lon, lat)]
            seg = np.hypot(*np.diff(xy, axis=0).T)
            ids = []
            for la, lo in zip(lat, lon):
                ids.append(node_of.setdefault((round(la, 7), round(lo, 7)),
                                              len(node_of)))
            self.xy[k], self.cum[k], self.ids[k] = xy, np.r_[0, np.cumsum(
                seg)], ids
            for i in range(len(ids) - 1):
                if ids[i] != ids[i + 1]:
                    self.adj[ids[i]].append((ids[i + 1], seg[i]))
                    self.adj[ids[i + 1]].append((ids[i], seg[i]))

    def locate(self, k, x, y):
        """(position along way k, segment index, fraction, offset m)."""
        xy = self.xy[k]
        a, d = xy[:-1], np.diff(xy, axis=0)
        l2 = np.maximum((d ** 2).sum(1), 1e-9)
        t = np.clip(((x - a[:, 0]) * d[:, 0] + (y - a[:, 1]) * d[:, 1])
                    / l2, 0, 1)
        off = np.hypot(a[:, 0] + t * d[:, 0] - x, a[:, 1] + t * d[:, 1] - y)
        i = int(np.argmin(off))
        return (float(self.cum[k][i] + t[i] * np.sqrt(l2[i])), i,
                float(t[i]), float(off[i]))

    def route(self, p, q, chord):
        """Route length between two located points (way, pos, i, f)."""
        (k1, m1, i1, f1), (k2, m2, i2, f2) = p, q
        if k1 == k2:
            dm = abs(m2 - m1)
            if self.ids[k1][0] == self.ids[k1][-1]:       # closed way
                dm = min(dm, self.cum[k1][-1] - dm)
            return dm
        cut = 3 * chord + 100
        len1 = self.cum[k1][i1 + 1] - self.cum[k1][i1]
        len2 = self.cum[k2][i2 + 1] - self.cum[k2][i2]
        src = {self.ids[k1][i1]: f1 * len1,
               self.ids[k1][i1 + 1]: (1 - f1) * len1}
        dst = {self.ids[k2][i2]: f2 * len2,
               self.ids[k2][i2 + 1]: (1 - f2) * len2}
        dist, heap, best = dict(src), [(d, n) for n, d in src.items()], np.inf
        heapq.heapify(heap)
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist.get(n, np.inf) or d > min(cut, best):
                continue
            if n in dst:
                best = min(best, d + dst[n])
            for nb, w in self.adj[n]:
                nd = d + w
                if nd < dist.get(nb, np.inf) and nd <= cut:
                    dist[nb] = nd
                    heapq.heappush(heap, (nd, nb))
        return best if best <= cut else chord


def piece_lengths(net, p, idx):
    """Straight-line and route length over the points idx of one piece."""
    x, y = p.x.to_numpy()[idx], p.y.to_numpy()[idx]
    loc = p["loc_"].to_numpy()[idx]
    chord = np.hypot(np.diff(x), np.diff(y))
    route = np.array([net.route(loc[j], loc[j + 1], chord[j])
                      if loc[j] and loc[j + 1] else chord[j]
                      for j in range(len(idx) - 1)])
    route = np.where(route > 2 * chord + 10, chord, route)   # artifacts
    return float(chord.sum()), float(route.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="wm")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    key = args.region
    net = Network(b.load_ways(regions.region_name(key), regions.tiles(key)),
                  regions.utm_epsg(key))
    d = regions.data_dir(key)
    tr = pd.read_csv(d / "traces.csv")
    md = pd.read_csv(d / "modes.csv")
    walk = set(md.loc[md["mode"] == "walk", "trace_id"]) & set(
        tr.loc[tr.hiking_trace, "trace_id"])
    pts = pd.read_parquet(d / "points.parquet", columns=[
        "trace_id", "piece", "t", "mlat", "mlon", "way_index", "native_dt"])
    pts = pts[pts.trace_id.isin(walk) & pts.mlat.notna()].sort_values(
        ["trace_id", "piece", "t"]).reset_index(drop=True)
    pts["x"], pts["y"] = net.to.transform(pts.mlon.to_numpy(),
                                          pts.mlat.to_numpy())
    locs, offs = [], []
    for k, x, y in zip(pts.way_index, pts.x, pts.y):
        if k in net.xy:
            m, i, f, off = net.locate(k, x, y)
            locs.append((k, m, i, f))
            offs.append(off)
        else:
            locs.append(None)
            offs.append(np.nan)
    pts["loc_"], pts["off"] = locs, offs
    print(f"{len(pts):,} walking points; projection offset median "
          f"{np.nanmedian(offs):.2f} m, 99% {np.nanpercentile(offs, 99):.1f}"
          " m", flush=True)

    nat = pts.groupby("trace_id").native_dt.median()
    rows = []
    for (tid, piece), p in pts.groupby(["trace_id", "piece"], sort=False):
        p = p.reset_index(drop=True)
        t = p.t.to_numpy()
        rec = {"trace_id": tid, "native_dt": nat[tid]}
        rec["chord_5"], rec["route_5"] = piece_lengths(net, p,
                                                       np.arange(len(p)))
        if nat[tid] <= 5:
            for r in RATES:
                idx = np.unique(np.r_[g.thin(t, r), len(t) - 1])
                if len(idx) >= 2:
                    rec[f"chord_{r}"], rec[f"route_{r}"] = piece_lengths(
                        net, p, idx)
        rows.append(rec)
    r = pd.DataFrame(rows).groupby("trace_id").sum(min_count=1)
    r["native_dt"] = nat.reindex(r.index)
    dense = r[(r.native_dt <= 5)].dropna()
    base = dense.chord_5.sum()
    summary = {
        "region": key, "walking_points": int(len(pts)),
        "projection_offset_m": {
            "median": float(np.nanmedian(offs)),
            "p99": float(np.nanpercentile(offs, 99)),
            "unlocated_share": float(np.mean(np.isnan(offs)))},
        "dense_traces": int(len(dense)),
        "dense_full_rate_route_vs_chord": float(dense.route_5.sum() / base),
        "thinned": {str(rt): {
            "chord_vs_full": float(dense[f"chord_{rt}"].sum() / base),
            "route_vs_full": float(dense[f"route_{rt}"].sum() / base)}
            for rt in RATES},
        "all_traces_route_vs_chord_by_interval": {
            str(iv): {"traces": int(len(x)),
                      "ratio": float(x.route_5.sum() / x.chord_5.sum())}
            for iv, x in r.groupby(pd.cut(r.native_dt, IV_BINS),
                                   observed=True)}}
    (OUT / f"{key}_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
