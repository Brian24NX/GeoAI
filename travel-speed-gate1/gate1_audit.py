#!/usr/bin/env python3
"""
Gate 1 audit: are the OpenStreetMap GPS traces in a region usable?

Version 2 (2 Oct 2026). Version 1 (archive/gate1_audit_v1.py) was written and
tested on fake data only. Running it against the real OSM API showed problems
that would have made the headline number wrong -- see "WHAT CHANGED" below.

PLAIN-ENGLISH SUMMARY
To measure walking speed you need GPS points that have timestamps AND are in
time order. OpenStreetMap only gives you that for traces uploaded as
"identifiable" or "trackable". Points from "public" and "private" traces come
back with no timestamps, sorted by latitude (for privacy), so no speed can be
computed from them.

This script answers the Gate 1 question (semester plan, section 6):
  1. Download the GPS points in a few small boxes per region. Every page is
     saved to disk the first time and never downloaded again.
  2. Count how many points are usable (timestamped) and how many are not.
  3. Download the paths and roads in each box from OSM (Overpass API) and
     match every GPS point to the nearest one. That separates trail traffic
     from cars, ski lifts and the Cog Railway, and splits trail traffic by
     which modes the trail allows (plan section 6, last checkbox).
  4. Compute speed between points at least 10 s apart.
  5. Remove stops two ways -- the crude 0.5 km/h rule from the plan, and a
     draft "minimum duration" rule (plan section 8) -- so they can be compared.
  6. Print a summary and save tables and plots in results/<region>/.

WHAT CHANGED IN VERSION 2 (all found on real data)
  * Paging. The API sends every timestamped point first and every untimed
    point after them. Version 1 read at most 10 pages, so in a busy box it saw
    only usable points and would have reported ~100% usable. (The Mt
    Washington box has 22 full pages of usable points before the first
    unusable one.) Version 2 reads up to where the unusable points start, then
    jumps ahead (+1, +2, +4, ... pages) to find the last page, so it can count
    the unusable points without downloading all of them.
  * Recording segments. One upload can hold several recordings that are not
    stored in date order (one hiker's whole winter in one file). Version 1 saw
    time "going backwards" and threw the trace away as shuffled. Version 2
    checks timestamps one segment at a time and never computes a speed across
    a segment break.
  * Repeated timestamps. Some car loggers record 10 points per second but
    store whole seconds only. Version 1 skipped the zero-time pairs and read a
    car at walking pace. Version 2 keeps the first point of each second.
  * Gaps. A trace that leaves the box and comes back jumps forward in time.
    Steps longer than 5 minutes now count as gaps, not as stops.
  * Speed is measured over steps of at least 10 s, which removes most of the
    GPS-wobble inflation found in the fake-data test (README, Lesson 2).

HOW TO RUN
  python gate1_audit.py --region white_mountains
  python gate1_audit.py --region all                  # all three candidates
  python gate1_audit.py --region cascades --offline   # re-run from saved files

Needs: requests, numpy, pandas, matplotlib, scipy
"""

import argparse
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # save plots to files, no window needed
import matplotlib.pyplot as plt
import matplotlib.ticker
from scipy.spatial import cKDTree

