#!/usr/bin/env python3
"""
Gate 1 audit: are the OpenStreetMap GPS traces in a region usable?

PLAIN-ENGLISH SUMMARY
To measure walking speed you need GPS points that have timestamps AND are in
time order. OpenStreetMap only gives you that for traces uploaded as
"identifiable" or "trackable". Traces uploaded as "public" come back with
their points sorted by position (for privacy), so no speed can be computed.

This script answers the Gate 1 question (semester plan, section 6):
  1. Download GPS points for a few small boxes in a region. Every page is
     saved to disk the first time and never downloaded again.
  2. Sort each trace into: identifiable / trackable / unordered.
  3. For usable traces, compute the speed between each pair of points.
  4. Drop "stops" (speed under 0.5 km/h): lunch, photos, resting.
  5. Report the usable fraction and save two speed histograms.

HOW TO RUN
  python gate1_audit.py --region white_mountains
  python gate1_audit.py --region all                  # all three candidates
  python gate1_audit.py --region cascades --offline   # re-run from saved pages

Needs only: requests, numpy, pandas, matplotlib
"""

import argparse
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # save plots to files, no window needed
import matplotlib.pyplot as plt
import matplotlib.ticker

# ------------------------------------------------------------------ settings
API_URL = "https://api.openstreetmap.org/api/0.6/trackpoints"
POINTS_PER_PAGE = 5000     # OSM returns at most 5,000 points per page
MAX_BOX_DEG = 0.25         # OSM limit: box width and height each <= 0.25 deg
STOP_SPEED_KMH = 0.5       # crude stop threshold from plan section 6
GLITCH_SPEED_KMH = 60.0    # faster than this on a trail = GPS glitch
REQUEST_DELAY_S = 1.0      # pause between downloads; OSM is volunteer-run
USER_AGENT = "WashU-MVRL-travel-speed-gate1/0.1 (contact: zhou.n@wustl.edu)"

# Rough speed bands for a FIRST LOOK only. This is not mode detection --
# real mode inference needs the trail's access tags (plan section 8).
BANDS = [
    ("walking-like", 1.5, 6.0),
    ("in-between", 6.0, 10.0),
    ("cycling-like", 10.0, 30.0),
]

# Sample boxes over popular trail areas: (name, west, south, east, north).
# These are starting points for the audit. Edit freely, but keep each side
# of every box at or under 0.25 degrees.
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

    Each trace: {"name", "desc", "url", "points": [(lat, lon, time|None)]}
    """
    root = ET.fromstring(xml_text)
    traces = []
    for trk in root:
        if _local(trk.tag) != "trk":
            continue
        trace = {"name": None, "desc": None, "url": None, "points": []}
        for child in trk:
            tag = _local(child.tag)
            if tag in ("name", "desc", "url"):
                trace[tag] = (child.text or "").strip() or None
            elif tag == "trkseg":
                for pt in child:
                    if _local(pt.tag) != "trkpt":
                        continue
                    when = None
                    for sub in pt:
                        if _local(sub.tag) == "time":
                            when = parse_time(sub.text)
                    trace["points"].append(
                        (float(pt.get("lat")), float(pt.get("lon")), when))
        traces.append(trace)
    return traces


def merge_pages(traces):
    """Join identifiable traces that were split across pages (same URL).

    Unnamed (trackable) traces cannot be joined, so a trackable trace that
    straddles a page boundary is counted twice. Known limitation.
    """
    merged, by_url = [], {}
    for trace in traces:
        url = trace["url"]
        if url and url in by_url:
            by_url[url]["points"].extend(trace["points"])
            continue
        if url:
            by_url[url] = trace
        merged.append(trace)
    return merged


def classify(trace):
    """identifiable / trackable = usable. unordered = shuffled, unusable."""
    pts = trace["points"]
    if len(pts) < 2:
        return "too_short"
    times = [p[2] for p in pts]
    if any(t is None for t in times):
        return "unordered"            # no timestamps: speed impossible
    if any(b < a for a, b in zip(times, times[1:])):
        return "unordered"            # time goes backwards: points shuffled
    return "identifiable" if (trace["url"] or trace["name"]) else "trackable"


# --------------------------------------------------------------------- speeds
def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between points on the Earth's surface."""
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def segment_speeds(points):
    """Speed (km/h), duration (s), distance (m) for each consecutive pair.

    Worked example: two points 25 m apart, 30 s apart
      -> 25 / 30 = 0.833 m/s -> x 3.6 = 3.0 km/h
    """
    lat = np.array([p[0] for p in points])
    lon = np.array([p[1] for p in points])
    t = np.array([p[2].timestamp() for p in points])
    dist = haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])
    dt = np.diff(t)
    ok = dt > 0                       # skip duplicate timestamps
    return dist[ok] / dt[ok] * 3.6, dt[ok], dist[ok]


