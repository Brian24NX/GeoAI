#!/usr/bin/env python3
"""
FIRST LOOK at the slope-speed curve. This previews the plan's week-9
diagnostic (sec. 9) and T4. Run it after gate1_audit.py.

This is NOT the real analysis. There is no HMM map-matching, no fixed-length
trail segments and no tuned stop rule yet (those are T1). It exists to answer
one question early: can these traces answer Question 1 at all?

For every region it:
  1. re-reads the cached GPS pages and OSM trails (no OSM downloads);
  2. cuts each usable trace into ~50 m chunks of continuous, moving, on-trail
     travel (both stop rules applied; any gap or stop ends a chunk);
  3. snaps each chunk's two ends to the nearest trail point and reads their
     elevation from a 5 m USGS 3DEP DEM (downloaded once per box, cached);
  4. slope = rise / distance in the direction of travel (+ = uphill);
  5. plots the median speed per 2% slope bin against Tobler's curve, plus the
     log-speed diagnostic. If Tobler is right, log(speed) plotted against
     |slope + 0.05| is a straight line with slope -3.5.

Run:  python first_look_slope.py
Needs: the cache from gate1_audit.py, plus tifffile
"""

import json
import logging
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gate1_audit as g

DEM_URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/"
           "3DEPElevation/ImageServer/exportImage")
AGENT = {"User-Agent": "WashU-MVRL-travel-speed/0.2 (research)"}
DEM_PIXEL_M = 5.0      # DEM grid spacing requested from USGS
CHUNK_M = 50.0         # speed and slope are measured over ~50 m of travel
MAX_ABS_SLOPE = 0.6    # steeper than 60% over 50 m = probably a DEM or GPS error
MIN_BIN = 20           # plot a slope bin only if it has this many chunks
WALKER_MAX_KMH = 7.0   # walkers only: drop traces whose median chunk speed is
                       #   higher (cyclists, runners, skiers)
MIN_CHUNKS = 6         # and traces with less than ~300 m of usable trail
COLORS = {"white_mountains": "#185FA5", "cascades": "#1D9E75",
          "front_range": "#D85A30"}


def tobler(s):
    """Tobler (1993): km/h from slope as rise/run (0.10 = 10% grade)."""
    return 6 * np.exp(-3.5 * np.abs(s + 0.05))


# ------------------------------------------------------------------ the DEM
def dem(cache, name, extent):
    """5 m elevation grid (m) over extent=(w, s, e, n), cached on disk.

    Returns (array, exact extent). Row 0 of the array is the north edge.
    """
    import requests
    import tifffile
    logging.getLogger("tifffile").setLevel(logging.ERROR)
    tif, meta = cache / f"{name}_dem5m.tif", cache / f"{name}_dem5m.json"
    if not tif.exists():
        w, s, e, n = extent
        kx = 111_320.0 * math.cos(math.radians((s + n) / 2))
        width = min(8000, math.ceil((e - w) * kx / DEM_PIXEL_M))
        height = min(8000, math.ceil((n - s) * 111_132.0 / DEM_PIXEL_M))
        params = {"bbox": f"{w},{s},{e},{n}", "bboxSR": 4326,
                  "imageSR": 4326, "size": f"{width},{height}",
                  "format": "tiff", "pixelType": "F32", "noData": -9999,
                  "interpolation": "RSP_BilinearInterpolation",
                  "adjustAspectRatio": "false", "f": "json"}
        for attempt in range(3):
            try:
                r = requests.get(DEM_URL, params=params, headers=AGENT,
                                 timeout=300)
                r.raise_for_status()
                info = r.json()
                img = requests.get(info["href"], headers=AGENT, timeout=600)
                img.raise_for_status()
                break
            except (requests.RequestException, KeyError):
                if attempt == 2:
                    raise
                time.sleep(20 * (attempt + 1))
        cache.mkdir(parents=True, exist_ok=True)
        tif.write_bytes(img.content)
        meta.write_text(json.dumps(info["extent"]))
        time.sleep(1.0)
    a = tifffile.imread(tif).astype(float)
    a[a < -1000] = np.nan
    ext = json.loads(meta.read_text())
    return a, (ext["xmin"], ext["ymin"], ext["xmax"], ext["ymax"])