# ------------------------------------------------------------------ settings
# Every number here is a decision. summary.json records them for each run.
API_URL = "https://api.openstreetmap.org/api/0.6/trackpoints"
OVERPASS_URLS = [                  # tried in order until one answers
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
POINTS_PER_PAGE = 5000     # OSM returns at most 5,000 points per page
MAX_BOX_DEG = 0.25         # OSM limit: box width and height each <= 0.25 deg
REQUEST_DELAY_S = 1.0      # pause between downloads; OSM is volunteer-run
USER_AGENT = "WashU-MVRL-travel-speed-gate1/0.2 (contact: zhou.n@wustl.edu)"
OVERPASS_AGENT = "WashU-MVRL-travel-speed-gate1/0.2 (research)"

STOP_SPEED_KMH = 0.5       # crude stop rule from plan section 6
FAST_SPEED_KMH = 60.0      # faster than this = vehicle or GPS glitch
MIN_STEP_S = 10.0          # measure speed over steps of at least 10 s
MAX_GAP_S = 300.0          # a step longer than 5 min is a gap, not a stop
WINDOW_STOP_S = 60.0       # draft stop rule (plan section 8): any stretch of
WINDOW_STOP_M = 10.0       #   60+ s that ends < 10 m from where it started
MATCH_RADIUS_M = 25.0      # a GPS point is "on" a way if within 25 m of it
MIN_TRAIL_MIN = 5.0        # a "trail trace" has 5+ moving minutes on trails
CONTINUE_S = 600.0         # join trackable pieces split by a page break if
                           #   the second starts within 10 min of the first

# Rough speed bands for a FIRST LOOK only. This is not mode detection --
# real mode inference is plan section 8.
BANDS = [
    ("walking-like", 1.5, 6.0),
    ("in-between", 6.0, 10.0),
    ("cycling-like", 10.0, 30.0),
]

# What kind of way a GPS point is on.
TRAIL_HIGHWAYS = {"path", "footway", "bridleway", "steps", "cycleway",
                  "via_ferrata"}
ROAD_HIGHWAYS = {"motorway", "trunk", "primary", "secondary", "tertiary",
                 "unclassified", "residential", "service", "living_street",
                 "road", "busway", "raceway", "motorway_link", "trunk_link",
                 "primary_link", "secondary_link", "tertiary_link"}
RAILWAYS = {"rail", "narrow_gauge", "light_rail", "funicular", "monorail",
            "preserved", "tram", "subway", "miniature"}
CLASSES = ["trail", "track", "road", "lift", "rail", "piste", "other", "none"]
TRAIL, TRACK, ROAD, NONE = (CLASSES.index(c)
                            for c in ("trail", "track", "road", "none"))

# Which modes a trail allows (plan section 6: "break the usable count down by
# permitted mode").
PERMISSIONS = ["foot-only", "bicycle-permitted", "horse-permitted",
               "bike+horse", "unclear"]
YES = {"yes", "designated", "permissive", "official", "destination"}
NO = {"no", "private", "dismount", "use_sidepath", "discouraged"}

# Trail attributes the Tags arm would use (plan section 4).
TAG_KEYS = ["surface", "sac_scale", "width", "trail_visibility", "smoothness",
            "mtb:scale", "incline"]

# Sample boxes over popular trail areas: (name, west, south, east, north).
# Keep each side of every box at or under 0.25 degrees.
REGIONS = {
    "white_mountains": [
        ("presidentials_mt_washington", -71.35, 44.22, -71.25, 44.32),
        ("franconia_ridge", -71.70, 44.10, -71.60, 44.20),
        ("crawford_notch", -71.46, 44.15, -71.36, 44.25),
        ("lincoln_woods", -71.62, 44.02, -71.52, 44.12),
    ],
    "cascades": [
        ("rainier_paradise", -121.80, 46.74, -121.70, 46.84),
        ("snoqualmie_pass", -121.46, 47.38, -121.36, 47.48),
        ("mount_si", -121.78, 47.44, -121.68, 47.54),
        ("cascade_pass", -121.13, 48.43, -121.03, 48.53),
    ],
    "front_range": [
        ("boulder_flatirons", -105.33, 39.95, -105.23, 40.05),
        ("rmnp_bear_lake", -105.70, 40.26, -105.60, 40.36),
        ("golden_foothills", -105.30, 39.70, -105.20, 39.80),
        ("brainard_lake", -105.62, 40.03, -105.52, 40.13),
    ],
}


# ----------------------------------------------------------- download + cache
class DownloadError(Exception):
    pass


def check_box(box):
    name, west, south, east, north = box
    if not (west < east and south < north):
        raise ValueError(f"Box {name}: west<east and south<north required")
    if east - west > MAX_BOX_DEG or north - south > MAX_BOX_DEG:
        raise ValueError(f"Box {name}: each side must be <= {MAX_BOX_DEG} deg")


def get_page(cache_dir, region, box, page, offline):
    """Return (gpx_text, source). Reads from disk if already downloaded."""
    name, west, south, east, north = box
    path = Path(cache_dir) / region / f"{name}_p{page:03d}.gpx"
    if path.exists():
        return path.read_text(encoding="utf-8"), "cache"
    if offline:
        return None, "missing"

    import requests  # only needed when actually downloading

    params = {"bbox": f"{west},{south},{east},{north}", "page": page}
    try:
        resp = requests.get(API_URL, params=params,
                            headers={"User-Agent": USER_AGENT}, timeout=120)
    except requests.RequestException as err:
        print(f"    ! network problem on {name} page {page}: {err}")
        return None, "error"
    finally:
        time.sleep(REQUEST_DELAY_S)

    if resp.status_code != 200:
        print(f"    ! HTTP {resp.status_code} on {name} page {page}: "
              f"{resp.text[:150]!r}")
        return None, "error"

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(resp.text, encoding="utf-8")
    os.replace(tmp, path)  # never leave a half-written file in the cache
    return resp.text, "downloaded"


def page_counts(text):
    """(points, timestamped points) on one page. A quick count, no parsing."""
    return text.count("<trkpt"), text.count("<time>")


def download_box(cache_dir, region, box, offline=False, max_pages=150,
                 untimed_sample=6):
    """Download one box.

    Returns (texts of the pages with usable points, info, texts of a sample
    of pages with untimed points).

    The API sends every timestamped point first (newest upload first), then
    every untimed point (sorted by latitude). So we:
      1. read pages 0, 1, 2, ... up to the first page holding untimed points
         -- those pages hold all the usable data;
      2. find the last page by jumping ahead (+1, +2, +4, ...) and narrowing
         down, so untimed points are counted from about a dozen pages instead
         of downloading every one;
      3. if step 1 stopped at max_pages first, narrow down where the untimed
         points start, so the usable count is still exact (the speed numbers
         then use only the first max_pages pages -- the newest uploads, which
         can be mostly car loggers);
      4. read a few evenly spaced untimed pages, so we can estimate how many
         of the UNusable points are on trails too.
    """
    counts = {}  # page number -> (points, timestamped points)

    def fetch(page):
        text, source = get_page(cache_dir, region, box, page, offline)
        if text is None:
            raise DownloadError(f"page {page}: {source}")
        counts[page] = page_counts(text)
        return text

    def size(page):
        if page not in counts:
            fetch(page)
        return counts[page][0]

    def untimed_started(page):
        n = size(page)
        return counts[page][1] < n or n == 0

    texts, untimed_texts = [], []
    info = {"box": box[0], "status": "ok", "usable_part_complete": False,
            "pages_read": 0, "usable_pages_used": 0, "boundary_page": None,
            "last_page": None, "points_total": None, "points_timed": None,
            "points_untimed": None, "order_check": "ok"}
    boundary = end = None
    try:
        # 1. the timestamped part
        for page in range(max_pages):
            texts.append(fetch(page))
            n, timed = counts[page]
            if timed < n:
                boundary = page
            if n < POINTS_PER_PAGE:
                end = page
            if boundary is not None or end is not None:
                break
        info["usable_part_complete"] = boundary is not None or end is not None

        # 2. find the last page: jump ahead, then narrow down
        if end is None:
            lo, step = len(texts) - 1, 1          # page lo is known to be full
            while size(lo + step) >= POINTS_PER_PAGE:
                lo, step = lo + step, 2 * step
            hi = lo + step                        # page hi is known to be short
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if size(mid) >= POINTS_PER_PAGE:
                    lo = mid
                else:
                    hi = mid
            end = hi

        # 3. stopped early? then narrow down where the untimed points start
        if not info["usable_part_complete"] and untimed_started(end):
            lo, hi = len(texts) - 1, end
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if untimed_started(mid):
                    hi = mid
                else:
                    lo = mid
            boundary = hi

        total = POINTS_PER_PAGE * end + counts[end][0]
        timed_total = total if boundary is None else \
            POINTS_PER_PAGE * boundary + counts[boundary][1]
        info.update(points_total=total, points_timed=timed_total,
                    points_untimed=total - timed_total,
                    boundary_page=boundary, last_page=end)
        if not info["usable_part_complete"]:
            info["status"] = (f"usable part cut at {max_pages} pages "
                              "(speeds use a sample; counts are exact)")

        # 4. a spread-out sample of untimed pages (they're sorted by latitude)
        if boundary is not None and total > timed_total:
            last_full = end if counts[end][0] else end - 1
            for p in np.unique(np.linspace(boundary, last_full,
                                           untimed_sample).round().astype(int)):
                size(int(p))
            for p in sorted(counts):
                if p >= boundary and counts[p][1] < counts[p][0]:
                    text, _ = get_page(cache_dir, region, box, p, True)
                    untimed_texts.append(text)

        # sanity check on the API order: nothing timestamped after the start
        # of the untimed points
        late = sorted(p for p in counts
                      if boundary is not None and p > boundary
                      and counts[p][1] > 0)
        if late:
            info["order_check"] = ("timestamped points after the first "
                                   f"untimed page, on pages {late}")
    except DownloadError as err:
        info["status"] = f"stopped: {err}"
    info["pages_read"] = len(counts)
    info["usable_pages_used"] = len(texts)
    return texts, info, untimed_texts


# -------------------------------------------------------------------- parsing
_FRACTION = re.compile(r"\.(\d+)")


def parse_time(text):
    """Parse a GPX time like 2019-06-26T14:27:58Z. Returns None if missing."""
    if not text:
        return None
    s = text.strip().replace("Z", "+00:00")
    s = _FRACTION.sub(lambda m: "." + (m.group(1) + "000000")[:6], s)
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _local(tag):
    return tag.rsplit("}", 1)[-1]  # drop the XML namespace prefix


def parse_gpx(xml_text):
    """Turn one OSM trackpoints page into a list of traces.

    Each trace: {"name", "desc", "url", "segments": [[(lat, lon, time|None)]]}
    One <trkseg> is one continuous recording.
    """
    root = ET.fromstring(xml_text)
    traces = []
    for trk in root:
        if _local(trk.tag) != "trk":
            continue
        trace = {"name": None, "desc": None, "url": None, "segments": []}
        for child in trk:
            tag = _local(child.tag)
            if tag in ("name", "desc", "url"):
                trace[tag] = (child.text or "").strip() or None
            elif tag == "trkseg":
                seg = []
                for pt in child:
                    if _local(pt.tag) != "trkpt":
                        continue
                    when = None
                    for sub in pt:
                        if _local(sub.tag) == "time":
                            when = parse_time(sub.text)
                    seg.append((float(pt.get("lat")), float(pt.get("lon")),
                                when))
                if seg:
                    trace["segments"].append(seg)
        traces.append(trace)
    return traces


def all_points(trace):
    return [p for seg in trace["segments"] for p in seg]


USABLE = ("identifiable", "trackable")


def classify(trace):
    """identifiable / trackable = usable (timestamped).

    untimed = points from public or private traces: no timestamps, sorted by
    position, so no speed can be computed. The API puts all of them in one
    unnamed track per page, so they are counted as points, not traces.
    """
    pts = all_points(trace)
    timed = sum(p[2] is not None for p in pts)
    if timed == 0:
        return "untimed" if pts else "empty"
    if timed < len(pts):
        return "partly_timed"       # never seen so far; flagged if it happens
    if len(pts) < 2:
        return "too_short"
    return "identifiable" if (trace["url"] or trace["name"]) else "trackable"


def merge_pages(pages):
    """Join traces that were split across pages.

    pages: one list of timestamped traces per page, in API order.
    Identifiable traces are joined by their URL. Trackable traces have no
    URL, but the API sends points in upload order, so a split trace carries
    on at the top of the next page: the first trace on a page is joined to
    the last one on the page before if it starts within CONTINUE_S after it.
    """
    merged, by_url, prev = [], {}, None
    for traces in pages:
        target = None
        for i, trace in enumerate(traces):
            url = trace["url"]
            if url and url in by_url:
                target = by_url[url]
                target["segments"].extend(trace["segments"])
            elif (i == 0 and prev is not None and not url and not prev["url"]
                  and _continues(prev, trace)):
                target = prev
                target["segments"].extend(trace["segments"])
            else:
                target = trace
                merged.append(trace)
                if url:
                    by_url[url] = trace
        if target is not None:
            prev = target
    return merged


def _continues(a, b):
    end, start = a["segments"][-1][-1][2], b["segments"][0][0][2]
    if end is None or start is None:
        return False
    return 0 <= (start - end).total_seconds() <= CONTINUE_S


def user_of(url):
    """OSM user name from a trace URL like /user/NAME/traces/123."""
    m = re.search(r"/user/([^/]+)/traces/", url or "")
    return unquote(m.group(1)) if m else None


def fingerprint(trace):
    """Same points at the same times = the same recording uploaded twice."""
    pts = sorted((p[2].timestamp(), round(p[0], 6), round(p[1], 6))
                 for p in all_points(trace))
    return hash(tuple(pts))


def group_outings(table, minutes=15, meters=1000):
    """Label traces that start together (same box, within 15 min and 1 km).

    Two phones in one hiking group give two traces of one outing -- they are
    not independent samples. Returns an outing id per row (NaN if not usable).
    """
    ids = pd.Series(np.nan, index=table.index)
    if "start_s" not in table:
        return ids
    rows = table.dropna(subset=["start_s"]).sort_values(["box", "start_s"])
    next_id, open_groups = 0, []           # (box, start_s, lat, lon, id)
    for idx, r in rows.iterrows():
        match = None
        for g in open_groups:
            if (g[0] == r["box"] and r["start_s"] - g[1] <= 60 * minutes
                    and haversine_m(g[2], g[3], r["start_lat"],
                                    r["start_lon"]) <= meters):
                match = g[4]
                break
        if match is None:
            match, next_id = next_id, next_id + 1
            open_groups.append((r["box"], r["start_s"], r["start_lat"],
                                r["start_lon"], match))
        ids[idx] = match
    return ids


# --------------------------------------------------------------------- speeds
def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between points on the Earth's surface."""
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def clean_segment(seg):
    """One recording -> (lat, lon, t in seconds, was_unsorted).

    Sorts by time if needed and keeps only the first point of each timestamp
    (10-per-second loggers that store whole seconds repeat timestamps).
    """
    lat = np.array([p[0] for p in seg])
    lon = np.array([p[1] for p in seg])
    t = np.array([p[2].timestamp() for p in seg])
    unsorted = bool(np.any(np.diff(t) < 0))
    if unsorted:
        order = np.argsort(t, kind="stable")
        lat, lon, t = lat[order], lon[order], t[order]
    keep = np.r_[True, np.diff(t) > 0]
    return lat[keep], lon[keep], t[keep], unsorted


def thin(t, min_step_s=MIN_STEP_S):
    """Indices of the points to keep so kept points are >= min_step_s apart."""
    if min_step_s <= 0 or len(t) == 0:
        return np.arange(len(t))
    keep, last = [0], t[0]
    for i in range(1, len(t)):
        if t[i] - last >= min_step_s:
            keep.append(i)
            last = t[i]
    return np.array(keep)


def steps(lat, lon, t):
    """Speed (km/h), duration (s), distance (m) for each consecutive pair.

    Worked example: two points 25 m apart, 30 s apart
      -> 25 / 30 = 0.833 m/s -> x 3.6 = 3.0 km/h
    """
    dist = haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    dt = np.diff(t)
    return dist / dt * 3.6, dt, dist


def segment_speeds(points, min_step_s=0.0):
    """Speeds for ONE recording given as [(lat, lon, time)], after cleaning
    and (if min_step_s > 0) thinning. Returns speed, duration, distance."""
    lat, lon, t, _ = clean_segment(points)
    k = thin(t, min_step_s)
    return steps(lat[k], lon[k], t[k])


def window_stops(lat, lon, t, dt):
    """Draft "speed + minimum duration" stop rule (plan section 8).

    A step counts as stopped if it lies inside a stretch of at least
    WINDOW_STOP_S seconds (with no gap) that ends less than WINDOW_STOP_M
    meters from where it started. GPS wobble jiggles the points but does not
    carry a standing hiker 10 m away, so this catches stops the 0.5 km/h rule
    misses.
    """
    n = len(t)
    if n < 2:
        return np.zeros(0, dtype=bool)
    j = np.searchsorted(t, t + WINDOW_STOP_S, side="left")
    i_idx = np.nonzero(j < n)[0]
    j_idx = j[i_idx]
    d = haversine_m(lat[i_idx], lon[i_idx], lat[j_idx], lon[j_idx])
    gaps = np.r_[0, np.cumsum(dt > MAX_GAP_S)]
    ok = (d < WINDOW_STOP_M) & (gaps[j_idx] == gaps[i_idx])
    mark = np.zeros(n, dtype=int)          # steps i..j-1 are inside a stop
    np.add.at(mark, i_idx[ok], 1)
    np.add.at(mark, j_idx[ok], -1)
    return np.cumsum(mark)[:-1] > 0


def wmedian(values, weights):
    """Weighted median (here: the median speed over time, not over points)."""
    values, weights = np.asarray(values, float), np.asarray(weights, float)
    if values.size == 0 or weights.sum() <= 0:
        return np.nan
    order = np.argsort(values)
    cum = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cum, 0.5 * cum[-1])])