def band_of(speed):
    if speed is None or np.isnan(speed):
        return "unknown"
    for name, lo, hi in BANDS:
        if lo <= speed < hi:
            return name
    return "other"


def trace_stats(trace):
    speed, dt, dist = segment_speeds(trace["points"])
    glitch = speed > GLITCH_SPEED_KMH
    speed, dt, dist = speed[~glitch], dt[~glitch], dist[~glitch]
    moving = speed >= STOP_SPEED_KMH
    total_s = dt.sum()
    stats = {
        "duration_min": total_s / 60,
        "distance_km": dist.sum() / 1000,
        "median_interval_s": float(np.median(dt)) if dt.size else np.nan,
        "median_speed_raw": float(np.median(speed)) if speed.size else np.nan,
        "median_speed_moving":
            float(np.median(speed[moving])) if moving.any() else np.nan,
        "frac_time_stopped":
            float(dt[~moving].sum() / total_s) if total_s > 0 else np.nan,
        "n_glitch_segments": int(glitch.sum()),
    }
    stats["band"] = band_of(stats["median_speed_moving"])
    return stats, speed, dt, moving


# ---------------------------------------------------------------- the audit
def audit_region(region, boxes, cache_dir="cache", out_dir="results",
                 offline=False, max_pages=10, quiet=False):
    """Run Gate 1 for one region. Returns (summary dict, per-trace table)."""
    say = (lambda *a: None) if quiet else print
    out = Path(out_dir) / region
    out.mkdir(parents=True, exist_ok=True)

    rows, box_log = [], []
    seg_raw, w_raw, seg_mov, w_mov = [], [], [], []

    say(f"\n=== {region}: {len(boxes)} boxes ===")
    for box in boxes:
        check_box(box)
        name = box[0]
        page_traces, pages, status = [], 0, "ok"
        for page in range(max_pages):
            text, source = get_page(cache_dir, region, box, page, offline)
            if text is None:
                if source != "missing" or page == 0:
                    status = source
                break
            traces = parse_gpx(text)
            page_traces.extend(traces)
            pages += 1
            if sum(len(t["points"]) for t in traces) < POINTS_PER_PAGE:
                break                  # last page reached
        else:
            status = "hit page limit (counts partial)"

        traces = merge_pages(page_traces)
        n_pts = sum(len(t["points"]) for t in traces)
        say(f"  {name:32s} pages={pages:2d}  traces={len(traces):4d}  "
            f"points={n_pts:7d}  [{status}]")
        box_log.append({"box": name, "pages": pages, "traces": len(traces),
                        "points": n_pts, "status": status})

        for trace in traces:
            kind = classify(trace)
            row = {"box": name, "type": kind,
                   "n_points": len(trace["points"]), "url": trace["url"]}
            if kind in ("identifiable", "trackable"):
                stats, speed, dt, moving = trace_stats(trace)
                row.update(stats)
                seg_raw.append(speed)
                w_raw.append(dt)
                seg_mov.append(speed[moving])
                w_mov.append(dt[moving])
            rows.append(row)

    table = pd.DataFrame(rows)
    summary = summarize(region, boxes, box_log, table, seg_raw, w_raw,
                        seg_mov, w_mov, max_pages)

    table.to_csv(out / "traces.csv", index=False)
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=_to_builtin)
    if summary["usable_traces"] > 0:
        save_plots(region, out, table, seg_raw, w_raw, seg_mov, w_mov)
    print_summary(summary, say)
    say(f"  saved: {out}/summary.json, traces.csv"
        + (", speed_histograms.png" if summary["usable_traces"] else ""))
    return summary, table