def sample(a, extent, lat, lon):
    """Bilinear elevation at (lat, lon). Row 0 is north, column 0 is west."""
    w, s, e, n = extent
    rows, cols = a.shape
    x = (np.asarray(lon) - w) / (e - w) * cols - 0.5
    y = (n - np.asarray(lat)) / (n - s) * rows - 0.5
    x0 = np.clip(np.floor(x).astype(int), 0, cols - 2)
    y0 = np.clip(np.floor(y).astype(int), 0, rows - 2)
    fx, fy = np.clip(x - x0, 0, 1), np.clip(y - y0, 0, 1)
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy)
            + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy)


def sign_check():
    """Plan sec. 8: "write a test for the sign convention".

    A fake DEM that rises 10% to the north, and a walker heading north,
    must give slope +0.10 (uphill = positive). Heading south must give -0.10.
    """
    ext = (-71.0, 44.0, -70.99, 44.01)
    rows, cols = 200, 160
    north_m = (rows - 1 - np.arange(rows) + 0.5) / rows * 0.01 * 111_195.0
    a = np.repeat((1000 + 0.10 * north_m)[:, None], cols, axis=1)
    lat, lon = np.array([44.002, 44.008]), np.array([-70.995, -70.995])
    z = sample(a, ext, lat, lon)
    run = g.haversine_m(lat[0], lon[0], lat[1], lon[1])
    up, down = (z[1] - z[0]) / run, (z[0] - z[1]) / run
    assert abs(up - 0.10) < 0.005 and abs(down + 0.10) < 0.005, (up, down)
    print(f"  sign check passed: heading uphill reads {up:+.3f}, "
          f"downhill {down:+.3f}")


# ------------------------------------------------------------------- chunks
def chunks(trace, matcher, a, ext):
    """~50 m pieces of continuous, moving, on-trail travel in one trace."""
    out = []
    for seg in trace["segments"]:
        lat, lon, t, _ = g.clean_segment(seg)
        k = g.thin(t)
        if len(k) < 2:
            continue
        la, lo, tt = lat[k], lon[k], t[k]
        v, dt, dist = g.steps(la, lo, tt)
        win = g.window_stops(la, lo, tt, dt)
        way, sla, slo = matcher.snap(la, lo)
        trail = matcher.cls[way] == g.TRAIL
        ok = ((dt <= g.MAX_GAP_S) & (v <= g.FAST_SPEED_KMH)
              & (v >= g.STOP_SPEED_KMH) & ~win & trail[:-1] & trail[1:])
        pieces, i, n = [], 0, len(v)
        while i < n:
            if not ok[i]:
                i += 1
                continue
            j, d_sum, t_sum = i, 0.0, 0.0
            while j < n and ok[j] and d_sum < CHUNK_M:
                d_sum, t_sum, j = d_sum + dist[j], t_sum + dt[j], j + 1
            if d_sum >= CHUNK_M:
                pieces.append((i, j, d_sum, t_sum))
            i = j
        if not pieces:
            continue
        ii = np.array([p[0] for p in pieces])
        jj = np.array([p[1] for p in pieces])
        z0, z1 = sample(a, ext, sla[ii], slo[ii]), sample(a, ext, sla[jj],
                                                           slo[jj])
        for (i, j, d_sum, t_sum), za, zb in zip(pieces, z0, z1):
            out.append({"slope": (zb - za) / d_sum,
                        "speed_kmh": d_sum / t_sum * 3.6,
                        "dist_m": d_sum, "time_s": t_sum, "t0": tt[i],
                        "elev_m": za, "interval_s": float(np.median(dt))})
    return out


