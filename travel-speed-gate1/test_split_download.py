"""Offline test of t1_download's box splitting against a fake OSM API.

Fake API: points in the bbox, timestamped tracks first (newest upload
first), then untimed points by latitude, 50 points per page. A query times
out (503 "first byte timeout") when the box holds too many points or the
page is deep. Checks: splits recorded, leaves tile the region exactly, every
timestamped point downloaded exactly once, capped boxes reported, the
builder's collect_traces rejoins anonymous tracks cut at quarter edges
(including recordings that zigzag across an edge) without mixing two
recordings (concurrent ones, and two phones on one group hike).
Decision #135, 11 Nov 2026.

Run:  python test_split_download.py [work_dir]     (~2 min, no network)
"""
import json
import os
import random
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(tempfile.mkdtemp(prefix="split_test_"))
shutil.rmtree(WORK, ignore_errors=True)
(WORK / "cache").mkdir(parents=True)
(WORK / "results").mkdir()
(WORK / "logs").mkdir()
os.chdir(WORK)
sys.path.insert(0, str(REPO))

import requests
import gate1_audit as g
import regions
import t1_download as d

g.POINTS_PER_PAGE = 50
g.REQUEST_DELAY_S = 0
d.RETRY_WAIT_S = 0
random.seed(1)

KEY = "bayarea"
REGION = regions.region_name(KEY)
W, S, E, N = regions.CANDIDATES[KEY][1]

# ---- synthetic tracks: (upload_id, url or None, [(lat, lon, t)])
tracks = []
t0 = datetime(2015, 1, 1, tzinfo=timezone.utc)
uid = 0


def walk(lat, lon, n, step=0.0004):
    global uid
    uid += 1
    pts, t = [], t0 + timedelta(days=uid)
    for _ in range(n):
        pts.append((lat, lon, t))
        lat += random.uniform(-step, step)
        lon += random.uniform(0, step)          # drifts east: crosses edges
        t += timedelta(seconds=5)
    return pts


for k in range(160):                             # spread over the region
    lat, lon = random.uniform(S + 0.01, N - 0.05), random.uniform(W, E - 0.1)
    url = f"/user/u{k % 7}/traces/{1000 + k}" if k % 3 else None
    tracks.append((uid + 1, url, walk(lat, lon, random.randint(40, 300))))
# a "freeway" in tile r1_c1: many long anonymous tracks
for k in range(120):
    tracks.append((uid + 1, None, walk(37.60 + random.uniform(0, 0.01),
                                       -122.40, 400, step=0.0006)))
# a hopeless spot: dense even at the smallest box size (capped)
for k in range(60):
    tracks.append((uid + 1, None, walk(37.95, -122.20, 120, step=0.00003)))