def band_of(speed):
    if speed is None or np.isnan(speed):
        return "unknown"
    for name, lo, hi in BANDS:
        if lo <= speed < hi:
            return name
    return "other"


# ----------------------------------------------------------- trails and roads
def get_ways(cache_dir, region, box, offline=False, say=print):
    """OSM ways (paths, roads, lifts, railways, ski runs) around a box.

    Downloaded once from the Overpass API and cached as JSON. Returns the
    list of ways, or None if they could not be downloaded. Busy servers
    often refuse a whole city-sized box but still answer small questions,
    so if the box fails it is fetched again as 4 x 4 smaller pieces.
    """
    name, west, south, east, north = box
    path = Path(cache_dir) / region / f"{name}_ways.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["elements"]
    if offline:
        return None

    pad = 0.002  # about 200 m, so points near the edge still find their way
    w, s, e, n = west - pad, south - pad, east + pad, north + pad
    elements = _overpass((w, s, e, n), say, rounds=2)
    if elements is None:
        say("    ... trying the box again as 16 smaller pieces")
        elements, seen = [], set()
        xs, ys = np.linspace(w, e, 5), np.linspace(s, n, 5)
        for i in range(4):
            for j in range(4):
                part = _overpass((xs[i], ys[j], xs[i + 1], ys[j + 1]), say,
                                 rounds=3)
                if part is None:
                    say("    ! no trail data for this box; re-run later "
                        "to fill it in")
                    return None
                for el in part:            # a way can cross several pieces
                    if el["id"] not in seen:
                        seen.add(el["id"])
                        elements.append(el)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"elements": elements}), encoding="utf-8")
    os.replace(tmp, path)
    return elements


def _overpass(bbox, say, rounds=3):
    """Ask the Overpass servers for the ways in bbox=(w, s, e, n).

    Tries each server in OVERPASS_URLS, with patient retries. Returns the
    list of elements, or None if every server stayed busy.
    """
    import requests

    w, s, e, n = bbox
    bb = f"{s:.5f},{w:.5f},{n:.5f},{e:.5f}"
    query = (f'[out:json][timeout:180];(way["highway"]({bb});'
             f'way["aerialway"]({bb});way["railway"]({bb});'
             f'way["piste:type"]({bb}););out tags geom;')
    for round_ in range(rounds):     # public servers get busy; be patient
        if round_:
            say(f"    ... all Overpass servers busy; waiting 2 min "
                f"(round {round_ + 1} of {rounds})")
            time.sleep(120)
        for url in OVERPASS_URLS:
            host = url.split("/")[2]
            for attempt in range(2):
                try:
                    resp = requests.post(url, data={"data": query},
                                         timeout=150,
                                         headers={"User-Agent": OVERPASS_AGENT})
                except requests.RequestException as err:
                    say(f"    ! Overpass {host}: {err.__class__.__name__}")
                    break                           # try the next server
                finally:
                    time.sleep(REQUEST_DELAY_S)
                ok = (resp.status_code == 200
                      and resp.text.lstrip().startswith("{"))
                if ok:
                    data = resp.json()
                    if "error" not in str(data.get("remark", "")).lower():
                        return data["elements"]
                say(f"    ! Overpass {host}: HTTP {resp.status_code}"
                    + (" (incomplete answer)" if ok else ""))
                if resp.status_code in (429, 504) or ok:
                    time.sleep(20)                  # busy: wait, retry once
                else:
                    break
    return None


