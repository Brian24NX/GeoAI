#!/usr/bin/env python3
"""
T1 step 5 (prototype): HMM map-matching of real hikes onto the OSM network.

Uses leuvenmapmatching, an HMM matcher in the spirit of Newson & Krumm (2009),
on the Gate 1 White Mountains sample that is already cached (GPS pages and
OSM ways for the Mt Washington box), so it downloads nothing.

For each hiking trace it reports:
  * matched share  -- how much of the trace the matcher could follow
  * distance       -- how far the GPS points sit from the matched way
  * on trails      -- share of matched points on trail (not road/track) edges
  * agreement      -- how often the HMM's way type equals the Gate 1
                      nearest-way rule
and saves a figure of the trace with its matched path.

Run:  python t1_mapmatch_test.py
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from leuvenmapmatching.map.inmem import InMemMap
from leuvenmapmatching.matcher.distance import DistanceMatcher

import gate1_audit as g

REGION, BOX = "white_mountains", g.REGIONS["white_mountains"][0]
OUT = Path("results/t1_mapmatch")
WALKABLE = ("trail", "track", "road")    # ways a hiker can be on

# Matcher settings (starting points; tune once we hand-check failures)
SETTINGS = dict(
    obs_noise=15,        # GPS error under canopy, 1 sd (m)
    obs_noise_ne=30,     # same, for points between observations (m)
    dist_noise=15,       # mismatch between path length and GPS step (m)
    max_dist=60,         # hard cut: farther than this = no candidate (m)
    max_dist_init=60,
    non_emitting_states=True,
    max_lattice_width=8,
    only_edges=True,
)


def build_graph(ways):
    """Routable graph from OSM ways; junction nodes share coordinates."""
    graph = InMemMap("osm", use_latlon=True, use_rtree=True,
                     index_edges=True)
    node_of, edge_class = {}, {}

    def node(lat, lon):
        key = (round(lat, 7), round(lon, 7))
        if key not in node_of:
            node_of[key] = len(node_of)
            graph.add_node(node_of[key], (lat, lon))
        return node_of[key]

    for way in ways:
        cls = g.way_class(way.get("tags", {}))
        if cls not in WALKABLE:
            continue
        ids = [node(p["lat"], p["lon"])
               for p in way.get("geometry") or [] if p]
        for a, b in zip(ids[:-1], ids[1:]):
            if a != b:
                graph.add_edge(a, b)
                graph.add_edge(b, a)
                edge_class[(a, b)] = edge_class[(b, a)] = cls
    return graph, edge_class, len(node_of)


def match_trace(graph, edge_class, lat, lon):
    """Match a whole trace; restart after breaks. Per-point results."""
    n = len(lat)
    out = pd.DataFrame({"lat": lat, "lon": lon, "matched": False,
                        "dist_m": np.nan, "cls": None,
                        "mlat": np.nan, "mlon": np.nan})
    i = 0
    while i < n - 1:
        matcher = DistanceMatcher(graph, **SETTINGS)
        path = list(zip(lat[i:], lon[i:]))
        try:
            _, last = matcher.match(path)
        except Exception:                    # no candidates near the start
            last = -1
        if last < 1:
            i += 1                           # skip this point, try the next
            continue
        for m in matcher.lattice_best:
            if not m.is_emitting():
                continue
            k = i + m.obs
            if k > i + last:
                continue
            out.at[k, "matched"] = True
            out.at[k, "dist_m"] = m.dist_obs
            out.at[k, "cls"] = edge_class.get((m.edge_m.l1, m.edge_m.l2))
            out.at[k, "mlat"], out.at[k, "mlon"] = m.edge_m.pi
        i += last + 1
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    texts, info, _ = g.download_box("cache", REGION, BOX, offline=True)
    traces = [t for t in g.timed_traces(texts, info)
              if g.classify(t) in g.USABLE]
    ways = g.get_ways("cache", REGION, BOX, offline=True)
    t0 = time.time()
    graph, edge_class, n_nodes = build_graph(ways)
    print(f"graph: {n_nodes:,} nodes, {len(edge_class) // 2:,} edges "
          f"({time.time() - t0:.1f} s)")
    nearest = g.WayMatcher(ways, BOX)

    table = pd.read_csv(Path("results") / REGION / "traces.csv")
    hikes = table[(table.box == BOX[0]) & (table.trail_moving_min >= 5)]
    wanted = set(zip(hikes.start_utc, hikes.n_points))
    rows, seen = [], set()
    for k, trace in enumerate(traces):
        fp = g.fingerprint(trace)
        if fp in seen:                        # same recording uploaded twice
            continue
        seen.add(fp)
        pts = g.all_points(trace)
        start = min(p[2] for p in pts).strftime("%Y-%m-%dT%H:%M:%SZ")
        if (start, len(pts)) not in wanted:
            continue
        lat, lon, t, _ = g.clean_segment(sorted(pts, key=lambda p: p[2]))
        keep = g.thin(t)                      # points >= 10 s apart
        lat, lon = lat[keep], lon[keep]
        t1 = time.time()
        res = match_trace(graph, edge_class, lat, lon)
        secs = time.time() - t1
        near_cls = np.array(g.CLASSES)[nearest.cls[nearest.match(lat, lon)]]
        m = res["matched"].to_numpy()
        agree = (res.loc[m, "cls"].to_numpy() == near_cls[m]).mean() \
            if m.any() else np.nan
        rows.append({
            "start_utc": start, "points": len(lat),
            "matched_share": m.mean(),
            "median_dist_m": res.loc[m, "dist_m"].median(),
            "p90_dist_m": res.loc[m, "dist_m"].quantile(0.9),
            "on_trail_share": (res.loc[m, "cls"] == "trail").mean(),
            "agree_with_nearest": agree,
            "seconds": secs,
        })
        print(f"  {start}  {len(lat):5d} pts  matched {100 * m.mean():5.1f}%"
              f"  median {rows[-1]['median_dist_m']:5.1f} m  "
              f"trail {100 * rows[-1]['on_trail_share']:5.1f}%  "
              f"agree {100 * agree:5.1f}%  ({secs:.0f} s)")
        if len(rows) <= 3:
            plot(res, ways, OUT / f"match_{start[:10]}_{len(pts)}.png")
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "match_summary.csv", index=False)
    print(f"\n{len(df)} hikes: median matched share "
          f"{100 * df.matched_share.median():.1f}%, median GPS-to-way "
          f"distance {df.median_dist_m.median():.1f} m, agreement with "
          f"nearest-way {100 * df.agree_with_nearest.median():.1f}%")


def plot(res, ways, path):
    fig, ax = plt.subplots(figsize=(7, 5.5))
    for way in ways:
        cls = g.way_class(way.get("tags", {}))
        geom = [p for p in way.get("geometry") or [] if p]
        if cls in WALKABLE and len(geom) > 1:
            ax.plot([p["lon"] for p in geom], [p["lat"] for p in geom],
                    color="#bdbdbd" if cls == "trail" else "#e3cfa6",
                    lw=0.7, zorder=1)
    m = res["matched"]
    ax.scatter(res.lon[~m], res.lat[~m], s=6, color="#D85A30", zorder=3,
               label="GPS point, not matched")
    ax.scatter(res.lon[m], res.lat[m], s=3, color="#185FA5", zorder=2,
               label="GPS point, matched")
    # draw the matched path, broken wherever the trace jumps (new day,
    # left the box) so separate pieces aren't joined by straight lines
    mm = res[m]
    jump = g.haversine_m(mm.lat.values[:-1], mm.lon.values[:-1],
                         mm.lat.values[1:], mm.lon.values[1:]) > 300
    xs, ys = [], []
    for k in range(len(mm)):
        xs.append(mm.mlon.values[k])
        ys.append(mm.mlat.values[k])
        if k < len(jump) and jump[k]:
            xs.append(np.nan)
            ys.append(np.nan)
    ax.plot(xs, ys, color="#1D9E75", lw=1.2, zorder=4,
            label="matched position on the trail")
    pad = 0.004
    ax.set_xlim(res.lon.min() - pad, res.lon.max() + pad)
    ax.set_ylim(res.lat.min() - pad, res.lat.max() + pad)
    ax.set_aspect(1 / np.cos(np.radians(res.lat.mean())))
    ax.legend(fontsize=7, loc="best")
    ax.set_title(f"HMM map-matching: {100 * m.mean():.0f}% of points matched",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
