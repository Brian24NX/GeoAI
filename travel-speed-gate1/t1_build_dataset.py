#!/usr/bin/env python3
"""
T1: build the trajectory dataset (semester plan sec. 8).

Input: the cached T1 download for one region (t1_download.py): GPS pages and
OSM ways for every tile, plus the original GPX files of identifiable traces;
and, when present, the lab's original files of public + identifiable traces
uploaded 2016-2022 (cache/lab_traces/<region>.parquet, from
cluster/extract_lab_traces.py).

For every hike it:
  1. collects the trace once: identifiable traces use the full original file
     (whole hike) when we have it, otherwise their tile pieces joined by URL;
     anonymous (trackable) pieces are stitched across tile edges by time;
     lab traces are added unless the API already gave the same trace id;
     car loggers and duplicate uploads are dropped;
  2. cleans each recording (repeated timestamps, >60 km/h steps) and splits
     it at gaps > 5 min;
  3. flags stops (stop rule below; to be tuned on the hand-labeled sheet);
  4. map-matches it to the OSM network with an HMM (leuvenmapmatching);
  5. cuts the matched path into fixed-length segments (50 m and 25 m) and
     records, per segment: length, wall-clock and moving time, speed, signed
     slope along the direction of travel (5 m USGS DEM), direction relative to
     the OSM way, way type and trail tags, permitted modes, match error,
     sampling interval, date / day of year, and uploader;
  6. keeps the cleaned, matched point sequences as well (plan sec. 8: "keep
     the cleaned point sequences, not only the aggregated table").

Sign convention (plan sec. 8, "write a test for the sign convention"):
slope = rise / run in the direction of travel, positive = uphill. A
synthetic test runs first and the script stops if it fails.

Output (data/t1_<region>/, e.g. data/t1_white_mountains/):
  segments_L50.parquet, segments_L25.parquet   one row per traversal
  points.parquet                               cleaned matched points
  traces.csv                                   one row per hike
  data_card.md                                 counts and every setting used

Run:  python t1_build_dataset.py                    (White Mountains)
      python t1_build_dataset.py --region cascades  (any key in regions.py)
      python t1_build_dataset.py --sample           (Gate 1 WM boxes)
"""

import argparse
import bz2
import gzip
import io
import json
import re
import tarfile
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import gate1_audit as g
import first_look_slope as fl
import regions

# ------------------------------------------------------------------ settings
SEGMENT_LENGTHS = (50.0, 25.0)       # meters (plan sec. 8: 25 or 50 m)
THIN_S = 5.0                         # keep points >= 5 s apart for matching
GAP_S = g.MAX_GAP_S                  # split recordings at gaps > 5 min
STITCH_S = 600.0                     # join anonymous pieces <= 10 min apart
STITCH_M = 1000.0                    #   and <= 1 km apart
# Stop rules: (kind, seconds, meters or km/h). The draft is the default;
# the others exist for the sensitivity check (results under each rule).
STOP_RULES = {
    "window60_10": ("window", 60, 10),   # draft: 60 s ending < 10 m away
    "window30_5": ("window", 30, 5),     # stricter
    "window90_15": ("window", 90, 15),   # looser
    "crude05": ("crude", 0, 0.5),        # plan sec. 6: step speed < 0.5 km/h
}
DEFAULT_STOP_RULE = "window60_10"
MIN_MOVING_TRAIL_MIN = g.MIN_TRAIL_MIN
SUSPECT_KMH = 30.0                   # flag (don't drop) faster segments
SUSPECT_SLOPE = 0.8                  #   and steeper than 80% over a segment
CAR_LOGGERS = {"sunnypilot", "dragonpilot", "openpilot", "frogpilot"}
WALKABLE = ("trail", "track", "road")
TZ = ZoneInfo("America/New_York")
MATCH = dict(obs_noise=15, obs_noise_ne=30, dist_noise=15, max_dist=60,
             max_dist_init=60, non_emitting_states=True,
             max_lattice_width=8, only_edges=True)
GPX_DIR = Path("cache/t1_gpx")
MAX_PAGES = 2000                                # = t1_download.MAX_PAGES
LAB_DIR = Path("cache/lab_traces")              # cluster/extract_lab_traces.py
LAB_UPLOADERS = Path("cache/lab_index/uploaders.parquet")
LAB_MIN_POINTS = 10                             # inside the region
DATE_OK_FROM = 2005                             # earlier = clock bug (flag)
SAME_RECORDING = 0.5      # share of the shorter trace's points (same second,
                          # same ~10 m) found in another = one recording
OUTING_S, OUTING_M = 15 * 60, 1000.0   # starts this close = one outing


