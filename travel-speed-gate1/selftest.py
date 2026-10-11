#!/usr/bin/env python3
"""
Self-test for gate1_audit.py (version 2) using FAKE data. No internet needed.

It builds fake OSM-style pages in the same order the real API uses (every
timestamped point first, then the untimed points sorted by latitude), plus
fake OSM trails and roads, runs the real audit code on them offline, and
checks the answers.

The fake traces (we know the true answer for each one):
  A. identifiable walker, 4 km/h, GPS every 5 s, with a 10-minute stop
  B. trackable walker, 3 km/h, GPS every 5 s, split across two pages
  C. trackable cyclist, 16 km/h, GPS every 5 s, on a cycleway
  D. trackable "winter hiker": 3 hikes on 3 days in one upload, stored out
     of date order (version 1 wrongly called this shuffled)
  E. identifiable walker, 3.5 km/h, no GPS wobble, split across two pages
  F. identifiable car logger: 10 points per second but whole-second
     timestamps, 40 km/h on a road (version 1 read it at walking pace)
  G. trace B uploaded a second time (a duplicate)
  + 9,000 untimed "public" points, sorted by latitude, after all of the above

Run:  python selftest.py      -> should end with "ALL CHECKS PASSED"
"""

import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gate1_audit as g

M_PER_DEG_LAT = 111_195.0
rng = np.random.default_rng(42)
START = datetime(2025, 7, 12, 13, 0, 0, tzinfo=timezone.utc)
REGION = "SYNTHETIC_selftest"
BOX = ("box_a", -71.40, 44.20, -71.30, 44.30)


def walk(lat, lon, speed_kmh, every_s, n, noise_m=1.5, stop=None,
         start=START):
    """Fake GPS track heading north. stop=(first_index, n_points) stands still.

    Each point gets a little random GPS error (noise_m), like a real phone.
    Timestamps are whole seconds, so every_s=0.1 makes a logger that records
    10 points per second but stores only whole seconds (like the real car
    loggers on OSM).
    """
    pts, v = [], speed_kmh / 3.6
    for i in range(n):
        standing = stop is not None and stop[0] <= i < stop[0] + stop[1]
        if i > 0 and not standing:
            lat += v * every_s / M_PER_DEG_LAT
        jitter_lat = rng.normal(0, noise_m) / M_PER_DEG_LAT
        jitter_lon = rng.normal(0, noise_m) / (
            M_PER_DEG_LAT * np.cos(np.radians(lat)))
        when = start + timedelta(seconds=int(i * every_s))
        pts.append((lat + jitter_lat, lon + jitter_lon, when))
    return pts


def api_pages(traces, untimed):
    """Write fake pages exactly the way the OSM API orders them.

    traces: list of {"name", "url", "segments"} in upload order (newest
    first). All their points come first, then the untimed points.
    """
    flat = [(k, s, p) for k, tr in enumerate(traces)
            for s, seg in enumerate(tr["segments"]) for p in seg]
    flat += [(None, None, p) for p in untimed]
    pages = []
    for start in range(0, len(flat), g.POINTS_PER_PAGE):
        chunk = flat[start:start + g.POINTS_PER_PAGE]
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<gpx version="1.0" creator="OpenStreetMap.org" '
               'xmlns="http://www.topografix.com/GPX/1/0">']
        cur = None
        for k, s, (lat, lon, when) in chunk:
            if (k, s) != cur:
                if cur is not None:
                    out.append("</trkseg>")
                if cur is None or k != cur[0]:
                    if cur is not None:
                        out.append("</trk>")
                    out.append("<trk>")
                    tr = traces[k] if k is not None else {}
                    for key in ("name", "url"):
                        if tr.get(key):
                            out.append(f"<{key}>{tr[key]}</{key}>")
                out.append("<trkseg>")
                cur = (k, s)
            if when is None:
                out.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}"/>')
            else:
                out.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}">'
                           f'<time>{when:%Y-%m-%dT%H:%M:%SZ}</time></trkpt>')
        if cur is not None:
            out.append("</trkseg></trk>")
        out.append("</gpx>")
        pages.append("\n".join(out))
    return pages