ROADSIDE = {"sidewalk", "crossing", "traffic_island", "access_aisle"}


def way_class(tags):
    hw = tags.get("highway")
    if hw in TRAIL_HIGHWAYS:
        if tags.get("footway") in ROADSIDE or tags.get("cycleway") in ROADSIDE:
            return "other"       # sidewalks and crosswalks: beside roads, so
                                 # car points snap to them (Boulder has ~3,500)
        return "trail"
    if hw == "track":
        return "track"
    if hw in ROAD_HIGHWAYS:
        return "road"
    if hw:
        return "other"           # plazas, platforms, proposed roads, ...
    if "aerialway" in tags:
        return "lift"
    if tags.get("railway") in RAILWAYS:
        return "rail"
    if "piste:type" in tags:
        return "piste"
    return "other"               # abandoned railways, ...


def _access(value):
    v = (value or "").split(";")[0].strip().lower()
    return True if v in YES else False if v in NO else None


def permission(tags):
    """Which modes a trail way allows (index into PERMISSIONS).

    Explicit bicycle= / horse= tags win. Otherwise cycleway or mtb:scale
    means bikes, bridleway means horses, and footway / steps mean neither.
    A plain path with no bicycle tag is "unclear": US defaults are disputed.
    """
    hw = tags.get("highway")
    bike, horse = _access(tags.get("bicycle")), _access(tags.get("horse"))
    if bike is None:
        if hw == "cycleway" or "mtb:scale" in tags:
            bike = True
        elif hw in ("footway", "steps"):
            bike = False
    if horse is None:
        if hw == "bridleway":
            horse = True
        elif hw in ("footway", "steps", "cycleway"):
            horse = False
    if bike and horse:
        return 3
    if bike:
        return 1
    if horse:
        return 2
    if bike is False:
        return 0
    return 4


class WayMatcher:
    """Finds the nearest OSM way (within MATCH_RADIUS_M) to GPS points.

    Each way is cut into points every <= 5 m and put in a KD-tree; a GPS
    point takes the way of the nearest such point. A crude stand-in for real
    map-matching (plan section 8) -- good enough for a Gate 1 head count.
    Way index -1 means "no way nearby"; the lookup arrays below have an extra
    last entry so that index -1 reads as class "none".
    """
    SPACING_M = 5.0

    def __init__(self, ways, box):
        _, west, south, east, north = box
        self.kx = 111_320.0 * np.cos(np.radians((south + north) / 2))
        self.ky = 111_132.0                    # meters per degree of latitude
        cls, perm, bits, length = [], [], [], []
        xs, ys, owner = [], [], []
        for k, way in enumerate(ways):
            tags = way.get("tags", {})
            c = way_class(tags)
            cls.append(CLASSES.index(c))
            perm.append(permission(tags) if c == "trail" else -1)
            bits.append(sum(1 << i for i, key in enumerate(TAG_KEYS)
                            if key in tags))
            geom = [g for g in way.get("geometry") or [] if g]
            if not geom:
                length.append(0.0)
                continue
            lon = np.array([g["lon"] for g in geom])
            lat = np.array([g["lat"] for g in geom])
            x, y = lon * self.kx, lat * self.ky
            dx, dy = np.diff(x), np.diff(y)
            seg = np.hypot(dx, dy)
            n = np.maximum(1, np.ceil(seg / self.SPACING_M).astype(int))
            idx = np.repeat(np.arange(len(seg)), n)
            frac = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)) \
                / np.repeat(n, n)
            xs.append(np.r_[x[idx] + frac * dx[idx], x[-1]])
            ys.append(np.r_[y[idx] + frac * dy[idx], y[-1]])
            owner.append(np.full(len(xs[-1]), k))
            mid_lon, mid_lat = (lon[:-1] + lon[1:]) / 2, (lat[:-1] + lat[1:]) / 2
            inside = ((mid_lon >= west) & (mid_lon <= east)
                      & (mid_lat >= south) & (mid_lat <= north))
            length.append(float(seg[inside].sum()))
        self.cls = np.array(cls + [NONE])
        self.perm = np.array(perm + [-1])
        self.bits = np.array(bits + [0])
        self.length_m = np.array(length + [0.0])
        self.n_ways = len(ways)
        self.tree = cKDTree(np.c_[np.concatenate(xs), np.concatenate(ys)]) \
            if xs else None
        self.owner = np.concatenate(owner) if owner else np.zeros(0, int)

    def snap(self, lat, lon):
        """Nearest way point: (way index, lat, lon) for each GPS point.

        Way index -1 = no way within MATCH_RADIUS_M (the point is returned
        unchanged).
        """
        way = np.full(len(lat), -1)
        slat, slon = np.array(lat, float), np.array(lon, float)
        if self.tree is None or len(lat) == 0:
            return way, slat, slon
        d, i = self.tree.query(np.c_[lon * self.kx, lat * self.ky],
                               distance_upper_bound=MATCH_RADIUS_M)
        ok = np.isfinite(d)
        way[ok] = self.owner[i[ok]]
        xy = self.tree.data[i[ok]]
        slon[ok], slat[ok] = xy[:, 0] / self.kx, xy[:, 1] / self.ky
        return way, slat, slon

    def match(self, lat, lon):
        """Way index for each point (-1 = no way within MATCH_RADIUS_M)."""
        return self.snap(lat, lon)[0]

    def network(self):
        """Trail network inside the box: length, tags present, permissions."""
        trail = self.cls[:-1] == TRAIL
        km = self.length_m[:-1][trail] / 1000
        bits, perm = self.bits[:-1][trail], self.perm[:-1][trail]
        return {
            "trail_km": float(km.sum()),
            "trail_km_with_tag": {key: float(km[(bits >> i) & 1 == 1].sum())
                                  for i, key in enumerate(TAG_KEYS)},
            "trail_km_by_permission": {name: float(km[perm == i].sum())
                                       for i, name in enumerate(PERMISSIONS)},
        }