def summarize(region, boxes, box_log, table, seg_raw, w_raw, seg_mov, w_mov,
              max_pages):
    n = len(table)
    types = table["type"].value_counts().to_dict() if n else {}
    usable = table[table["type"].isin(["identifiable", "trackable"])] if n \
        else table
    pts_total = int(table["n_points"].sum()) if n else 0
    pts_usable = int(usable["n_points"].sum()) if len(usable) else 0

    raw_s = float(np.concatenate(w_raw).sum()) if w_raw else 0.0
    mov_s = float(np.concatenate(w_mov).sum()) if w_mov else 0.0
    moving_medians = usable["median_speed_moving"].dropna() \
        if len(usable) else pd.Series(dtype=float)

    return {
        "region": region,
        "settings": {  # decisions log: every threshold used in this run
            "stop_speed_kmh": STOP_SPEED_KMH,
            "glitch_speed_kmh": GLITCH_SPEED_KMH,
            "max_pages_per_box": max_pages,
            "bands": BANDS,
            "boxes": boxes,
        },
        "boxes": box_log,
        "traces_total": n,
        "by_type": types,
        "usable_traces": len(usable),
        "usable_trace_pct": 100 * len(usable) / n if n else 0.0,
        "points_total": pts_total,
        "points_usable": pts_usable,
        "usable_point_pct": 100 * pts_usable / pts_total if pts_total else 0.0,
        "median_moving_speed_kmh":
            float(moving_medians.median()) if len(moving_medians) else None,
        "time_removed_by_stop_filter_pct":
            100 * (1 - mov_s / raw_s) if raw_s else None,
        "bands": usable["band"].value_counts().to_dict()
            if len(usable) and "band" in usable else {},
        "speed_by_interval": speed_by_interval(usable),
        "known_limitations": [
            "0.5 km/h stop filter is crude: GPS jitter can hide real stops",
            "trackable traces split across pages are counted twice",
            "a hike crossing two boxes is counted in both boxes",
            "speed bands are a rough first look, not mode inference",
            "point-to-point speed is inflated when GPS records very often",
        ],
    }


def speed_by_interval(usable):
    """Compare slow traces recorded at different GPS intervals.

    If traces recorded every few seconds look faster than traces recorded
    every 15+ seconds, GPS wobble is probably inflating their speed.
    Only traces under 10 km/h are used, so cyclists don't skew it.
    """
    groups = {}
    if not len(usable) or "median_interval_s" not in usable:
        return groups
    slow = usable[usable["median_speed_moving"] < 10]
    for label, lo, hi in [("under 5 s", 0, 5), ("5-15 s", 5, 15),
                          ("over 15 s", 15, np.inf)]:
        sel = slow[(slow["median_interval_s"] >= lo)
                   & (slow["median_interval_s"] < hi)]
        v = sel["median_speed_moving"].dropna()
        groups[label] = {"traces": int(len(sel)),
                         "median_speed_kmh": float(v.median()) if len(v)
                         else None}
    return groups


def print_summary(s, say):
    t = s["by_type"]
    say(f"\n  Traces found: {s['traces_total']}   "
        f"(identifiable {t.get('identifiable', 0)}, "
        f"trackable {t.get('trackable', 0)}, "
        f"unordered {t.get('unordered', 0)}, "
        f"too short {t.get('too_short', 0)})")
    say(f"  Usable traces: {s['usable_traces']} of {s['traces_total']} "
        f"({s['usable_trace_pct']:.0f}%)")
    say(f"  Usable points: {s['points_usable']:,} of {s['points_total']:,} "
        f"({s['usable_point_pct']:.0f}%)   <- write this down (plan sec. 6)")
    if s["traces_total"] == 0:
        say("  Nothing was downloaded -- check the box statuses above")
        say("  (network error? --offline with an empty cache?).")
        say("  This is NOT a Gate 1 result. Fix the download and re-run.")
        return
    if s["usable_traces"] == 0:
        say("  Traces exist but none are usable (all shuffled). Plan says:")
        say("  try another region before building anything.")
        return
    med = s["median_moving_speed_kmh"]
    b = s["bands"]
    say(f"  Median moving speed per trace: {med:.1f} km/h")
    say(f"  Time removed by stop filter: "
        f"{s['time_removed_by_stop_filter_pct']:.1f}%")
    say(f"  Speed bands: walking-like {b.get('walking-like', 0)} | "
        f"in-between {b.get('in-between', 0)} | "
        f"cycling-like {b.get('cycling-like', 0)} | "
        f"other {b.get('other', 0)}")
    say("\n  Gate 1 checks (plan section 6):")
    say(f"   - ordered traces found: {s['usable_traces']}  "
        f"-> is that 'enough'? decide with Danni and Tianyi")
    ok = 1.5 <= med <= 5.0
    say(f"   - median speed in walking range 1.5-5 km/h: "
        f"{'YES' if ok else 'NO'} ({med:.1f})")
    say(f"   - faster second lobe (cyclists): "
        f"{b.get('cycling-like', 0)} traces at 10-30 km/h")

    parts = []
    for label, g in s["speed_by_interval"].items():
        v = g["median_speed_kmh"]
        parts.append(f"{label}: " + (f"{v:.1f} km/h" if v is not None
                                     else "-") + f" (n={g['traces']})")
    if parts:
        say("\n  Wobble check -- slow traces by GPS interval:")
        say("   " + " | ".join(parts))
        say("   (if 'under 5 s' is clearly faster, GPS wobble is "
            "inflating speed)")