# ------------------------------------------------------------ collect traces
def _open_any(path):
    """Text of an uploaded trace file (plain, gzip, bzip2, zip or tar)."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    elif raw[:3] == b"BZh":
        raw = bz2.decompress(raw)
    if raw[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".gpx")]
            return [z.read(n).decode("utf-8", "replace") for n in names]
    if len(raw) > 262 and raw[257:262] == b"ustar":
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:
            return [t.extractfile(m).read().decode("utf-8", "replace")
                    for m in t.getmembers()
                    if m.isfile() and m.name.lower().endswith(".gpx")]
    return [raw.decode("utf-8", "replace")]


def read_original_gpx(path, bbox):
    """Segments [(lat, lon, time)] from an original upload, clipped to bbox."""
    import xml.etree.ElementTree as ET
    w, s, e, n = bbox
    segments = []
    for text in _open_any(path):
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError:
            continue
        for seg in root.iter():
            if g._local(seg.tag) != "trkseg":
                continue
            pts = []
            for pt in seg:
                if g._local(pt.tag) != "trkpt":
                    continue
                when = None
                for sub in pt:
                    if g._local(sub.tag) == "time":
                        when = g.parse_time(sub.text)
                try:
                    lat, lon = float(pt.get("lat")), float(pt.get("lon"))
                except (TypeError, ValueError):
                    continue                # corrupt point (seen: NMEA text
                                            # like "-$GPGG" as a coordinate)
                if when is not None and w <= lon <= e and s <= lat <= n:
                    pts.append((lat, lon, when))
            if len(pts) >= 2:
                segments.append(pts)
    return segments


def read_lab_traces(key, bbox):
    """Lab crawl traces for one region, clipped to bbox, in the same form as
    the API traces: [{"url", "user", "segments": [[(lat, lon, time)]]}].

    The crawl has the ORIGINAL uploaded files of public + identifiable
    traces, so the points keep their timestamps (the API strips them from
    public traces)."""
    path = LAB_DIR / f"{key}.parquet"
    if key is None or not path.exists():
        return []
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    users = pd.read_parquet(LAB_UPLOADERS).drop_duplicates("trace_id") \
        .set_index("trace_id").user
    tab = pq.read_table(path)
    coords = tab.column("point_coordinates").combine_chunks()
    n_pts = pc.list_value_length(coords).to_numpy(zero_copy_only=False)
    cum = np.r_[0, np.cumsum(np.nan_to_num(n_pts).astype(np.int64))]
    xy = coords.flatten().flatten().to_numpy(zero_copy_only=False)
    if len(xy) != 2 * cum[-1]:
        raise ValueError(f"{path}: points are not (lon, lat) pairs")
    xy = xy.reshape(-1, 2)
    us = tab.column("point_timestamps").combine_chunks().flatten() \
        .cast(pa.int64()).to_numpy(zero_copy_only=False).astype(float)
    seg = tab.column("point_segment_indices").combine_chunks().flatten() \
        .to_numpy(zero_copy_only=False).astype(float)
    w, s, e, n = bbox
    out = []
    for i, tid in enumerate(tab.column("trace_id").to_pylist()):
        a, b = cum[i], cum[i + 1]
        lon, lat, t, sg = xy[a:b, 0], xy[a:b, 1], us[a:b], seg[a:b]
        keep = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n) \
            & np.isfinite(t)
        if keep.sum() < LAB_MIN_POINTS:
            continue
        segments = []
        for k in np.unique(sg[keep]):
            m = keep & (sg == k)
            segments.append([(float(la), float(lo), datetime.fromtimestamp(
                tt / 1e6, tz=timezone.utc))
                for la, lo, tt in zip(lat[m], lon[m], t[m])])
        user = users.get(str(tid))
        out.append({"url": f"https://www.openstreetmap.org/user/"
                           f"{user or 'unknown'}/traces/{tid}",
                    "user": user, "segments": [x for x in segments
                                               if len(x) >= 2],
                    "source": "lab original file"})
    return out


def _trace_id(url):
    m = re.search(r"/traces/(\d+)", url or "")
    return int(m.group(1)) if m else None


def collect_traces(region, boxes, bbox, lab_key=None):
    """Every hike once. Returns (list of traces, counts for the data card)."""
    by_url, anon, counts = {}, [], defaultdict(int)
    for box in boxes:
        texts, info, _ = g.download_box("cache", region, box, offline=True,
                                        max_pages=MAX_PAGES)
        for tr in g.timed_traces(texts, info):
            if g.classify(tr) not in g.USABLE:
                continue
            user = g.user_of(tr["url"])
            if user and user.lower() in CAR_LOGGERS:
                counts["car_logger_pieces"] += 1
                continue
            if tr["url"]:
                rec = by_url.setdefault(tr["url"], {"url": tr["url"],
                                                    "user": user,
                                                    "segments": []})
                rec["segments"].extend(tr["segments"])
            else:
                anon.append({"url": None, "user": None,
                             "segments": tr["segments"], "box": box[0]})

    traces = []
    for url, rec in by_url.items():
        tid = _trace_id(url)
        files = sorted(GPX_DIR.glob(f"{tid}.*")) if tid else []
        files = [f for f in files if not f.name.endswith(".tmp")]
        if files:
            segs = read_original_gpx(files[0], bbox)
            if segs:
                rec = dict(rec, segments=segs, source="original GPX")
                counts["identifiable_full_gpx"] += 1
            else:
                rec = dict(rec, source="tile pieces")
                counts["identifiable_gpx_unreadable"] += 1
        else:
            rec = dict(rec, source="tile pieces")
            counts["identifiable_tile_pieces"] += 1
        traces.append(rec)

    # stitch anonymous pieces that continue across a tile edge
    anon.sort(key=lambda r: min(p[2] for s in r["segments"] for p in s))
    stitched = []
    for rec in anon:
        first = min((p for s in rec["segments"] for p in s),
                    key=lambda p: p[2])
        joined = False
        for prev in stitched[-30:]:
            last = max((p for s in prev["segments"] for p in s),
                       key=lambda p: p[2])
            gap = (first[2] - last[2]).total_seconds()
            if 0 <= gap <= STITCH_S and prev.get("box") != rec["box"] and \
                    g.haversine_m(last[0], last[1], first[0], first[1]) \
                    <= STITCH_M:
                prev["segments"].extend(rec["segments"])
                prev["box"] = rec["box"]
                counts["anonymous_pieces_stitched"] += 1
                joined = True
                break
        if not joined:
            stitched.append(dict(rec, source="tile pieces"))
    traces += stitched

    # lab crawl: original files of public + identifiable traces (2016-2022)
    api_ids = {_trace_id(t["url"]) for t in traces if t["url"]}
    for rec in read_lab_traces(lab_key, bbox):
        if _trace_id(rec["url"]) in api_ids:
            counts["lab_traces_already_from_api"] += 1
        elif rec["user"] and rec["user"].lower() in CAR_LOGGERS:
            counts["lab_car_loggers"] += 1
        elif rec["segments"]:
            traces.append(rec)
            counts["lab_traces_added"] += 1

    # drop the same recording uploaded twice: exact copies, then partial
    # copies (one upload holding most of another's points)
    seen, unique = set(), []
    for tr in traces:
        fp = g.fingerprint(tr)
        if fp in seen:
            counts["duplicates_dropped"] += 1
            continue
        seen.add(fp)
        unique.append(tr)
    unique = drop_near_duplicates(unique, counts)
    for tr in unique:
        tid = _trace_id(tr["url"])
        # stable ids: OSM trace id, or a hash of the points for anonymous ones
        tr["trace_id"] = f"osm{tid}" if tid else \
            f"anon{abs(g.fingerprint(tr)) % 10**10:010d}"
        tr["uploader"] = tr["user"] or f"anon:{tr['trace_id']}"
    counts["named"] = sum(1 for t in unique if t["url"])
    counts["anonymous"] = sum(1 for t in unique if not t["url"])
    return unique, dict(counts)


def _keys(tr):
    return {(int(p[2].timestamp()), round(p[0], 4), round(p[1], 4))
            for p in g.all_points(tr)}


def drop_near_duplicates(traces, counts):
    """Same recording uploaded twice but not identical (re-trimmed, thinned,
    or joined to other pieces): if >= SAME_RECORDING of the shorter trace's
    points (same second, same ~10 m) are in the longer one, keep the longer.
    Two phones on one hike share times but not exact positions, so they stay
    (they become one outing, see outing_ids)."""
    span = []
    for i, tr in enumerate(traces):
        ts = [p[2].timestamp() for p in g.all_points(tr)]
        span.append((min(ts), max(ts), i) if ts else (np.inf, np.inf, i))
    span.sort()
    keys, drop = {}, set()
    for a in range(len(span)):
        t0, t1, i = span[a]
        for b in range(a + 1, len(span)):
            u0, u1, j = span[b]
            if u0 > t1:
                break                      # sorted by start: no more overlap
            if i in drop or j in drop:
                continue
            ki = keys.setdefault(i, _keys(traces[i]))
            kj = keys.setdefault(j, _keys(traces[j]))
            small, big = (i, j) if len(ki) <= len(kj) else (j, i)
            if len(ki & kj) >= SAME_RECORDING * min(len(ki), len(kj)):
                drop.add(small)
    counts["near_duplicates_dropped"] = len(drop)
    return [t for k, t in enumerate(traces) if k not in drop]


def outing_ids(starts):
    """One id per group of traces that start within OUTING_S and OUTING_M of
    each other (a group hike with two phones = one outing; plan sec. 9:
    the effective sample size is the number of independent hikes).
    starts: DataFrame trace_id, t0 (epoch s), lat0, lon0."""
    st = starts.sort_values("t0").reset_index(drop=True)
    parent = list(range(len(st)))

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    t, la, lo = st.t0.to_numpy(), st.lat0.to_numpy(), st.lon0.to_numpy()
    for a in range(len(st)):
        for b in range(a + 1, len(st)):
            if t[b] - t[a] > OUTING_S:
                break
            if g.haversine_m(la[a], lo[a], la[b], lo[b]) <= OUTING_M:
                parent[root(b)] = root(a)
    roots = [root(k) for k in range(len(st))]
    first = {r: st.trace_id[r] for r in set(roots)}
    return dict(zip(st.trace_id, (f"out_{first[r]}" for r in roots)))


# -------------------------------------------------------------- the network
def load_ways(region, boxes):
    ways, seen = [], set()
    for box in boxes:
        for w in g.get_ways("cache", region, box, offline=True) or []:
            if w["id"] not in seen:
                seen.add(w["id"])
                ways.append(w)
    return ways


def build_graph(ways):
    """Routable graph; each directed edge remembers its way and direction."""
    from leuvenmapmatching.map.inmem import InMemMap
    graph = InMemMap("osm", use_latlon=True, use_rtree=True,
                     index_edges=True)
    node_of, edge = {}, {}

    def node(lat, lon):
        key = (round(lat, 7), round(lon, 7))
        if key not in node_of:
            node_of[key] = len(node_of)
            graph.add_node(node_of[key], (lat, lon))
        return node_of[key]

    for k, way in enumerate(ways):
        if g.way_class(way.get("tags", {})) not in WALKABLE:
            continue
        ids = [node(p["lat"], p["lon"])
               for p in way.get("geometry") or [] if p]
        for a, b in zip(ids[:-1], ids[1:]):
            if a != b:
                graph.add_edge(a, b)
                graph.add_edge(b, a)
                edge[(a, b)] = (k, +1)       # along the way's node order
                edge[(b, a)] = (k, -1)       # against it
    return graph, edge


# ---------------------------------------------------------- worker globals
W = {}


def init_worker(region, boxes, stop_rule=DEFAULT_STOP_RULE):
    init_layers(region, boxes, stop_rule)
    W["graph"], W["edge"] = build_graph(W["ways"])


def init_layers(region, boxes, stop_rule=DEFAULT_STOP_RULE):
    """Everything except the routable graph (enough to rebuild segments)."""
    key = regions.key_of(region)
    W["tz"] = ZoneInfo(regions.tz(key)) if key else TZ
    ways = load_ways(region, boxes)
    W["ways"] = ways
    W["stop_rule"] = stop_rule
    W["cls"] = [g.way_class(w.get("tags", {})) for w in ways]
    W["perm"] = [g.PERMISSIONS[g.permission(w.get("tags", {}))]
                 if c == "trail" else None
                 for w, c in zip(ways, W["cls"])]
    # (no elevation grids here: 48 grids x 8 workers would not fit in RAM;
    #  add_elevation() runs once in the main process instead)


def dem_pieces(region, boxes):
    """Cached 5 m grids for these boxes, loaded ONE AT A TIME (lazily)."""
    for b in boxes:
        for tif in sorted(Path("cache/layers").glob(
                f"{region}_{b[0]}*_dem5m.tif")):
            yield fl.dem(Path("cache/layers"),
                         tif.name[:-len("_dem5m.tif")], None)


def add_elevation(df, dems):
    """Elevation at both ends, signed slope (+ = uphill) and suspect flag."""
    ends = {k: (df[f"lat{k}"].to_numpy(), df[f"lon{k}"].to_numpy(),
                np.full(len(df), np.nan)) for k in "01"}
    for a, (w, s, e, n) in dems:
        for lat, lon, z in ends.values():
            inside = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n) & \
                np.isnan(z)
            if inside.any():
                z[inside] = fl.sample(a, (w, s, e, n), lat[inside],
                                      lon[inside])
    df["z0_m"], df["z1_m"] = ends["0"][2], ends["1"][2]
    df["slope"] = (df.z1_m - df.z0_m) / df.length_m    # along travel
    # implausible values: matching glitch, DEM edge or bridge -> flag
    df["suspect"] = (df.speed_kmh > SUSPECT_KMH) | \
        (df.slope.abs() > SUSPECT_SLOPE) | (df.match_err_m > 40)
    return df


# ----------------------------------------------------------- per-trace work
def runs_of(segment):
    """Clean one recording and split it at long gaps."""
    lat, lon, t, _ = g.clean_segment(segment)
    if len(t) < 2:
        return []
    v, dt, _ = g.steps(lat, lon, t)
    cut = np.where((dt > GAP_S) | (v > g.FAST_SPEED_KMH))[0]
    out, start = [], 0
    for c in list(cut) + [len(t) - 1]:
        stop = c + 1
        if stop - start >= 3:
            out.append((lat[start:stop], lon[start:stop], t[start:stop]))
        start = c + 1
    return out


def match_run(lat, lon):
    """HMM-match one run; restart after breaks. Per-point results."""
    from leuvenmapmatching.matcher.distance import DistanceMatcher
    n = len(lat)
    mlat, mlon = np.full(n, np.nan), np.full(n, np.nan)
    err, way, direction = np.full(n, np.nan), np.full(n, -1), np.zeros(n)
    i = 0
    while i < n - 1:
        m = DistanceMatcher(W["graph"], **MATCH)
        try:
            _, last = m.match(list(zip(lat[i:], lon[i:])))
        except Exception:
            last = -1
        if last < 1:
            i += 1
            continue
        for st in m.lattice_best:
            if not st.is_emitting():
                continue
            k = i + st.obs
            if k > i + last:
                continue
            mlat[k], mlon[k] = st.edge_m.pi
            err[k] = st.dist_obs
            wk, d = W["edge"].get((st.edge_m.l1, st.edge_m.l2), (-1, 0))
            way[k], direction[k] = wk, d
        i += last + 1
    return mlat, mlon, err, way, direction


def stop_mask(lat, lon, t, rule=None):
    """Per-step stop flags under one of STOP_RULES."""
    kind, secs, size = STOP_RULES[rule or W.get("stop_rule",
                                                  DEFAULT_STOP_RULE)]
    n = len(t)
    if n < 2:
        return np.zeros(0, bool)
    if kind == "crude":
        v, _, _ = g.steps(lat, lon, t)
        return v < size
    j = np.searchsorted(t, t + secs, side="left")
    i_idx = np.nonzero(j < n)[0]
    j_idx = j[i_idx]
    d = g.haversine_m(lat[i_idx], lon[i_idx], lat[j_idx], lon[j_idx])
    ok = d < size
    mark = np.zeros(n, int)
    np.add.at(mark, i_idx[ok], 1)
    np.add.at(mark, j_idx[ok], -1)
    return np.cumsum(mark)[:-1] > 0


def segments_of_piece(p, L, base):
    """Cut one continuously matched piece into L-meter segments."""
    rows = []
    step = g.haversine_m(p["mlat"][:-1], p["mlon"][:-1], p["mlat"][1:],
                         p["mlon"][1:])
    step[p["stopped"]] = 0.0                 # standing still adds no distance
    dist = np.r_[0.0, np.cumsum(step)]
    dt = np.diff(p["t"])
    t_move = np.r_[0.0, np.cumsum(np.where(p["stopped"], 0.0, dt))]
    total = dist[-1]
    if total < L:
        return rows
    # strictly increasing distance axis for interpolation
    d_axis = dist + np.arange(len(dist)) * 1e-6
    edges = np.arange(0, total - L + 1e-9, L)
    moved_in = np.r_[True, ~p["stopped"]]    # skip stop wobble in geometry
    for k, d0 in enumerate(edges):
        d1 = d0 + L
        ta, tb = np.interp([d0, d1], d_axis, p["t"])
        ma, mb = np.interp([d0, d1], d_axis, t_move)
        la = np.interp([d0, d1], d_axis, p["mlat"])
        lo = np.interp([d0, d1], d_axis, p["mlon"])
        inside = (d_axis >= d0) & (d_axis <= d1)
        idx = np.nonzero(inside)[0]
        if len(idx) == 0:
            idx = np.array([np.searchsorted(d_axis, d0)])
            idx = np.clip(idx, 0, len(d_axis) - 1)
        ways_here = p["way"][idx]
        ways_here = ways_here[ways_here >= 0]
        wk = int(np.bincount(ways_here).argmax()) if len(ways_here) else -1
        dirs = p["direction"][idx][p["way"][idx] == wk]
        # plan sec. 8 schema: segment id and geometry (the matched path)
        mid = (d_axis > d0) & (d_axis < d1) & moved_in
        path = zip(np.r_[lo[0], p["mlon"][mid], lo[1]],
                   np.r_[la[0], p["mlat"][mid], la[1]])
        rows.append({**base,
                     "segment_id": f"{base.get('trace_id', 'x')}_p"
                                   f"{base.get('piece', 0)}_L{int(L)}_{k}",
                     "geometry_wkt": "LINESTRING(" + ", ".join(
                         f"{x:.7f} {y:.7f}" for x, y in path) + ")",
                     "seg_index": k, "length_m": L,
                     "lat0": la[0], "lon0": lo[0], "lat1": la[1],
                     "lon1": lo[1],
                     "t_start": ta, "elapsed_s": tb - ta,
                     "moving_s": mb - ma,
                     "way_index": wk,
                     "way_dir": int(np.sign(dirs.sum())) if len(dirs) else 0,
                     "match_err_m": float(np.nanmedian(p["err"][idx])),
                     "n_points": int(len(idx)),
                     "native_interval_s": p.get("native_dt", np.nan)})
    return rows


def process_trace(tr):
    """All segments, a summary row and the matched points for one hike."""
    pieces, n_pts, n_matched = [], 0, 0
    stopped_s = total_s = 0.0
    for seg in tr["segments"]:
        for lat, lon, t in runs_of(seg):
            k = g.thin(t, THIN_S)
            if len(k) < 3:
                continue
            la, lo, tt = lat[k], lon[k], t[k]
            native_dt = float(np.median(np.diff(t)))   # device's own rate
            n_pts += len(tt)
            stopped = stop_mask(la, lo, tt)
            dt = np.diff(tt)
            stopped_s += dt[stopped].sum()
            total_s += dt.sum()
            mlat, mlon, err, way, direction = match_run(la, lo)
            ok = ~np.isnan(mlat)
            n_matched += ok.sum()
            # continuous matched pieces
            breaks = np.nonzero(np.diff(ok.astype(int)) != 0)[0] + 1
            for a, b in zip(np.r_[0, breaks], np.r_[breaks, len(ok)]):
                if not ok[a] or b - a < 3:
                    continue
                pieces.append({"lat": la[a:b], "lon": lo[a:b], "t": tt[a:b],
                               "mlat": mlat[a:b], "mlon": mlon[a:b],
                               "err": err[a:b], "way": way[a:b],
                               "direction": direction[a:b],
                               "stopped": stopped[a:b - 1],
                               "native_dt": native_dt})
    base = {"trace_id": tr["trace_id"], "uploader": tr["uploader"],
            "identifiable": bool(tr["url"]), "source": tr["source"]}
    segs = {L: [] for L in SEGMENT_LENGTHS}
    points = []
    for pi, p in enumerate(pieces):
        for L in SEGMENT_LENGTHS:
            segs[L] += segments_of_piece(p, L, {**base, "piece": pi})
        points.append(pd.DataFrame({
            "trace_id": tr["trace_id"], "piece": pi, "t": p["t"],
            "lat": p["lat"], "lon": p["lon"], "mlat": p["mlat"],
            "mlon": p["mlon"], "match_err_m": p["err"],
            "way_index": p["way"], "direction": p["direction"],
            "native_dt": p["native_dt"],
            "stopped_after": np.r_[p["stopped"], False]}))
    for L in SEGMENT_LENGTHS:
        if segs[L]:
            segs[L] = attributes(pd.DataFrame(segs[L]))
    trail_min = 0.0
    if isinstance(segs[SEGMENT_LENGTHS[0]], pd.DataFrame):
        d = segs[SEGMENT_LENGTHS[0]]
        trail_min = d.loc[d.way_class == "trail", "moving_s"].sum() / 60
    summary = {**base, "points_used": n_pts,
               "matched_share": n_matched / n_pts if n_pts else np.nan,
               "stopped_share": stopped_s / total_s if total_s else np.nan,
               "trail_moving_min": trail_min,
               "segments_L50": len(segs[50.0]) if isinstance(
                   segs[50.0], pd.DataFrame) else 0}
    pts = pd.concat(points) if points else pd.DataFrame()
    return segs, summary, pts


def attributes(df):
    """Speed, way type, tags and dates (elevation: add_elevation)."""
    df["speed_kmh"] = df.length_m / df.moving_s.clip(lower=1e-6) * 3.6
    df["stopped_frac"] = (1 - df.moving_s / df.elapsed_s.clip(lower=1e-6)
                          ).clip(0, 1)
    wk = df.way_index.to_numpy()
    df["way_class"] = [W["cls"][k] if k >= 0 else None for k in wk]
    df["osm_way_id"] = [W["ways"][k]["id"] if k >= 0 else None
                        for k in wk]
    df["permission"] = [W["perm"][k] if k >= 0 else None for k in wk]
    for key in g.TAG_KEYS + ["name", "highway"]:
        df[f"tag_{key.replace(':', '_')}"] = [
            W["ways"][k].get("tags", {}).get(key) if k >= 0 else None
            for k in wk]
    local = pd.to_datetime(df.t_start, unit="s", utc=True) \
        .dt.tz_convert(W.get("tz", TZ))
    df["local_time"] = local.dt.strftime("%Y-%m-%d %H:%M")
    df["day_of_year"] = local.dt.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * df.day_of_year / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * df.day_of_year / 365.25)
    df["year"] = local.dt.year
    # dates before OSM took GPS uploads = a device clock bug (e.g. the GPS
    # week rollover puts 2007 in 1987); season columns can't be trusted
    df["date_suspect"] = df.year < DATE_OK_FROM
    return df


# ---------------------------------------------------------------- the test
def sign_test():
    """A path heading north on a DEM rising north must give slope > 0."""
    fl.sign_check()
    a = np.repeat((1000 + 0.10 * (199 - np.arange(200) + 0.5) / 200 * 0.01
                   * 111_195.0)[:, None], 160, axis=1)
    ext = (-71.0, 44.0, -70.99, 44.01)
    lat = np.linspace(44.002, 44.008, 40)
    lon = np.full(40, -70.995)
    t = np.arange(40) * 15.0
    p = {"lat": lat, "lon": lon, "t": t, "mlat": lat, "mlon": lon,
         "err": np.zeros(40), "way": np.zeros(40, int),
         "direction": np.ones(40), "stopped": np.zeros(39, bool)}

    def slopes(piece):
        df = pd.DataFrame(segments_of_piece(piece, 50.0, {}))
        df["speed_kmh"] = 3.0
        return add_elevation(df, [(a, ext)]).slope.to_numpy()

    rev = {k: (v[::-1] if isinstance(v, np.ndarray) and k != "t" else v)
           for k, v in p.items()}
    up, down = slopes(p), slopes(rev)
    assert np.all(up > 0.09) and np.all(down < -0.09), (up, down)
    print("  segment sign test passed: northbound +10%, southbound -10%")


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="T1: build the dataset")
    ap.add_argument("--sample", nargs="?", const="white_mountains",
                    choices=sorted(g.REGIONS), help="use a Gate 1 region's "
                    "4 sample boxes instead (default white_mountains)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--stop-rule", default=DEFAULT_STOP_RULE,
                    choices=sorted(STOP_RULES))
    ap.add_argument("--region", default="wm",
                    choices=sorted(regions.CANDIDATES))
    ap.add_argument("--no-lab", action="store_true",
                    help="API traces only (as in T1 v0)")
    args = ap.parse_args()
    sign_test()

    if args.sample:
        region, boxes = args.sample, g.REGIONS[args.sample]
        out = Path("data/t1_sample" if args.sample == "white_mountains"
                   else f"data/t1_sample_{args.sample}")
        lab_key = None
    else:
        region, boxes = regions.region_name(args.region), \
            regions.tiles(args.region)
        out, lab_key = regions.data_dir(args.region), args.region
    if args.no_lab:
        lab_key = None
    key = regions.key_of(region)
    W["tz"] = ZoneInfo(regions.tz(key)) if key else TZ   # (workers: init)
    if args.stop_rule != DEFAULT_STOP_RULE:
        out = out.with_name(out.name + "__" + args.stop_rule)
    bbox = (min(b[1] for b in boxes), min(b[2] for b in boxes),
            max(b[3] for b in boxes), max(b[4] for b in boxes))
    out.mkdir(parents=True, exist_ok=True)

    # elevation grids: 2 x 2 pieces per box, downloaded once and cached
    import t1_prefetch_dem
    t1_prefetch_dem.ensure_dems(region, boxes)

    t0 = time.time()
    traces, counts = collect_traces(region, boxes, bbox, lab_key)
    print(f"{len(traces)} traces to process ({counts}); "
          f"{time.time() - t0:.0f} s")

    results = []
    with Pool(args.workers, initializer=init_worker,
              initargs=(region, boxes, args.stop_rule)) as pool:
        for k, res in enumerate(pool.imap_unordered(process_trace, traces,
                                                    chunksize=2), 1):
            results.append(res)
            if k % 50 == 0 or k == len(traces):
                print(f"  {k}/{len(traces)} traces matched "
                      f"({time.time() - t0:.0f} s)")

    summaries = pd.DataFrame([r[1] for r in results])
    hikers = set(summaries.loc[summaries.trail_moving_min >=
                               MIN_MOVING_TRAIL_MIN, "trace_id"])
    starts = pd.DataFrame([{"trace_id": tr["trace_id"], **dict(zip(
        ("lat0", "lon0", "t0"), min(((p[0], p[1], p[2].timestamp())
                                     for p in g.all_points(tr)),
                                    key=lambda q: q[2])))}
        for tr in traces if any(tr["segments"])])
    outing = outing_ids(starts)
    summaries["outing_id"] = summaries.trace_id.map(outing)
    for L in SEGMENT_LENGTHS:
        parts = [r[0][L] for r in results
                 if isinstance(r[0][L], pd.DataFrame)]
        seg = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        seg = add_elevation(seg, dem_pieces(region, boxes))
        seg["hiking_trace"] = seg.trace_id.isin(hikers)
        seg["outing_id"] = seg.trace_id.map(outing)
        seg.to_parquet(out / f"segments_L{int(L)}.parquet", index=False)
        print(f"segments_L{int(L)}: {len(seg):,} rows "
              f"({(seg.way_class == 'trail').sum():,} on trails)")
    pts = pd.concat([r[2] for r in results if len(r[2])], ignore_index=True)
    pts.to_parquet(out / "points.parquet", index=False)
    summaries["hiking_trace"] = summaries.trace_id.isin(hikers)
    summaries.to_csv(out / "traces.csv", index=False)
    write_card(out, region, boxes, counts, summaries, args.stop_rule)
    print(f"done in {time.time() - t0:.0f} s -> {out}/")


def depth_capped(region):
    """Capped tiles and the oldest upload date their cached pages reach."""
    import t1_download
    key = regions.key_of(region)
    capped = t1_download.capped_tiles(key) if key else {}
    if not capped:
        return "none"
    parts = []
    for tile, page in capped.items():
        last = Path("cache", region, f"{tile}_p{page - 1:03d}.gpx")
        when = "?"
        if last.exists():
            stamps = re.findall(r"<time>(\d{4}-\d{2})", last.read_text(
                encoding="utf-8", errors="replace"))
            when = min(stamps) if stamps else "?"
        parts.append(f"{tile} (cut at page {page}; reaches uploads back to "
                     f"~{when})")
    return "; ".join(parts)


def osm_dates(region):
    """Date range of the cached Overpass downloads (the OSM snapshot)."""
    fs = list(Path("cache", region).glob("*_ways.json"))
    if not fs:
        return "unknown"
    days = sorted({datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)
                   .strftime("%Y-%m-%d") for f in fs})
    return days[0] if len(days) == 1 else f"{days[0]} to {days[-1]}"


def write_card(out, region, boxes, counts, summaries,
               stop_rule=DEFAULT_STOP_RULE):
    seg = pd.read_parquet(out / "segments_L50.parquet")
    hike = seg[seg.hiking_trace & (seg.way_class == "trail")]
    lines = [
        f"# Data card: {region} (T1, built "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
        "One row per (trace x fixed-length segment) traversal; see "
        "t1_build_dataset.py for every step.", "",
        "## Counts", "",
        f"- traces processed: {len(summaries)} "
        f"(named = identifiable or public "
        f"{int(summaries.identifiable.sum())}, anonymous "
        f"{int((~summaries.identifiable).sum())})",
        f"- by source: {summaries.source.value_counts().to_dict()}",
        *(["- **LAB-ONLY BUILD**: no OSM API pages yet, so anonymous "
           "(trackable) traces and uploads outside 2016-2022 are missing; a "
           "full download will rebuild this region"]
          if set(summaries.source) == {"lab original file"} else []),
        f"- hiking traces (>= {MIN_MOVING_TRAIL_MIN:.0f} moving min on "
        f"trails): {int(summaries.hiking_trace.sum())}",
        f"- independent outings among hiking traces (group hikes and "
        f"multi-phone recordings merged): "
        f"{summaries.loc[summaries.hiking_trace, 'outing_id'].nunique()}",
        f"- named uploaders among hiking traces: "
        f"{summaries.loc[summaries.hiking_trace & summaries.identifiable, 'uploader'].nunique()}",
        f"- 50 m trail segments from hiking traces: {len(hike):,}",
        f"- median share of each trace matched: "
        f"{100 * summaries.matched_share.median():.1f}%",
        f"- time removed as stops (all traces): "
        f"{100 * (summaries.stopped_share * 1).median():.1f}% median per "
        f"trace", "",
        "## Collection", "",
    ] + [f"- {k}: {v}" for k, v in counts.items()] + [
        "", "## Settings", "",
        f"- segment lengths: {SEGMENT_LENGTHS} m",
        f"- thinning for matching: >= {THIN_S} s",
        f"- split at gaps > {GAP_S:.0f} s or steps > "
        f"{g.FAST_SPEED_KMH:.0f} km/h",
        f"- stop rule: {stop_rule} {STOP_RULES[stop_rule]} (draft; see "
        "the stop-rule sensitivity check)",
        f"- map-matching: leuvenmapmatching DistanceMatcher {MATCH}",
        "- slope: (z_end - z_start) / length along travel, 5 m USGS 3DEP "
        "DEM; + = uphill (tested)",
        f"- suspect flag (kept, not dropped): speed > {SUSPECT_KMH:.0f} km/h, "
        f"abs(slope) > {SUSPECT_SLOPE}, or match error > 40 m",
        f"- suspect share of hiking trail segments: "
        f"{100 * hike.suspect.mean():.2f}%",
        f"- car-logger accounts dropped: {sorted(CAR_LOGGERS)}",
        f"- local time zone: {W.get('tz', TZ)}",
        f"- OSM ways (trails, tags) from Overpass, downloaded "
        f"{osm_dates(region)}",
        f"- OSM API depth limit (tiles whose oldest uploads are out of reach; "
        f"the API times out past ~4.5M points): {depth_capped(region)}",
        f"- traces with impossible dates (before {DATE_OK_FROM}, flagged "
        f"date_suspect): "
        f"{sorted(seg.loc[seg.date_suspect, 'trace_id'].unique())}"
        if "date_suspect" in seg else "- date_suspect: not computed",
        "- lab traces: original files of public + identifiable OSM traces "
        "uploaded 2016-2022 (lab crawl on ENGRFS), added unless the API "
        "gave the same trace id",
        "", "## Known limitations", "",
        "- The stop rule is a draft until the hand-labeled sheet is scored.",
        "- OSM trails are often traced from these same uploads, so match "
        "errors look smaller than true trail-position errors.",
        "- Uploaders are mappers and enthusiasts, not a random sample of "
        "hikers (plan sec. 8).",
    ]
    (out / "data_card.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