# ------------------------------------------------------------ per-trace stats
def trace_stats(trace, matcher=None):
    """Speeds, stops and trail matches for one usable trace.

    Returns (numbers for traces.csv, step arrays for the plots), or
    (None, None) if nothing is left after cleaning.
    """
    parts, native, p2p = [], [], []
    n_unsorted = 0
    for seg in trace["segments"]:
        lat, lon, t, unsorted = clean_segment(seg)
        n_unsorted += unsorted
        if len(t) < 2:
            continue
        native.append(np.diff(t))
        # point to point, as in version 1 -- kept only for the wobble check
        v0, dt0, _ = steps(lat, lon, t)
        ok0 = (dt0 <= MAX_GAP_S) & (v0 >= STOP_SPEED_KMH) \
            & (v0 <= FAST_SPEED_KMH)
        p2p.append((v0[ok0], dt0[ok0]))
        # the real measurement: steps of at least MIN_STEP_S
        k = thin(t, MIN_STEP_S)
        if len(k) < 2:
            continue
        la, lo, tt = lat[k], lon[k], t[k]
        speed, dt, dist = steps(la, lo, tt)
        way = matcher.match(la, lo) if matcher else np.full(len(la), -1)
        parts.append({"speed": speed, "dt": dt, "dist": dist,
                      "win": window_stops(la, lo, tt, dt),
                      "way0": way[:-1], "way1": way[1:], "t0": tt[:-1],
                      "lat": la[:-1], "lon": lo[:-1]})
    if not parts:
        return None, None

    s = {key: np.concatenate([p[key] for p in parts]) for key in parts[0]}
    v, dt = s["speed"], s["dt"]
    gap = dt > MAX_GAP_S
    fast = (v > FAST_SPEED_KMH) & ~gap
    valid = ~gap & ~fast
    crude_stop = valid & (v < STOP_SPEED_KMH)
    win_stop = valid & s["win"]
    if matcher:
        cls0, cls1 = matcher.cls[s["way0"]], matcher.cls[s["way1"]]
        perm, bits = matcher.perm[s["way0"]], matcher.bits[s["way0"]]
    else:
        cls0 = cls1 = np.full(len(v), NONE)
        perm, bits = np.full(len(v), -1), np.zeros(len(v), int)
    on_trail = valid & (cls0 == TRAIL) & (cls1 == TRAIL)
    moving, moving_w = valid & ~crude_stop, valid & ~win_stop
    trail_mv, trail_mv_w = on_trail & ~crude_stop, on_trail & ~win_stop

    valid_s = dt[valid].sum()
    share = (lambda mask: float(dt[mask].sum() / valid_s)) if valid_s > 0 \
        else (lambda mask: np.nan)
    pv, pd_ = (np.concatenate([a for a, _ in p2p]),
               np.concatenate([b for _, b in p2p])) if p2p else ([], [])
    perm_time = [dt[trail_mv & (perm == i)].sum()
                 for i in range(len(PERMISSIONS))]
    pts = all_points(trace)
    t_all = np.array([p[2].timestamp() for p in pts])
    lon_all = np.array([p[1] for p in pts])
    local_days = np.unique(((t_all + lon_all / 15 * 3600) // 86400))
    first = pts[int(np.argmin(t_all))]

    row = {
        "n_segments": len(trace["segments"]),
        "unsorted_segments": n_unsorted,
        "start_utc": datetime.fromtimestamp(t_all.min(), timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "start_s": float(t_all.min()),
        "start_lat": first[0],
        "start_lon": first[1],
        "n_days": int(len(local_days)),
        "median_interval_s": float(np.median(np.concatenate(native))),
        "valid_min": valid_s / 60,
        "gap_min": dt[gap].sum() / 60,
        "fast_min": dt[fast].sum() / 60,
        "distance_km": s["dist"][valid].sum() / 1000,
        "median_speed_raw": wmedian(v[valid], dt[valid]),
        "median_speed_moving": wmedian(v[moving], dt[moving]),
        "median_speed_moving_window": wmedian(v[moving_w], dt[moving_w]),
        "median_speed_p2p": wmedian(pv, pd_),
        "frac_time_stopped": share(crude_stop),
        "frac_time_stopped_window": share(win_stop),
        "share_trail": share(valid & (cls0 == TRAIL)),
        "share_track": share(valid & (cls0 == TRACK)),
        "share_road": share(valid & (cls0 == ROAD)),
        "share_other_way": share(valid & ~np.isin(cls0, [TRAIL, TRACK, ROAD,
                                                         NONE])),
        "share_no_way": share(valid & (cls0 == NONE)),
        "trail_moving_min": dt[trail_mv].sum() / 60,
        "median_speed_trail": wmedian(v[trail_mv], dt[trail_mv]),
        "median_speed_trail_window": wmedian(v[trail_mv_w], dt[trail_mv_w]),
        "main_permission": PERMISSIONS[int(np.argmax(perm_time))]
        if sum(perm_time) > 0 else None,
    }
    row["band"] = band_of(row["median_speed_moving"])
    row["band_trail"] = band_of(row["median_speed_trail"]) \
        if row["trail_moving_min"] >= MIN_TRAIL_MIN else "little trail time"
    arrays = {"speed": v, "dt": dt, "valid": valid, "crude_stop": crude_stop,
              "win_stop": win_stop, "on_trail": on_trail, "cls": cls0,
              "perm": perm, "bits": bits, "t0": s["t0"],
              "lat": s["lat"], "lon": s["lon"]}
    return row, arrays


# ---------------------------------------------------------------- the audit
def timed_traces(texts, info):
    """Parse a box's pages, set the untimed points aside, join split traces.

    Also checks the API order on every page (no timestamped track may come
    after the untimed one) and notes it in info["order_check"].
    """
    pages, odd = [], 0
    for text in texts:
        traces = parse_gpx(text)
        kinds = [classify(t) for t in traces]
        seen_untimed = False
        for kind in kinds:
            seen_untimed |= kind == "untimed"
            if seen_untimed and kind in USABLE:
                info["order_check"] = "timestamped track after untimed one"
            odd += kind == "partly_timed"
        pages.append([t for t, k in zip(traces, kinds)
                      if k not in ("untimed", "empty")])
    info["partly_timed_tracks"] = odd
    return merge_pages(pages)


def trail_share_of_points(traces, untimed_texts, matcher):
    """How many usable and unusable GPS points lie on trails?

    The plain usable fraction counts every point, including car loggers on
    highways. For hiking, what matters is the usable fraction ON TRAILS:
    timestamped trail points / all trail points. Untimed points are only
    sampled (a few pages spread across the box), so their trail share is an
    estimate. Every point is tested raw (no thinning) so both sides compare
    like with like.
    """
    def on_trail(lat, lon):
        if not len(lat):
            return np.zeros(0, dtype=bool)
        return matcher.cls[matcher.match(np.array(lat), np.array(lon))] \
            == TRAIL

    tp = [p for tr in traces if classify(tr) in USABLE for p in all_points(tr)]
    up = [p for text in untimed_texts for tr in parse_gpx(text)
          if classify(tr) == "untimed" for p in all_points(tr)]
    t_on = on_trail([p[0] for p in tp], [p[1] for p in tp])
    u_on = on_trail([p[0] for p in up], [p[1] for p in up])
    return {"timed_points_checked": int(len(tp)),
            "timed_trail_share": float(t_on.mean()) if len(tp) else None,
            "untimed_points_sampled": int(len(up)),
            "untimed_trail_share": float(u_on.mean()) if len(up) else None}


def audit_region(region, boxes, cache_dir="cache", out_dir="results",
                 offline=False, max_pages=150, trails=True, quiet=False):
    """Run Gate 1 for one region. Returns (summary dict, per-trace table)."""
    say = (lambda *a: None) if quiet else print
    out = Path(out_dir) / region
    out.mkdir(parents=True, exist_ok=True)

    rows, box_log, steps_by_box = [], [], {}
    say(f"\n=== {region}: {len(boxes)} boxes ===")
    for box in boxes:
        check_box(box)
        name = box[0]
        texts, info, untimed_texts = download_box(cache_dir, region, box,
                                                  offline, max_pages)
        traces = timed_traces(texts, info)

        ways = get_ways(cache_dir, region, box, offline, say) if trails else None
        matcher = WayMatcher(ways, box) if ways else None
        info["ways"] = matcher.n_ways if matcher else None
        info["network"] = matcher.network() if matcher else None
        if matcher is not None:
            info.update(trail_share_of_points(traces, untimed_texts, matcher))

        box_steps, seen = [], set()
        for trace in traces:
            kind = classify(trace)
            if kind in USABLE:
                fp = fingerprint(trace)
                if fp in seen:
                    kind = "duplicate"     # same recording uploaded again
                seen.add(fp)
            row = {"box": name, "type": kind,
                   "n_points": len(all_points(trace)), "url": trace["url"],
                   "user": user_of(trace["url"])}
            if kind in USABLE:
                stats, arrays = trace_stats(trace, matcher)
                if stats is not None:
                    row.update(stats)
                    box_steps.append(arrays)
            rows.append(row)
        steps_by_box[name] = box_steps
        info["traces"] = sum(r["box"] == name and r["type"] in USABLE
                             for r in rows)
        box_log.append(info)

        pct = (f"{100 * info['points_timed'] / info['points_total']:.0f}%"
               if info["points_total"] else "-")
        say(f"  {name:28s} points={_fmt(info['points_total']):>9s}  "
            f"usable={_fmt(info['points_timed']):>9s} ({pct:>4s})  "
            f"traces={info['traces']:4d}  pages read={info['pages_read']:3d}  "
            f"ways={info['ways'] if info['ways'] is not None else '-'}  "
            f"[{info['status']}]")

    table = pd.DataFrame(rows)
    table["outing"] = group_outings(table)
    pooled = _pool(steps_by_box)
    summary = summarize(region, boxes, box_log, table, pooled, max_pages,
                        trails)
    table.to_csv(out / "traces.csv", index=False)
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=_to_builtin)
    saved = ["summary.json", "traces.csv"]
    if pooled is not None and summary["usable_traces"] > 0:
        save_speed_plots(region, out, table, pooled)
        saved.append("speed_histograms.png")
        if trails:
            save_map(region, out, boxes, steps_by_box)
            saved.append("trace_map.png")
    print_summary(summary, say)
    say(f"  saved in {out}/: " + ", ".join(saved))
    return summary, table


def _fmt(n):
    return "-" if n is None else f"{n:,}"


def _pool(steps_by_box):
    arrays = [a for box in steps_by_box.values() for a in box]
    if not arrays:
        return None
    return {key: np.concatenate([a[key] for a in arrays]) for key in arrays[0]}


def summarize(region, boxes, box_log, table, pooled, max_pages, trails):
    n = len(table)
    usable = table[table["type"].isin(USABLE)] if n else table
    if len(usable) and "median_speed_trail" in usable:
        trail_tr = usable[usable["trail_moving_min"] >= MIN_TRAIL_MIN]
    else:
        trail_tr = usable.iloc[0:0]
    counted = [b for b in box_log if b["points_total"] is not None]
    pts_total = sum(b["points_total"] for b in counted)
    pts_timed = sum(b["points_timed"] for b in counted)
    urls = usable["url"].dropna() if len(usable) else pd.Series(dtype=str)
    users = usable["user"].dropna() if len(usable) else pd.Series(dtype=str)

    s = {
        "region": region,
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": {  # decisions log: every threshold used in this run
            "stop_speed_kmh": STOP_SPEED_KMH,
            "fast_speed_kmh": FAST_SPEED_KMH,
            "min_step_s": MIN_STEP_S,
            "max_gap_s": MAX_GAP_S,
            "window_stop_s": WINDOW_STOP_S,
            "window_stop_m": WINDOW_STOP_M,
            "match_radius_m": MATCH_RADIUS_M,
            "min_trail_min": MIN_TRAIL_MIN,
            "continue_s": CONTINUE_S,
            "max_pages_per_box": max_pages,
            "trails": trails,
            "bands": BANDS,
            "boxes": boxes,
        },
        "boxes": box_log,
        "boxes_counted": f"{len(counted)} of {len(box_log)}",
        "points_total": pts_total,
        "points_usable": pts_timed,
        "usable_point_pct": 100 * pts_timed / pts_total if pts_total else None,
        "traces_by_type": table["type"].value_counts().to_dict() if n else {},
        "usable_traces": int(len(usable)),
        "identifiable_unique": int(urls.nunique()),
        "identifiable_users": int(users.nunique()),
        "trace_days": int(usable["n_days"].sum()) if "n_days" in usable else 0,
        "duplicates_removed": int((table["type"] == "duplicate").sum())
        if n else 0,
        "trail_traces": int(len(trail_tr)),
        "trail_outings": int(trail_tr["outing"].nunique()) if len(trail_tr)
        else 0,
        # independence: one person can upload many traces
        "trail_named_users": int(trail_tr["user"].nunique()) if len(trail_tr)
        else 0,
        "trail_anonymous_traces": int(trail_tr["user"].isna().sum())
        if len(trail_tr) else 0,
        "trail_top_user_traces": int(trail_tr["user"].value_counts().iloc[0])
        if len(trail_tr) and trail_tr["user"].notna().any() else None,
        "trail_trace_days": int(trail_tr["n_days"].sum()) if len(trail_tr)
        else 0,
        "median_trail_speed_kmh": float(trail_tr["median_speed_trail"]
                                        .median()) if len(trail_tr) else None,
        "median_trail_speed_window_kmh":
            float(trail_tr["median_speed_trail_window"].median())
            if len(trail_tr) else None,
        "trail_bands": trail_tr["band_trail"].value_counts().to_dict()
        if len(trail_tr) else {},
        "trail_traces_by_permission":
            trail_tr["main_permission"].value_counts().to_dict()
            if len(trail_tr) else {},
        "sampling_interval": _interval_bins(usable),
        "wobble_check": _wobble(trail_tr),
        "known_limitations": [
            "nearest-way matching is not real map-matching: near junctions "
            "and roads a point can pick the wrong way",
            "a trackable trace split across pages at a recording-segment "
            "break is counted twice",
            "a hike crossing two boxes is counted in both boxes (the "
            "Franconia and Lincoln Woods boxes also overlap slightly)",
            "speed bands are a rough first look, not mode inference",
            "the window stop rule is a first draft, not tuned",
            "page order shifts when someone uploads a new trace, so pages "
            "cached on different days may not line up exactly",
        ],
    }
    if pooled is not None:
        v, dt = pooled["speed"], pooled["dt"]
        valid, trail = pooled["valid"], pooled["on_trail"]
        vt = dt[valid].sum()
        s["time_share_by_way"] = {
            c: float(dt[valid & (pooled["cls"] == i)].sum() / vt) if vt else
            None for i, c in enumerate(CLASSES)}
        tt = dt[trail].sum()
        s["trail_hours"] = float(tt / 3600)
        s["trail_time_removed_pct"] = {
            "crude_0.5_kmh": float(100 * dt[trail & pooled["crude_stop"]]
                                   .sum() / tt) if tt else None,
            "window_60s_10m": float(100 * dt[trail & pooled["win_stop"]]
                                    .sum() / tt) if tt else None,
        }
        mv = trail & ~pooled["crude_stop"]
        mt = dt[mv].sum()
        s["trail_moving_time_by_permission"] = {
            p: float(dt[mv & (pooled["perm"] == i)].sum() / mt) if mt else None
            for i, p in enumerate(PERMISSIONS)}
        s["trail_moving_time_with_tag"] = {
            key: float(dt[mv & ((pooled["bits"] >> i) & 1 == 1)].sum() / mt)
            if mt else None for i, key in enumerate(TAG_KEYS)}
        months = pd.to_datetime(pooled["t0"][mv], unit="s").month
        by_month = pd.Series(dt[mv]).groupby(np.asarray(months)).sum()
        s["trail_moving_time_by_month"] = {
            int(m): float(x / mt) for m, x in by_month.items()} if mt else {}
    # usable fraction ON TRAILS (see trail_share_of_points)
    est = [b for b in box_log if b.get("points_total")
           and b.get("timed_trail_share") is not None
           and (b.get("untimed_trail_share") is not None
                or not b["points_untimed"])]
    if est:
        tt = sum(b["points_timed"] * b["timed_trail_share"] for b in est)
        ut = sum(b["points_untimed"] * (b.get("untimed_trail_share") or 0)
                 for b in est)
        s["trail_points_usable_est"] = round(tt)
        s["trail_points_unusable_est"] = round(ut)
        s["usable_on_trail_pct"] = 100 * tt / (tt + ut) if tt + ut else None
        s["usable_on_trail_boxes"] = f"{len(est)} of {len(box_log)}"
        timed = sum(b["points_timed"] for b in est)
        s["usable_points_on_trails_pct"] = 100 * tt / timed if timed else None
        s["boxes_cut_at_max_pages"] = [b["box"] for b in est
                                       if not b["usable_part_complete"]]
        s["untimed_points_sampled"] = sum(b.get("untimed_points_sampled", 0)
                                          for b in est)
    nets = [b["network"] for b in box_log if b.get("network")]
    if nets:
        km = sum(x["trail_km"] for x in nets)
        s["trail_network_km"] = km
        s["trail_network_share_with_tag"] = {
            key: sum(x["trail_km_with_tag"][key] for x in nets) / km
            if km else None for key in TAG_KEYS}
        s["trail_network_share_by_permission"] = {
            p: sum(x["trail_km_by_permission"][p] for x in nets) / km
            if km else None for p in PERMISSIONS}
    return s


def _interval_bins(usable):
    if not len(usable) or "median_interval_s" not in usable:
        return {}
    bins = [("1 s or less", 0, 1.5), ("2-5 s", 1.5, 5.5),
            ("6-15 s", 5.5, 15.5), ("over 15 s", 15.5, np.inf)]
    iv = usable["median_interval_s"]
    return {label: int(((iv >= lo) & (iv < hi)).sum())
            for label, lo, hi in bins}


def _wobble(trail_tr):
    """Does frequent recording inflate speed on REAL data? (README Lesson 2)

    For walking-pace trail traces recorded every 1-2 s, compare the version-1
    point-to-point speed with the 10-s-step speed used now.
    """
    if not len(trail_tr):
        return {}
    walk = trail_tr[(trail_tr["median_speed_trail"] < 6)
                    & (trail_tr["median_interval_s"] <= 2)]
    if not len(walk):
        return {"traces": 0}
    ratio = walk["median_speed_p2p"] / walk["median_speed_moving"]
    return {"traces": int(len(walk)),
            "median_p2p_kmh": float(walk["median_speed_p2p"].median()),
            "median_10s_kmh": float(walk["median_speed_moving"].median()),
            "median_inflation_pct": float(100 * (ratio.median() - 1))}


def print_summary(s, say):
    t = s["traces_by_type"]
    say(f"\n  Boxes fully counted: {s['boxes_counted']}")
    if s["points_total"]:
        say(f"  Usable points: {s['points_usable']:,} of "
            f"{s['points_total']:,} ({s['usable_point_pct']:.0f}%)"
            "   <- write this down (plan sec. 6)")
    else:
        say("  Nothing was counted -- check the box statuses above")
        say("  (network error? --offline with an empty cache?).")
        say("  This is NOT a Gate 1 result. Fix the download and re-run.")
        return
    if s.get("usable_on_trail_pct") is not None:
        say(f"  On trails only: ~{s['usable_on_trail_pct']:.0f}% of GPS points"
            f" are usable (~{s['trail_points_usable_est']:,} usable vs "
            f"~{s['trail_points_unusable_est']:,} unusable; unusable side "
            f"estimated from {s['untimed_points_sampled']:,} sampled points,"
            f" {s['usable_on_trail_boxes']} boxes)")
        say(f"  Of the usable points, ~{s['usable_points_on_trails_pct']:.0f}%"
            " are on trails (the rest: roads, lifts, off the map)")
        if s["boxes_cut_at_max_pages"]:
            say(f"  ! {', '.join(s['boxes_cut_at_max_pages'])}: usable pages "
                "cut at --max-pages, so trail numbers there use the newest "
                "uploads only")
    say(f"  Usable traces: {s['usable_traces']} (identifiable "
        f"{t.get('identifiable', 0)} from {s['identifiable_users']} users, "
        f"trackable {t.get('trackable', 0)}); trace-days "
        f"{s['trace_days']}")
    if s["usable_traces"] == 0:
        say("  Traces exist but none are usable. Plan says: try another")
        say("  region before building anything.")
        return
    if "time_share_by_way" in s:
        sh = s["time_share_by_way"]
        say("  Where the usable time is: "
            + ", ".join(f"{c} {100 * sh[c]:.0f}%" for c in
                        ("trail", "track", "road", "none") if sh[c] is not None)
            + f", lift/rail/piste/other "
            f"{100 * sum(sh[c] or 0 for c in ('lift', 'rail', 'piste', 'other')):.0f}%")
    say(f"  Trail traces (5+ moving min on trails): {s['trail_traces']}"
        f"  (separate outings {s['trail_outings']}, trace-days "
        f"{s['trail_trace_days']}, {s.get('trail_hours', 0):.0f} h on trails;"
        f" duplicate uploads dropped: {s['duplicates_removed']})")
    if s["trail_traces"]:
        top = s["trail_top_user_traces"]
        say(f"  Who: {s['trail_named_users']} named uploaders + "
            f"{s['trail_anonymous_traces']} anonymous traces"
            + (f"; busiest uploader has {top} traces" if top else ""))
    med = s["median_trail_speed_kmh"]
    b = s["trail_bands"]
    if med is not None:
        say(f"  Median on-trail moving speed per trace: {med:.1f} km/h "
            f"(window stop rule: {s['median_trail_speed_window_kmh']:.1f})")
        say(f"  Trail traces by speed: walking-like {b.get('walking-like', 0)}"
            f" | in-between {b.get('in-between', 0)} | cycling-like "
            f"{b.get('cycling-like', 0)} | other {b.get('other', 0)}")
    rm = s.get("trail_time_removed_pct", {})
    if rm.get("crude_0.5_kmh") is not None:
        say(f"  Trail time removed as stops: crude 0.5 km/h rule "
            f"{rm['crude_0.5_kmh']:.1f}%  vs  draft 60 s / 10 m rule "
            f"{rm['window_60s_10m']:.1f}%")
    if s.get("trail_moving_time_by_permission"):
        pm = s["trail_moving_time_by_permission"]
        say("  On-trail moving time by permitted mode: "
            + ", ".join(f"{p} {100 * pm[p]:.0f}%" for p in PERMISSIONS
                        if pm[p]))
    if s.get("trail_network_share_with_tag"):
        tg = s["trail_network_share_with_tag"]
        say(f"  Trail network {s['trail_network_km']:.0f} km; share with tag: "
            + ", ".join(f"{k} {100 * tg[k]:.0f}%" for k in
                        ("surface", "sac_scale", "width", "trail_visibility")))
    say("\n  Gate 1 checks (plan section 6):")
    say(f"   - usable share of points: {s['usable_point_pct']:.0f}%; "
        f"trail traces: {s['trail_traces']} -> 'enough'? decide with "
        "Danni and Tianyi")
    if med is not None:
        ok = 1.5 <= med <= 5.0
        say(f"   - median on-trail speed in walking range 1.5-5 km/h: "
            f"{'YES' if ok else 'NO'} ({med:.1f})")
        say(f"   - faster second lobe (cyclists): "
            f"{b.get('cycling-like', 0)} trail traces at 10-30 km/h")
    w = s["wobble_check"]
    if w.get("traces"):
        say(f"\n  Wobble check, walking trail traces recorded every 1-2 s "
            f"(n={w['traces']}): point-to-point {w['median_p2p_kmh']:.1f} "
            f"km/h vs 10-s steps {w['median_10s_kmh']:.1f} km/h "
            f"(median inflation {w['median_inflation_pct']:+.0f}%)")


# --------------------------------------------------------------------- plots
def save_speed_plots(region, out, table, pooled):
    usable = table[table["type"].isin(USABLE)]
    bins = np.arange(0, 30.5, 0.5)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    trail_tr = usable[usable.get("trail_moving_min", 0) >= MIN_TRAIL_MIN] \
        if "trail_moving_min" in usable else usable.iloc[0:0]
    per_trace = trail_tr["median_speed_trail"].dropna() if len(trail_tr) \
        else pd.Series(dtype=float)
    hidden = int((per_trace > 30).sum())
    ax1.axvspan(1.5, 5, color="#9FE1CB", alpha=0.55, label="walking 1.5-5")
    ax1.axvspan(10, 25, color="#B5D4F4", alpha=0.55, label="cycling 10-25")
    ax1.hist(per_trace[per_trace <= 30], bins=bins, color="#185FA5")
    ax1.set_title(f"One value per trail trace (n={len(per_trace)}): "
                  "median moving speed on trails"
                  + (f"\n({hidden} above 30 km/h not shown)" if hidden else ""),
                  fontsize=10)
    ax1.set_xlabel("speed (km/h)")
    ax1.set_ylabel("number of traces")
    ax1.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax1.legend()

    v, dt = pooled["speed"], pooled["dt"]
    trail = pooled["on_trail"] & (v <= 30)
    for mask, color, label in [
            (trail, "#888780", "all trail time (includes stops)"),
            (trail & ~pooled["crude_stop"], "#D85A30",
             f"after crude rule (< {STOP_SPEED_KMH} km/h removed)"),
            (trail & ~pooled["win_stop"], "#1D9E75",
             f"after draft rule ({WINDOW_STOP_S:.0f} s, "
             f"< {WINDOW_STOP_M:.0f} m removed)")]:
        ax2.hist(v[mask], bins=bins, weights=dt[mask] / 3600,
                 histtype="step", lw=2, color=color, label=label)
    ax2.set_title("All on-trail steps (10 s or longer), weighted by time",
                  fontsize=10)
    ax2.set_xlabel("speed (km/h)")
    ax2.set_ylabel("hours")
    ax2.legend(fontsize=8)

    fig.suptitle(f"{region}: Gate 1 speed check (real OSM traces, "
                 "points matched to OSM trails)")
    fig.tight_layout()
    fig.savefig(out / "speed_histograms.png", dpi=150)
    plt.close(fig)


MAP_COLORS = {"trail": "#D85A30", "track": "#8B5E3C", "road": "#888780",
              "lift": "#7F3FBF", "rail": "#7F3FBF", "piste": "#7F3FBF",
              "other": "#B5D4F4", "none": "#185FA5"}


def save_map(region, out, boxes, steps_by_box, max_points=80_000):
    """Where the usable points are, colored by the kind of way they match."""
    rng = np.random.default_rng(0)
    ncols = min(4, len(boxes))                 # many tiles -> a grid of maps
    nrows = int(np.ceil(len(boxes) / ncols))
    fig, axes = plt.subplots(nrows, ncols, squeeze=False,
                             figsize=(max(12, 4.2 * ncols), 4.6 * nrows))
    for ax in axes.ravel()[len(boxes):]:
        ax.set_visible(False)
    for ax, box in zip(axes.ravel(), boxes):
        name, west, south, east, north = box
        arrays = steps_by_box.get(name, [])
        if arrays:
            lat = np.concatenate([a["lat"] for a in arrays])
            lon = np.concatenate([a["lon"] for a in arrays])
            cls = np.concatenate([a["cls"] for a in arrays])
            if len(lat) > max_points:
                pick = rng.choice(len(lat), max_points, replace=False)
                lat, lon, cls = lat[pick], lon[pick], cls[pick]
            for i, c in enumerate(CLASSES):
                m = cls == i
                if m.any():
                    ax.scatter(lon[m], lat[m], s=0.3, color=MAP_COLORS[c],
                               rasterized=True,
                               label=c if c in ("trail", "track", "road",
                                                "none") else None)
        ax.set_xlim(west, east)
        ax.set_ylim(south, north)
        ax.set_aspect(1 / np.cos(np.radians((south + north) / 2)))
        ax.set_title(name, fontsize=9)
        ax.tick_params(labelsize=7)
    handles = [plt.Line2D([], [], marker="o", ls="", color=MAP_COLORS[c],
                          label="no way within 25 m" if c == "none" else c)
               for c in ("trail", "track", "road", "none")]
    handles.append(plt.Line2D([], [], marker="o", ls="", color="#7F3FBF",
                              label="lift / railway / ski run"))
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=8)
    fig.suptitle(f"{region}: usable GPS points by the OSM way they match")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out / "trace_map.png", dpi=150)
    plt.close(fig)