def collect(cache, regions, max_pages=150):
    rows = []
    for region in regions:
        boxes = g.REGIONS[region]
        for box in boxes:
            name = box[0]
            texts, info, _ = g.download_box(cache, region, box,
                                            offline=True,
                                            max_pages=max_pages)
            ways = g.get_ways(cache, region, box, offline=True)
            if not texts or not ways:
                print(f"  {name}: skipped (run gate1_audit.py first)")
                continue
            matcher = g.WayMatcher(ways, box)
            trail_xy = matcher.tree.data[matcher.cls[matcher.owner]
                                         == g.TRAIL]
            lon_t, lat_t = trail_xy[:, 0] / matcher.kx, trail_xy[:, 1] / \
                matcher.ky
            pad = 0.003
            extent = (max(box[1], lon_t.min()) - pad,
                      max(box[2], lat_t.min()) - pad,
                      min(box[3], lon_t.max()) + pad,
                      min(box[4], lat_t.max()) + pad)
            a, ext = dem(cache / "layers", name, extent)
            seen, n_before = set(), len(rows)
            for k, trace in enumerate(g.timed_traces(texts, info)):
                if g.classify(trace) not in g.USABLE:
                    continue
                fp = g.fingerprint(trace)
                if fp in seen:
                    continue
                seen.add(fp)
                for c in chunks(trace, matcher, a, ext):
                    c.update(region=region, box=name, trace=f"{name}#{k}")
                    rows.append(c)
            print(f"  {name:28s} {len(rows) - n_before:6d} chunks of "
                  f"~{CHUNK_M:.0f} m")
    df = pd.DataFrame(rows)
    df = df[np.isfinite(df["slope"]) & (df["slope"].abs() <= MAX_ABS_SLOPE)]
    per_trace = df.groupby("trace")["speed_kmh"].agg(["median", "size"])
    keep = per_trace[(per_trace["median"] <= WALKER_MAX_KMH)
                     & (per_trace["size"] >= MIN_CHUNKS)].index
    print(f"  walkers only: kept {len(keep)} of {len(per_trace)} traces "
          f"(median <= {WALKER_MAX_KMH:.0f} km/h, >= {MIN_CHUNKS} chunks)")
    return df[df["trace"].isin(keep)]


# ---------------------------------------------------------------- fit + plot
def fit_tobler_form(df):
    """Least squares in log space: ln v = ln v0 - k |s + s0|, s0 by grid."""
    s, y = df["slope"].to_numpy(), np.log(df["speed_kmh"].to_numpy())
    best = None
    for s0 in np.arange(-0.10, 0.20001, 0.005):
        x = np.abs(s + s0)
        A = np.c_[np.ones_like(x), -x]
        coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = float(np.sum((A @ coef - y) ** 2))
        if best is None or sse < best[0]:
            best = (sse, s0, coef)
    sse, s0, (ln_v0, k) = best
    return {"v0_kmh": float(np.exp(ln_v0)), "k": float(k), "s0": float(s0),
            "peak_slope_pct": float(-100 * s0), "n_chunks": int(len(df)),
            "n_traces": int(df["trace"].nunique())}


def binned(df, edges):
    mid = (edges[:-1] + edges[1:]) / 2
    idx = np.digitize(df["slope"], edges) - 1
    out = []
    for b in range(len(mid)):
        v = df["speed_kmh"][idx == b]
        if len(v) >= MIN_BIN:
            out.append((mid[b], v.median(), v.quantile(0.25),
                        v.quantile(0.75), len(v)))
    return pd.DataFrame(out, columns=["slope", "median", "q25", "q75", "n"])


