#!/usr/bin/env python3
"""
Self-test for gate1_audit.py using FAKE data. No internet needed.

It writes fake OSM-style GPX pages into a temporary cache folder, runs the
real audit code on them in offline mode, and checks the answers.

The fake traces (we know the true answer for each one):
  A. identifiable walker, 4 km/h, GPS every 5 s, with a 10-minute stop
  B. trackable walker, 3 km/h, GPS every 10 s
  C. trackable cyclist, 16 km/h, GPS every 5 s
  D. "public" blob: 1,000 points sorted by latitude, no times (unusable)
  E. identifiable walker, 3.5 km/h, split across two pages (tests merging)

Run:  python selftest.py      -> should end with "ALL CHECKS PASSED"
"""

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
START = datetime(2025, 7, 12, 9, 0, 0, tzinfo=timezone.utc)


def walk(lat, lon, speed_kmh, every_s, n, noise_m=1.5, stop=None):
    """Fake GPS track heading north. stop=(first_index, n_points) stands still.

    Each point gets a little random GPS error (noise_m), like a real phone.
    """
    pts, v = [], speed_kmh / 3.6
    for i in range(n):
        standing = stop is not None and stop[0] <= i < stop[0] + stop[1]
        if i > 0 and not standing:
            lat += v * every_s / M_PER_DEG_LAT
        jitter_lat = rng.normal(0, noise_m) / M_PER_DEG_LAT
        jitter_lon = rng.normal(0, noise_m) / (
            M_PER_DEG_LAT * np.cos(np.radians(lat)))
        when = START + timedelta(seconds=i * every_s)
        pts.append((lat + jitter_lat, lon + jitter_lon, when))
    return pts