def save_comparison(summaries, out_dir):
    """One figure comparing the regions -- the plot for the weekly meeting."""
    names = [s["region"] for s in summaries]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))

    ax = axes[0]
    y = np.arange(len(summaries))
    for offset, key, label in [(0.2, "usable_point_pct", "all points"),
                               (-0.2, "usable_on_trail_pct",
                                "trail points only")]:
        pct = np.array([s.get(key) or 0 for s in summaries])
        ax.barh(y + offset, pct, height=0.38, color="#1D9E75")
        ax.barh(y + offset, 100 - pct, left=pct, height=0.38,
                color="#D3D1C7")
        for i, p in enumerate(pct):
            ax.text(1.5, y[i] + offset, f"{label}: {p:.0f}% usable",
                    va="center", fontsize=7.5, color="white")
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of GPS points with timestamps (green)")
    ax.set_title("Are the points usable?", fontsize=10)

    ax = axes[1]
    bins = np.arange(0, 30.5, 1.0)
    colors = ["#185FA5", "#D85A30", "#1D9E75", "#7F3FBF"]
    for s, color in zip(summaries, colors):
        path = Path(out_dir) / s["region"] / "traces.csv"
        t = pd.read_csv(path)
        if "trail_moving_min" not in t:
            continue
        v = t.loc[t["trail_moving_min"] >= MIN_TRAIL_MIN,
                  "median_speed_trail"].dropna()
        ax.hist(v[v <= 30], bins=bins, histtype="step", lw=2, color=color,
                label=f"{s['region']} (n={len(v)})")
    ax.axvspan(1.5, 5, color="#9FE1CB", alpha=0.4)
    ax.set_xlabel("median on-trail moving speed per trace (km/h)")
    ax.set_ylabel("number of trail traces")
    ax.set_title("How fast? (shaded: walking 1.5-5 km/h)", fontsize=10)
    ax.legend(fontsize=8)

    ax = axes[2]
    left = np.zeros(len(summaries))
    perm_colors = ["#185FA5", "#D85A30", "#8B5E3C", "#7F3FBF", "#D3D1C7"]
    for p, color in zip(PERMISSIONS, perm_colors):
        vals = np.array([100 * (s.get("trail_moving_time_by_permission", {})
                                .get(p) or 0) for s in summaries])
        ax.barh(names, vals, left=left, color=color, label=p)
        left += vals
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of on-trail moving time")
    ax.set_title("Which modes do those trails allow? (OSM tags)",
                 fontsize=10)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.16),
              ncol=3, frameon=False)

    fig.suptitle("Gate 1: region comparison (real OSM traces, "
                 f"{datetime.now():%d %b %Y})")
    fig.tight_layout()
    fig.savefig(Path(out_dir) / "region_comparison.png", dpi=150)
    plt.close(fig)