def plot(df, fits, path):
    edges = np.arange(-0.41, 0.4101, 0.02)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
    s = np.linspace(-0.4, 0.4, 400)
    ax1.plot(100 * s, tobler(s), "k--", lw=1.8, label="Tobler (1993)")
    for region, sub in df.groupby("region"):
        b = binned(sub, edges)
        c = COLORS.get(region, "gray")
        f = fits[region]
        ax1.fill_between(100 * b["slope"], b["q25"], b["q75"], color=c,
                         alpha=0.15)
        ax1.plot(100 * b["slope"], b["median"], "o-", color=c, ms=4,
                 label=f"{region} ({f['n_traces']} traces, "
                       f"{f['n_chunks']:,} chunks)")
    ax1.set_xlabel("slope along direction of travel (%)   "
                   "(+ = uphill)")
    ax1.set_ylabel("speed (km/h)")
    ax1.set_ylim(0, 7)
    ax1.set_title("Median speed per 2% slope bin (band: middle 50%)",
                  fontsize=10)
    ax1.legend(fontsize=8)

    x = np.linspace(0, 0.45, 50)
    ax2.plot(x, np.log(6) - 3.5 * x, "k--", lw=1.8,
             label="Tobler: ln 6 - 3.5 |s + 0.05|")
    for region, sub in df.groupby("region"):
        c, f = COLORS.get(region, "gray"), fits[region]
        xx = np.abs(sub["slope"] + 0.05)
        e2 = np.arange(0, 0.46, 0.02)
        idx = np.digitize(xx, e2) - 1
        for side, mask, marker, fill in [
                ("uphill side", sub["slope"] > -0.05, "o", c),
                ("downhill side", sub["slope"] <= -0.05, "s", "white")]:
            pts = [((e2[b] + e2[b + 1]) / 2,
                    np.log(sub["speed_kmh"][(idx == b) & mask]).median())
                   for b in range(len(e2) - 1)
                   if ((idx == b) & mask).sum() >= MIN_BIN]
            if pts:
                px, py = zip(*pts)
                ax2.plot(px, py, marker, color=c, mfc=fill, ms=5, ls="",
                         label=f"{region}, {side}")
        ax2.plot(x, np.log(f["v0_kmh"]) - f["k"] * x, "-", color=c, lw=1,
                 alpha=0.7)
    ax2.set_xlabel("|slope + 0.05|")
    ax2.set_ylabel("ln(speed in km/h)")
    ax2.set_title("Plan sec. 9 diagnostic: a straight line if Tobler's form "
                  "holds", fontsize=10)
    ax2.legend(fontsize=7, ncol=2)
    fig.suptitle("FIRST LOOK, not validated: walkers on OSM trails (real OSM "
                 "traces), 50 m chunks, 5 m USGS DEM", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="First look at slope vs speed")
    ap.add_argument("--region", default="all",
                    choices=sorted(g.REGIONS) + ["all"])
    ap.add_argument("--out-dir", default="results")
    args = ap.parse_args()
    regions = list(g.REGIONS) if args.region == "all" else [args.region]
    sign_check()
    cache, out = Path("cache"), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = collect(cache, regions)
    df.to_csv(out / "first_look_chunks.csv", index=False)
    fits = {r: fit_tobler_form(sub) for r, sub in df.groupby("region")}
    print("\nFitted ln v = ln v0 - k |s + s0|   (Tobler: v0 = 6, k = 3.5, "
          "peak at -5%)")
    for region, f in fits.items():
        print(f"  {region:16s} v0 = {f['v0_kmh']:.2f} km/h  k = {f['k']:.2f}"
              f"  fastest at {f['peak_slope_pct']:+.1f}% slope   "
              f"({f['n_traces']} traces, {f['n_chunks']:,} chunks)")
    with open(out / "first_look_fits.json", "w") as fh:
        json.dump(fits, fh, indent=2)
    plot(df, fits, out / "first_look_slope_speed.png")
    print(f"\nsaved: {out}/first_look_slope_speed.png, first_look_fits.json,"
          " first_look_chunks.csv")


if __name__ == "__main__":
    main()