# concurrent anonymous recordings (same start time, ~3 km apart)
uid += 1
same_day = uid
for k in range(12):
    lat, lon = 37.80 + 0.03 * (k % 4), -122.30 + 0.03 * (k // 4)
    pts, t = [], t0 + timedelta(days=same_day)
    for _ in range(250):
        pts.append((lat, lon, t))
        lat += random.uniform(-0.0004, 0.0004)
        lon += random.uniform(0, 0.0004)
        t += timedelta(seconds=5)
    tracks.append((same_day * 100 + k, None, pts))

# two phones on one group hike, walking along a box edge (lon -122.30 is
# a quarter edge in tile r1_c1) on opposite sides, 20 m apart; pair 1 has
# the same clock, pair 2 is 2 s apart
for pair, offset in ((1, 0), (2, 2)):
    uid += 1
    day = uid
    for side in (-1, 1):
        pts, t = [], t0 + timedelta(days=day, seconds=offset * (side > 0))
        lat, lon = 37.62 + 0.01 * pair, -122.30 + side * 0.0001
        for _ in range(200):
            pts.append((lat, lon, t))
            lat += 0.00008
            t += timedelta(seconds=5)
        tracks.append((day * 100 + 50 + side, None, pts))

untimed = [(random.uniform(S, N), random.uniform(W, E)) for _ in range(3000)]

calls = {"n": 0, "timeouts": 0, "glitch": 0}


class Resp:
    def __init__(self, code, text):
        self.status_code, self.text = code, text
        self.content = text.encode()
        self.headers = {}


def fake_get(url, params=None, headers=None, timeout=None):
    calls["n"] += 1
    w, s, e, n = map(float, params["bbox"].split(","))
    page = int(params["page"])
    inside = lambda la, lo: s <= la <= n and w <= lo <= e
    timed = []
    for up, u, pts in sorted(tracks, key=lambda x: -x[0]):  # newest first
        timed += [(up, u, p) for p in pts if inside(p[0], p[1])]
    unt = sorted((p for p in untimed if inside(*p)))
    total = len(timed) + len(unt)
    # the query time grows with the points in the box and the page depth
    if total > 6000 or (page > 40 and total > 3000):
        calls["timeouts"] += 1
        if calls["timeouts"] % 7 == 0:             # sometimes a client timeout
            raise requests.ReadTimeout("read timed out")
        return Resp(503, "<html>Error 503 first byte timeout</html>")
    # one transient error (not a timeout) for one box, once
    if calls["glitch"] == 0 and page == 1 and w < -122.5 and s > 37.7:
        calls["glitch"] += 1
        return Resp(502, "Bad gateway")
    P = g.POINTS_PER_PAGE
    rows = (timed + [(None, "untimed", (la, lo, None)) for la, lo in unt])
    rows = rows[page * P:(page + 1) * P]
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gpx version="1.0" creator="OpenStreetMap.org" '
           'xmlns="http://www.topografix.com/GPX/1/0">']
    prev, is_open = None, False
    for up, u, (la, lo, t) in rows:
        key = (up, u)
        if key != prev or not is_open:
            if is_open:
                out.append("</trkseg></trk>")
            is_open = True
            out.append("<trk>")
            if u and u != "untimed":
                out.append(f"<name>x.gpx</name><desc>d</desc><url>{u}</url>")
            out.append("<trkseg>")
            prev = key
        tt = f"<time>{t:%Y-%m-%dT%H:%M:%SZ}</time>" if t else ""
        out.append(f'<trkpt lat="{la:.7f}" lon="{lo:.7f}">{tt}</trkpt>')
    if rows:
        out.append("</trkseg></trk>")
    out.append("</gpx>")
    return Resp(200, "\n".join(out))


requests.get = fake_get


def no_overpass(*a, **k):
    raise AssertionError("Overpass called: quarters should use tile ways")


g._overpass = no_overpass
for t in regions.tiles(KEY):          # tile ways exist (as on the cluster)
    p = Path("cache") / REGION / f"{t[0]}_ways.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"elements": []}))

# ---- run the download (pages + summary), as main() does
d.step_pages(KEY)
d.step_trackpoints(KEY)

splits = d.load_splits(REGION)
leaves = d.leaf_boxes(REGION, regions.tiles(KEY))
print(f"\nsplits: {len(splits)}, leaves: {len(leaves)}, API calls "
      f"{calls['n']}, timeouts {calls['timeouts']}")
area = lambda b: (b[3] - b[1]) * (b[4] - b[2])
tiles_area = sum(area(t) for t in regions.tiles(KEY))
assert abs(sum(area(b) for b in leaves) - tiles_area) < 1e-9, "leaves != tiles"
assert min(min(b[3] - b[1], b[4] - b[2]) for b in leaves) >= d.SPLIT_MIN_DEG

# every timestamped point exactly once across the leaves' cached pages
# (except in capped boxes, which miss their oldest uploads by design)
capped = d.capped_tiles(KEY)
print("capped:", capped)
print("incomplete:", d.incomplete_tiles(KEY))
assert not d.incomplete_tiles(KEY)
assert capped, "the hopeless spot should be capped"
got = {}
for b in leaves:
    texts, info, _ = g.download_box("cache", REGION, b, offline=True,
                                    max_pages=d.MAX_PAGES)
    for tr in g.timed_traces(texts, info):
        for seg in tr["segments"]:
            for la, lo, t, *_ in seg:
                k = (round(la, 7), round(lo, 7), t)
                got[k] = got.get(k, 0) + 1