def save_plots(region, out, table, seg_raw, w_raw, seg_mov, w_mov):
    usable = table[table["type"].isin(["identifiable", "trackable"])]
    bins = np.arange(0, 30.5, 0.5)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    per_trace = usable["median_speed_moving"].dropna()
    hidden = int((per_trace > 30).sum())
    ax1.axvspan(1.5, 5, color="#9FE1CB", alpha=0.55, label="walking 1.5-5")
    ax1.axvspan(10, 25, color="#B5D4F4", alpha=0.55, label="cycling 10-25")
    ax1.hist(per_trace[per_trace <= 30], bins=bins, color="#185FA5")
    ax1.set_title("One value per trace: median moving speed"
                  + (f"\n({hidden} traces above 30 km/h not shown)"
                     if hidden else ""))
    ax1.set_xlabel("speed (km/h)")
    ax1.set_ylabel("number of traces")
    ax1.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax1.legend()

    raw, wr = np.concatenate(seg_raw), np.concatenate(w_raw)
    mov, wm = np.concatenate(seg_mov), np.concatenate(w_mov)
    ax2.hist(raw[raw <= 30], bins=bins, weights=wr[raw <= 30] / 60,
             histtype="step", lw=2, color="#888780",
             label="raw (includes stops)")
    ax2.hist(mov[mov <= 30], bins=bins, weights=wm[mov <= 30] / 60,
             histtype="step", lw=2, color="#D85A30",
             label=f"after stop filter (< {STOP_SPEED_KMH} km/h removed)")
    ax2.set_title("All segments, weighted by time")
    ax2.set_xlabel("speed (km/h)")
    ax2.set_ylabel("minutes")
    ax2.legend()

    fig.suptitle(f"{region}: Gate 1 speed check (usable traces only)")
    fig.tight_layout()
    fig.savefig(out / "speed_histograms.png", dpi=150)
    plt.close(fig)


def _to_builtin(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return str(obj)


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Gate 1: are the traces usable?")
    ap.add_argument("--region", required=True,
                    choices=sorted(REGIONS) + ["all"])
    ap.add_argument("--cache-dir", default="cache")
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--offline", action="store_true",
                    help="use saved pages only, never download")
    ap.add_argument("--max-pages", type=int, default=10,
                    help="pages per box (5,000 points each)")
    args = ap.parse_args()

    names = sorted(REGIONS) if args.region == "all" else [args.region]
    summaries = [audit_region(r, REGIONS[r], args.cache_dir, args.out_dir,
                              args.offline, args.max_pages)[0] for r in names]

    if len(summaries) > 1:
        table = pd.DataFrame([{
            "region": s["region"],
            "traces": s["traces_total"],
            "usable_traces": s["usable_traces"],
            "usable_points_pct": round(s["usable_point_pct"], 1),
            "median_moving_kmh": s["median_moving_speed_kmh"],
            "walking_like": s["bands"].get("walking-like", 0),
            "cycling_like": s["bands"].get("cycling-like", 0),
            "boxes_cut_off": sum("limit" in b["status"] for b in s["boxes"]),
        } for s in summaries])
        print("\n=== Region comparison (trace side only) ===")
        print(table.to_string(index=False))
        path = Path(args.out_dir) / "region_comparison.csv"
        table.to_csv(path, index=False)
        print(f"saved: {path}")


if __name__ == "__main__":
    main()