def gpx(traces):
    """Write traces in the same GPX 1.0 format the OSM API returns."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gpx version="1.0" creator="OpenStreetMap.org" '
           'xmlns="http://www.topografix.com/GPX/1/0">']
    for tr in traces:
        out.append("<trk>")
        for key in ("name", "desc", "url"):
            if tr.get(key):
                out.append(f"<{key}>{tr[key]}</{key}>")
        out.append("<trkseg>")
        for lat, lon, when in tr["points"]:
            if when is None:
                out.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}"/>')
            else:
                out.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}">'
                           f'<time>{when:%Y-%m-%dT%H:%M:%SZ}</time></trkpt>')
        out.append("</trkseg></trk>")
    out.append("</gpx>")
    return "\n".join(out)


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label} {detail}")
    if not condition:
        raise SystemExit("SELF-TEST FAILED")


def main():
    region = "SYNTHETIC_selftest"
    box_a = ("box_a", -71.40, 44.20, -71.30, 44.30)
    box_b = ("box_b", -71.60, 44.10, -71.50, 44.20)
    tmp = Path(tempfile.mkdtemp())
    cache = tmp / "cache"

    # ---- build the fake traces (true answers known)
    walker_a = walk(44.21, -71.35, 4.0, 5, 600, stop=(240, 120))  # 10-min stop
    walker_b = walk(44.22, -71.36, 3.0, 10, 400)
    cyclist = walk(44.23, -71.34, 16.0, 5, 300)
    blob = sorted([(44.20 + rng.random() * 0.1, -71.40 + rng.random() * 0.1,
                    None) for _ in range(1000)])
    # no GPS noise on E, so its speed must come out EXACTLY 3.5 km/h
    walker_e = walk(44.12, -71.55, 3.5, 3, 6000, noise_m=0)  # 2 pages

    page_a = gpx([
        {"name": "saturday_hike.gpx", "desc": "Fake identifiable walk",
         "url": "https://api.openstreetmap.org/user/test/traces/1",
         "points": walker_a},
        {"points": walker_b},             # trackable: no name/url
        {"points": cyclist},              # trackable cyclist
        {"points": blob},                 # public: shuffled, no times
    ])
    url_e = "https://api.openstreetmap.org/user/test/traces/2"
    page_b0 = gpx([{"name": "long_walk.gpx", "url": url_e,
                    "points": walker_e[:5000]}])   # full page -> fetch next
    page_b1 = gpx([{"name": "long_walk.gpx", "url": url_e,
                    "points": walker_e[5000:]}])

    (cache / region).mkdir(parents=True)
    (cache / region / "box_a_p000.gpx").write_text(page_a, encoding="utf-8")
    (cache / region / "box_b_p000.gpx").write_text(page_b0, encoding="utf-8")
    (cache / region / "box_b_p001.gpx").write_text(page_b1, encoding="utf-8")

    # ---- run the REAL audit code, offline
    out_dir = Path("results")
    summary, table = g.audit_region(region, [box_a, box_b], cache_dir=cache,
                                    out_dir=out_dir, offline=True)

    print("\nChecking the answers against the known truth:")
    d = g.haversine_m(44.0, -71.0, 45.0, -71.0) / 1000
    check("1 degree of latitude is about 111.2 km", abs(d - 111.2) < 0.2,
          f"({d:.2f} km)")
    check("worked example: 25 m in 30 s = 3.0 km/h",
          abs(25 / 30 * 3.6 - 3.0) < 1e-9)

    t = summary["by_type"]
    check("2 identifiable traces", t.get("identifiable") == 2, str(t))
    check("2 trackable traces", t.get("trackable") == 2)
    check("1 unordered (shuffled) trace", t.get("unordered") == 1)
    check("usable points = 7,300 of 8,300",
          summary["points_usable"] == 7300 and summary["points_total"] == 8300)

    merged = table[table["url"] == url_e]
    check("split trace merged across pages into one",
          len(merged) == 1 and int(merged["n_points"].iloc[0]) == 6000)

    def med(mask):
        return float(table.loc[mask, "median_speed_moving"].iloc[0])

    urls = table["url"]
    v_a = med(urls == "https://api.openstreetmap.org/user/test/traces/1")
    v_e = med(urls == url_e)
    track = table[table["type"] == "trackable"].sort_values(
        "median_speed_moving")
    v_b, v_c = track["median_speed_moving"].tolist()
    check("walker A near 4 km/h", 3.5 <= v_a <= 4.8, f"({v_a:.2f})")
    check("walker B near 3 km/h", 2.6 <= v_b <= 3.6, f"({v_b:.2f})")
    check("cyclist near 16 km/h", 15.0 <= v_c <= 17.0, f"({v_c:.2f})")
    check("noise-free walker E is exactly 3.5 km/h", abs(v_e - 3.5) < 0.02,
          f"({v_e:.3f})")
    check("cyclist lands in cycling-like band",
          track["band"].tolist() == ["walking-like", "cycling-like"])

    # ---- the interesting part: how much of walker A's stop was caught?
    speed, dt, _ = g.segment_speeds(walker_a)
    minutes = np.cumsum(dt) / 60
    true_stop = 120 * 5 / (600 * 5) * 100          # 10 of 50 minutes = 20%
    caught = float(table.loc[urls == "https://api.openstreetmap.org/user/"
                             "test/traces/1", "frac_time_stopped"].iloc[0])
    print(f"\n  Walker A really stopped for {true_stop:.0f}% of the hike.")
    print(f"  The 0.5 km/h filter caught only {100 * caught:.1f}%.")
    print("  Why: GPS points wobble even when you stand still, so a")
    print("  standing hiker looks like they move at 1-3 km/h.")
    print("  -> Real T1 cleaning needs speed + minimum duration (plan sec. 8).")

    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.axvspan(20, 30, color="#FAC775", alpha=0.6, label="real stop (standing still)")
    ax.plot(minutes, speed, lw=0.8, color="#185FA5", label="speed between GPS points")
    ax.axhline(g.STOP_SPEED_KMH, color="#D85A30", ls="--", lw=1.6,
               label="0.5 km/h stop filter")
    ax.set_xlabel("minutes into hike")
    ax.set_ylabel("speed (km/h)")
    ax.set_ylim(0, 9)
    ax.set_title("FAKE DATA: during the real stop, GPS wobble reads 1-3 km/h,\n"
                 "so almost none of it falls below the 0.5 km/h filter")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out_dir / region / "stop_filter_problem.png", dpi=150)
    plt.close(fig)

    # ---- second lesson: GPS wobble makes slow walkers look fast
    print("\n  Same 3.5 km/h walker, same 1.5 m GPS wobble, different "
          "recording intervals:")
    intervals = [1, 2, 3, 5, 10, 30, 60]
    measured = []
    for every in intervals:
        pts = walk(44.0, -71.0, 3.5, every, int(3600 / every) + 1)
        v, _, _ = g.segment_speeds(pts)
        measured.append(float(np.median(v)))
        print(f"    GPS every {every:2d} s -> measured {measured[-1]:5.2f} km/h"
              f"  ({100 * (measured[-1] / 3.5 - 1):+5.0f}%)")
    print("  -> Point-to-point speed is inflated when each step is about as")
    print("     small as the wobble. T1 avoids this by measuring speed over")
    print("     fixed-length trail segments (plan sec. 8: 25-50 m).")
    check("bias shrinks as interval grows", measured[0] > measured[-1])
    check("60 s interval is within 3% of the truth",
          abs(measured[-1] / 3.5 - 1) < 0.03, f"({measured[-1]:.2f})")

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(intervals, measured, "o-", color="#185FA5", lw=2,
            label="measured median speed")
    ax.axhline(3.5, color="#1D9E75", ls="--", lw=1.6,
               label="true speed (3.5 km/h)")
    ax.set_xscale("log")
    ax.set_xticks(intervals)
    ax.set_xticklabels([str(i) for i in intervals])
    ax.set_xlabel("seconds between GPS points")
    ax.set_ylabel("speed (km/h)")
    ax.set_title("FAKE DATA: the more often GPS records, the more its\n"
                 "wobble inflates the speed of a slow walker")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / region / "speed_bias_vs_interval.png", dpi=150)
    plt.close(fig)

    shutil.rmtree(tmp)
    print(f"\n  plots saved in {out_dir / region}/")
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