def in_box(b, la, lo):
    return b[1] <= lo <= b[3] and b[2] <= la <= b[4]


capped_boxes = [b for b in leaves if b[0] in capped]
want = {(round(la, 7), round(lo, 7), t) for _, _, pts in tracks
        for la, lo, t in pts
        if any(in_box(b, la, lo) for b in leaves)
        and not any(in_box(b, la, lo) for b in capped_boxes)}
missing = want - set(got)
dup = sum(1 for k in want if got.get(k, 0) > 1)
print(f"timestamped points wanted {len(want)}, got {len(set(got) & want)}, "
      f"missing {len(missing)}, on 2 leaves (shared edge) {dup}")
assert not missing

# the builder: anonymous tracks cut at quarter edges are rejoined
import t1_build_dataset as b
b.GPX_DIR = Path("cache/t1_gpx")
boxes = regions.tiles(KEY)
bbox = (W, S, E, N)
traces, counts = b.collect_traces(REGION, boxes, bbox, lab_key=None)
print("collect_traces counts:", counts)
owner = {}
for i, (_, u, pts) in enumerate(tracks):
    if u is None:
        for la, lo, t in pts:
            owner[(round(la, 7), round(lo, 7), t)] = i
built = {}                     # true track -> built anonymous traces
mixed = swapped = 0
for tr in traces:
    if tr["url"]:
        continue
    seq = [owner.get((round(p[0], 7), round(p[1], 7), p[2])) for p in
           sorted((p for s in tr["segments"] for p in s), key=lambda p: p[2])]
    switches = sum(a != b for a, b in zip(seq, seq[1:]))
    ids = set(seq)
    mixed += switches > 2          # interleaves two recordings: garbage
    swapped += 0 < switches <= 2   # two recordings swapped at an edge
    for i in ids:
        built.setdefault(i, []).append(tr["trace_id"])
clean = [i for i, (_, u, pts) in enumerate(tracks) if u is None and not any(
    in_box(b, la, lo) for b in capped_boxes for la, lo, t in pts)
    and any(in_box(b, la, lo) for b in leaves for la, lo, t in pts)]
frag = [i for i in clean if len(built.get(i, [])) != 1]
print(f"anonymous recordings away from capped boxes: {len(clean)}; "
      f"rebuilt as exactly one trace: {len(clean) - len(frag)}; "
      f"traces interleaving two recordings: {mixed}; swapped once at an "
      f"edge: {swapped}")
for i in frag[:3]:                  # why: the pieces of this recording
    print(f"track {i}: built as {built.get(i)}")
    for b in leaves:
        texts, info, _ = g.download_box("cache", REGION, b, offline=True,
                                        max_pages=d.MAX_PAGES)
        for tr in g.timed_traces(texts, info):
            pts = [p for sg in tr["segments"] for p in sg]
            mine = [p for p in pts if owner.get((round(p[0], 7),
                                                 round(p[1], 7), p[2])) == i]
            if mine:
                print(f"   {b[0]}: {len(mine)} pts {mine[0][2]:%H:%M:%S}-"
                      f"{mine[-1][2]:%H:%M:%S} segs {len(tr['segments'])}"
                      f" url {tr['url']}")
assert mixed == 0 and not frag, (mixed, frag[:5])
summ = json.loads((Path("results") / REGION / "summary.json").read_text())
print("summary boxes:", len(summ["boxes"]), "| statuses:",
      sorted({str(x['status'])[:40] for x in summ["boxes"]}))
print("data-card line:", b.api_boxes(REGION, boxes))
print("depth_capped:", b.depth_capped(REGION)[:300])
print("ALL CHECKS PASSED")