def fake_ways():
    """North-south trails and a road, one per fake trace."""
    def line(lon, tags):
        return {"type": "way", "tags": tags,
                "geometry": [{"lat": lat, "lon": lon}
                             for lat in np.linspace(44.19, 44.31, 25)]}
    hiking = {"highway": "path", "bicycle": "no", "horse": "no",
              "surface": "ground", "sac_scale": "hiking"}
    return [line(-71.35, hiking), line(-71.36, hiking), line(-71.37, hiking),
            line(-71.33, {"highway": "footway"}),
            line(-71.34, {"highway": "cycleway", "surface": "gravel"}),
            line(-71.32, {"highway": "secondary"})]


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label} {detail}")
    if not condition:
        raise SystemExit("SELF-TEST FAILED")


def main():
    tmp = Path(tempfile.mkdtemp())
    cache = tmp / "cache"
    (cache / REGION).mkdir(parents=True)

    # ---- the fake traces (true answers known)
    url = "https://api.openstreetmap.org/user/test/traces/"
    walker_a = walk(44.21, -71.35, 4.0, 5, 600, stop=(240, 120))
    cyclist = walk(44.21, -71.34, 16.0, 5, 300)
    winter = [walk(44.22, -71.37, 2.5, 10, 300, start=START + timedelta(days=d))
              for d in (2, 0, 1)]                        # stored out of order
    walker_e = walk(44.22, -71.33, 3.5, 1, 4000, noise_m=0)
    car = walk(44.21, -71.32, 40.0, 0.1, 3600)
    walker_b = walk(44.21, -71.36, 3.0, 5, 1200)
    traces = [
        {"name": "saturday_hike.gpx", "url": url + "7", "segments": [walker_a]},
        {"segments": [cyclist]},
        {"segments": winter},
        {"name": "long_walk.gpx", "url": url + "5", "segments": [walker_e]},
        {"name": "drive.gpx", "url": url + "4", "segments": [car]},
        {"segments": [walker_b]},
        {"segments": [walker_b]},                         # G: duplicate of B
    ]
    untimed = sorted((44.20 + rng.random() * 0.1, -71.40 + rng.random() * 0.1,
                      None) for _ in range(9000))
    pages = api_pages(traces, untimed)
    empty = ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.0" '
             'creator="OpenStreetMap.org" '
             'xmlns="http://www.topografix.com/GPX/1/0">\n</gpx>')
    pages += [empty] * 8                         # pages past the end are empty
    for i, text in enumerate(pages):
        (cache / REGION / f"box_a_p{i:03d}.gpx").write_text(text, "utf-8")
    (cache / REGION / "box_a_ways.json").write_text(
        json.dumps({"elements": fake_ways()}), "utf-8")

    # ---- count the downloads the audit makes
    real_get_page, calls = g.get_page, []

    def counting_get_page(*args, **kwargs):
        calls.append(args[3])
        return real_get_page(*args, **kwargs)

    g.get_page = counting_get_page

    print("Paging (real API order: timestamped points first):")
    _, info, untimed = g.download_box(cache, REGION, BOX, offline=True,
                                      max_pages=40)
    check("20,800 points counted", info["points_total"] == 20800,
          f"({info['points_total']})")
    check("11,800 usable, 9,000 untimed",
          info["points_timed"] == 11800 and info["points_untimed"] == 9000)
    check("untimed points start on page 2, last page is 4",
          info["boundary_page"] == 2 and info["last_page"] == 4)
    check("only 6 pages requested to count everything",
          sorted(set(calls[:6])) == [0, 1, 2, 3, 4, 5], f"(pages {calls})")
    check("untimed sample covers pages 2-4", len(untimed) == 3)
    calls.clear()
    _, cut, _ = g.download_box(cache, REGION, BOX, offline=True,
                               max_pages=1)
    check("counts still exact when cut at 1 page",
          cut["points_timed"] == 11800 and cut["points_total"] == 20800
          and not cut["usable_part_complete"], f"(pages {calls})")
    g.get_page = real_get_page

    # ---- run the REAL audit code, offline
    out_dir = Path("results")
    summary, table = g.audit_region(REGION, [BOX], cache_dir=cache,
                                    out_dir=out_dir, offline=True)

    print("\nChecking the answers against the known truth:")
    d = g.haversine_m(44.0, -71.0, 45.0, -71.0) / 1000
    check("1 degree of latitude is about 111.2 km", abs(d - 111.2) < 0.2,
          f"({d:.2f} km)")
    check("worked example: 25 m in 30 s = 3.0 km/h",
          abs(25 / 30 * 3.6 - 3.0) < 1e-9)
    t = summary["traces_by_type"]
    check("3 identifiable traces (A, E, F)", t.get("identifiable") == 3, str(t))
    check("3 trackable traces (B, C, D)", t.get("trackable") == 3)
    check("duplicate upload G dropped", t.get("duplicate") == 1)
    check("usable points = 11,800 of 20,800",
          summary["points_usable"] == 11800
          and summary["points_total"] == 20800)

    def row(mask):
        return table[mask].iloc[0]

    a = row(table["url"] == url + "7")
    e = row(table["url"] == url + "5")
    f = row(table["url"] == url + "4")
    track = table[table["type"] == "trackable"].sort_values("n_points")
    c, w, b = (track.iloc[i] for i in range(3))   # 300, 900, 1200 points
    check("split identifiable trace E joined into one",
          (table["url"] == url + "5").sum() == 1 and e["n_points"] == 4000)
    check("split trackable trace B joined into one", b["n_points"] == 1200
          and (table["type"] == "trackable").sum() == 3)
    check("winter hiker D kept (3 hikes, 3 days), not called shuffled",
          w["n_segments"] == 3 and w["n_days"] == 3, f"(n_days={w['n_days']})")
    check("winter hiker D near 2.5 km/h", 2.2 <= w["median_speed_trail"] <= 2.8,
          f"({w['median_speed_trail']:.2f})")
    check("10-per-second car reads ~40 km/h, not walking pace",
          38 <= f["median_speed_moving"] <= 42,
          f"({f['median_speed_moving']:.1f})")
    check("car is on the road, not a trail",
          f["share_road"] > 0.9 and f["trail_moving_min"] == 0)
    check("walker A near 4 km/h", 3.6 <= a["median_speed_trail"] <= 4.5,
          f"({a['median_speed_trail']:.2f})")
    check("walker B near 3 km/h", 2.7 <= b["median_speed_trail"] <= 3.4,
          f"({b['median_speed_trail']:.2f})")
    check("cyclist near 16 km/h", 15.0 <= c["median_speed_trail"] <= 17.0,
          f"({c['median_speed_trail']:.2f})")
    check("noise-free walker E is exactly 3.5 km/h",
          abs(e["median_speed_trail"] - 3.5) < 0.02,
          f"({e['median_speed_trail']:.3f})")
    check("cyclist is cycling-like, on a bicycle-permitted trail",
          c["band_trail"] == "cycling-like"
          and c["main_permission"] == "bicycle-permitted")
    check("walker A is on a foot-only trail",
          a["main_permission"] == "foot-only")

    # ---- the interesting part: how much of walker A's stop was caught?
    true_stop = 120 * 5 / (600 * 5)                    # 10 of 50 minutes
    crude, window = a["frac_time_stopped"], a["frac_time_stopped_window"]
    print(f"\n  Walker A really stopped for {100 * true_stop:.0f}% of the hike.")
    print(f"  The crude 0.5 km/h rule caught {100 * crude:.1f}%.")
    print(f"  The draft 60 s / 10 m rule caught {100 * window:.1f}%.")
    print("  Why: GPS points wobble even when you stand still, so a standing")
    print("  hiker looks like they move at 1-3 km/h -- but the wobble never")
    print("  carries them 10 m away. (Plan sec. 8: speed + minimum duration.)")
    check("crude rule misses most of the stop", crude < 0.10)
    check("draft rule catches the stop", 0.17 <= window <= 0.24)

    lat, lon, ts, _ = g.clean_segment(walker_a)
    k = g.thin(ts)
    speed, dt, _ = g.steps(lat[k], lon[k], ts[k])
    win = g.window_stops(lat[k], lon[k], ts[k], dt)
    minutes = (ts[k][1:] - ts[0]) / 60
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axvspan(20, 30, color="#FAC775", alpha=0.6,
               label="real stop (standing still)")
    ax.plot(minutes, speed, lw=0.9, color="#185FA5",
            label="speed over 10-s steps")
    ax.axhline(g.STOP_SPEED_KMH, color="#D85A30", ls="--", lw=1.6,
               label=f"0.5 km/h rule (caught {100 * crude:.0f}%)")
    ax.fill_between(minutes, 0, 0.25, where=win, color="#1D9E75",
                    label=f"60 s / 10 m rule (caught {100 * window:.0f}%)")
    ax.set_xlabel("minutes into hike")
    ax.set_ylabel("speed (km/h)")
    ax.set_ylim(0, 7)
    ax.set_title("FAKE DATA: during the real stop GPS wobble reads ~1 km/h, so "
                 "the 0.5 km/h rule\nmisses most of it; a minimum-duration "
                 "rule catches it")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / REGION / "stop_filter_problem.png", dpi=150)
    plt.close(fig)

    # ---- second lesson: GPS wobble makes slow walkers look fast
    print("\n  Same 3.5 km/h walker, same 1.5 m GPS wobble, different "
          "recording intervals:")
    intervals = [1, 2, 3, 5, 10, 30, 60]
    p2p, ten = [], []
    for every in intervals:
        pts = walk(44.0, -71.0, 3.5, every, int(3600 / every) + 1)
        p2p.append(float(np.median(g.segment_speeds(pts)[0])))
        ten.append(float(np.median(g.segment_speeds(pts, g.MIN_STEP_S)[0])))
        print(f"    GPS every {every:2d} s -> point to point {p2p[-1]:5.2f} km/h"
              f" ({100 * (p2p[-1] / 3.5 - 1):+4.0f}%), 10-s steps "
              f"{ten[-1]:5.2f} km/h ({100 * (ten[-1] / 3.5 - 1):+4.0f}%)")
    print("  -> Point-to-point speed is inflated when each step is about as")
    print("     small as the wobble. Version 2 measures over 10-s steps; T1")
    print("     will use fixed-length trail segments (plan sec. 8: 25-50 m).")
    check("bias shrinks as interval grows", p2p[0] > p2p[-1])
    check("60 s interval is within 3% of the truth",
          abs(p2p[-1] / 3.5 - 1) < 0.03, f"({p2p[-1]:.2f})")
    check("10-s steps keep a 1-s recording within 10% of the truth",
          abs(ten[0] / 3.5 - 1) < 0.10, f"({ten[0]:.2f})")

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(intervals, p2p, "o-", color="#185FA5", lw=2,
            label="point to point (version 1)")
    ax.plot(intervals, ten, "s-", color="#D85A30", lw=2,
            label="steps of 10 s or more (version 2)")
    ax.axhline(3.5, color="#1D9E75", ls="--", lw=1.6,
               label="true speed (3.5 km/h)")
    ax.set_xscale("log")
    ax.set_xticks(intervals)
    ax.set_xticklabels([str(i) for i in intervals])
    ax.set_xlabel("seconds between GPS points")
    ax.set_ylabel("measured median speed (km/h)")
    ax.set_title("FAKE DATA: the more often GPS records, the more its\n"
                 "wobble inflates the speed of a slow walker")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / REGION / "speed_bias_vs_interval.png", dpi=150)
    plt.close(fig)

    shutil.rmtree(tmp)
    print(f"\n  plots saved in {out_dir / REGION}/")
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