def _to_builtin(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Gate 1: are the traces usable?")
    ap.add_argument("--region", required=True,
                    choices=sorted(REGIONS) + ["all"])
    ap.add_argument("--cache-dir", default="cache")
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--offline", action="store_true",
                    help="use saved files only, never download")
    ap.add_argument("--max-pages", type=int, default=150,
                    help="max pages of usable points per box (5,000 each)")
    ap.add_argument("--no-trails", action="store_true",
                    help="skip the OSM trail/road download and matching")
    args = ap.parse_args()

    names = sorted(REGIONS) if args.region == "all" else [args.region]
    summaries = [audit_region(r, REGIONS[r], args.cache_dir, args.out_dir,
                              args.offline, args.max_pages,
                              not args.no_trails)[0] for r in names]

    if len(summaries) > 1:
        table = pd.DataFrame([{
            "region": s["region"],
            "points": s["points_total"],
            "usable_points_pct": round(s["usable_point_pct"] or 0, 1),
            "usable_on_trail_pct": round(s.get("usable_on_trail_pct") or 0, 1),
            "usable_traces": s["usable_traces"],
            "identifiable_users": s["identifiable_users"],
            "trail_traces": s["trail_traces"],
            "trail_outings": s["trail_outings"],
            "trail_trace_days": s["trail_trace_days"],
            "trail_hours": round(s.get("trail_hours", 0), 1),
            "median_trail_kmh": s["median_trail_speed_kmh"],
            "walking_like": s["trail_bands"].get("walking-like", 0),
            "cycling_like": s["trail_bands"].get("cycling-like", 0),
            "foot_only_pct": round(100 * (s.get(
                "trail_moving_time_by_permission", {}).get("foot-only") or 0)),
            "bike_permitted_pct": round(100 * sum(
                s.get("trail_moving_time_by_permission", {}).get(p) or 0
                for p in ("bicycle-permitted", "bike+horse"))),
            "sac_scale_tagged_pct": round(100 * (s.get(
                "trail_network_share_with_tag", {}).get("sac_scale") or 0)),
            "boxes_counted": s["boxes_counted"],
        } for s in summaries])
        print("\n=== Region comparison (trace side) ===")
        print(table.to_string(index=False))
        path = Path(args.out_dir) / "region_comparison.csv"
        table.to_csv(path, index=False)
        save_comparison(summaries, args.out_dir)
        print(f"saved: {path} and region_comparison.png")


if __name__ == "__main__":
    main()
