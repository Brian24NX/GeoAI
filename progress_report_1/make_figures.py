"""Figures for Progress Report #1 (run from travel-speed-gate1/)."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import gate1_audit as g

OUT = Path("../progress_report_1/figures")
plt.rcParams.update({"font.family": "serif", "font.size": 7.5,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6,
                     "ytick.major.width": 0.6})

# ---- Figure 1: one real hike over the OSM trail network
region, box = "white_mountains", g.REGIONS["white_mountains"][0]
texts, info, _ = g.download_box("cache", region, box, offline=True)
traces = g.timed_traces(texts, info)
pick = [t for t in traces if g.classify(t) in g.USABLE
        and len(g.all_points(t)) == 4813][0]
ways = g.get_ways("cache", region, box, offline=True)
m = g.WayMatcher(ways, box)

fig, ax = plt.subplots(figsize=(3.3, 2.5))
for w in ways:
    c = g.way_class(w.get("tags", {}))
    geom = [p for p in w.get("geometry") or [] if p]
    if len(geom) < 2 or c not in ("trail", "road", "rail"):
        continue
    xs, ys = [p["lon"] for p in geom], [p["lat"] for p in geom]
    style = {"trail": dict(color="#9a9a9a", lw=0.5),
             "road": dict(color="#d9c7a7", lw=1.2),
             "rail": dict(color="#b07fd6", lw=0.8, ls="--")}[c]
    ax.plot(xs, ys, zorder=1, **style)
lat, lon, t, _ = g.clean_segment(pick["segments"][0])
k = g.thin(t)
la, lo, tt = lat[k], lon[k], t[k]
v, dt, dist = g.steps(la, lo, tt)
win = g.window_stops(la, lo, tt, dt)
seg = np.stack([np.c_[lo[:-1], la[:-1]], np.c_[lo[1:], la[1:]]], axis=1)
moving = ~win & (v >= g.STOP_SPEED_KMH) & (dt <= g.MAX_GAP_S)
lc = LineCollection(seg[moving], cmap="plasma", norm=plt.Normalize(0, 5),
                    linewidths=1.6, zorder=3)
lc.set_array(np.clip(v[moving], 0, 5))
ax.add_collection(lc)
ax.scatter(lo[:-1][win], la[:-1][win], s=4, color="#1D9E75", zorder=4,
           label="stopped (60 s / 10 m rule)")
ax.plot(lo[0], la[0], marker="^", color="k", ms=5, zorder=5, ls="",
        label="start")
cb = fig.colorbar(lc, ax=ax, orientation="horizontal", fraction=0.05,
                  pad=0.17, aspect=40)
cb.set_label("speed over 10-s steps (km/h)", fontsize=6.5)
cb.ax.tick_params(labelsize=6)
pad = 0.006
ax.set_xlim(lo.min() - pad, lo.max() + pad)
ax.set_ylim(la.min() - pad, la.max() + pad)
ax.set_aspect(1 / np.cos(np.radians(la.mean())))
ax.tick_params(labelsize=6)
ax.set_xlabel("longitude", fontsize=7)
ax.set_ylabel("latitude", fontsize=7)
ax.plot([], [], color="#9a9a9a", lw=0.8, label="OSM trails")
ax.plot([], [], color="#d9c7a7", lw=1.4, label="OSM roads")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4,
          fontsize=5.6, frameon=False, handlelength=1.4, columnspacing=0.8)
fig.tight_layout(pad=0.3)
fig.savefig(OUT / "fig_example_trace.pdf", bbox_inches="tight", pad_inches=0.02)
fig.savefig(OUT / "fig_example_trace.png", dpi=200, bbox_inches="tight", pad_inches=0.02)
plt.close(fig)
hrs = (t[-1] - t[0]) / 3600
print(f"example trace: {len(g.all_points(pick))} pts, {hrs:.1f} h, "
      f"{dist.sum()/1000:.1f} km, median moving "
      f"{g.wmedian(v[moving], dt[moving]):.2f} km/h, "
      f"stopped {100*dt[win].sum()/dt[dt<=g.MAX_GAP_S].sum():.0f}%, "
      f"first point {pick['segments'][0][0]}")

# ---- Figure 2: first-look slope-speed curves vs Tobler
df = pd.read_csv("results/first_look_chunks.csv")
edges = np.arange(-0.41, 0.4101, 0.02)
mid = (edges[:-1] + edges[1:]) / 2
fig, ax = plt.subplots(figsize=(3.3, 2.15))
s = np.linspace(-0.4, 0.4, 400)
ax.plot(100 * s, 6 * np.exp(-3.5 * np.abs(s + 0.05)), "k--", lw=1.2,
        label="Tobler (1993)")
names = {"white_mountains": "White Mtns", "cascades": "Cascades",
         "front_range": "Front Range"}
colors = {"white_mountains": "#185FA5", "cascades": "#1D9E75",
          "front_range": "#D85A30"}
for r in ["white_mountains", "cascades", "front_range"]:
    sub = df[df.region == r]
    idx = np.digitize(sub.slope, edges) - 1
    pts = [(mid[b], sub.speed_kmh[idx == b].median()) for b in range(len(mid))
           if (idx == b).sum() >= 20]
    x, y = zip(*pts)
    ax.plot(100 * np.array(x), y, "o-", ms=2.2, lw=1, color=colors[r],
            label=f"{names[r]} ({sub.trace.nunique()} traces)")
ax.set_xlabel("slope along direction of travel (%), + = uphill")
ax.set_ylabel("median speed (km/h)")
ax.set_ylim(0, 6.5)
ax.set_xlim(-42, 42)
ax.grid(alpha=0.25, lw=0.4)
ax.legend(fontsize=6, loc="upper right", frameon=False)
fig.tight_layout(pad=0.3)
fig.savefig(OUT / "fig_slope_speed.pdf", bbox_inches="tight", pad_inches=0.02)
fig.savefig(OUT / "fig_slope_speed.png", dpi=200)
plt.close(fig)
print("chunks per region:", df.region.value_counts().to_dict())
