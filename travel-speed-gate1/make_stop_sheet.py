#!/usr/bin/env python3
"""
Make the stop-checking sheet (T1, semester plan sec. 8).

Plan sec. 8: "Pick a rule (speed threshold plus minimum duration), apply it
consistently, and report the fraction of time you dropped. This one choice
will move your headline numbers more than any model change." To pick the rule
honestly we need a person to look at real cases.

This script picks 20 short episodes from real White Mountains hikes (the
Gate 1 sample, already cached) where a stop is ambiguous:
  W  the draft rule (60 s that end < 10 m from the start) says "stopped"
  C  only the crude rule (< 0.5 km/h) says "stopped": brief pauses
  S  neither rule says "stopped", but the hiker crawled at 0.5-1.2 km/h for
     a minute or more: steep climbing, or a stop hidden by GPS wobble?
It draws each one (speed over time + where the GPS points sat) and writes a
self-contained HTML sheet. The episode type is NOT shown on the sheet, so the
labeling is blind; the answer key is saved separately for scoring.

Output:  ../stop_check/stop_check.html   (open it, click, copy the result)
         ../stop_check/stop_labels.csv   (same cases, if you prefer a table)
         results/stop_check_key.csv      (hidden types, for scoring later)

Run:  python make_stop_sheet.py
"""

import base64
import io
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gate1_audit as g
import first_look_slope as fl

REGION = "white_mountains"
OUT = Path("../stop_check")
KEY = Path("results/stop_check_key.csv")
PICK = {"W": 7, "C": 6, "S": 7}          # 20 cases in total
MAX_PER_TRACE = 2                        # spread cases across many hikes
CONTEXT_S = 180                          # show 3 min before and after
TZ = ZoneInfo("America/New_York")
SEED = 7


def episodes_for_trace(trace_id, trace, matcher):
    """Candidate episodes in one hike (on trails only)."""
    found = []
    for s_idx, seg in enumerate(trace["segments"]):
        lat, lon, t, _ = g.clean_segment(seg)
        k = g.thin(t)
        if len(k) < 10:
            continue
        la, lo, tt = lat[k], lon[k], t[k]
        v, dt, _ = g.steps(la, lo, tt)
        win = g.window_stops(la, lo, tt, dt)
        trail = matcher.cls[matcher.match(la, lo)] == g.TRAIL
        ok = (dt <= g.MAX_GAP_S) & (v <= g.FAST_SPEED_KMH) \
            & trail[:-1] & trail[1:]
        kind = np.full(len(v), "", dtype=object)
        kind[ok & win] = "W"
        kind[ok & ~win & (v < g.STOP_SPEED_KMH)] = "C"
        kind[ok & ~win & (v >= g.STOP_SPEED_KMH) & (v < 1.2)] = "S"
        i = 0
        while i < len(kind):
            if not kind[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(kind) and kind[j + 1] == kind[i]:
                j += 1
            dur = dt[i:j + 1].sum()
            need = {"W": 60, "C": 20, "S": 60}[kind[i]]
            if dur >= need:
                found.append({"trace": trace_id, "segment": s_idx,
                              "kind": kind[i], "t_start": tt[i],
                              "t_end": tt[j + 1], "duration_s": dur})
            i = j + 1
    return found


def local_xy(lat, lon, lat0, lon0):
    kx = 111_320.0 * np.cos(np.radians(lat0))
    return (np.asarray(lon) - lon0) * kx, (np.asarray(lat) - lat0) * 111_132.0


def draw(ep, seg, ways, dem):
    """Speed over time (left) and where the GPS points sat (right)."""
    lat, lon, t, _ = g.clean_segment(seg)
    k = g.thin(t)
    la, lo, tt = lat[k], lon[k], t[k]
    v, dt, _ = g.steps(la, lo, tt)
    t0, t1 = ep["t_start"], ep["t_end"]
    ctx = (t >= t0 - CONTEXT_S) & (t <= t1 + CONTEXT_S)
    inside = (t >= t0) & (t <= t1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.2, 3.1),
                                   gridspec_kw={"width_ratios": [1.35, 1]})
    # left: speed over time
    mid = (tt[:-1] + tt[1:]) / 2
    sel = (mid >= t0 - CONTEXT_S) & (mid <= t1 + CONTEXT_S)
    ax1.step((mid[sel] - t0) / 60, v[sel], where="mid", color="#185FA5",
             lw=1.2)
    ax1.axvspan(0, (t1 - t0) / 60, color="#FAC775", alpha=0.55,
                label="the moment to judge")
    ax1.axhline(g.STOP_SPEED_KMH, color="#D85A30", ls="--", lw=1,
                label="0.5 km/h")
    ax1.set_ylim(0, max(6, np.nanpercentile(v[sel], 95) * 1.1)
                 if sel.any() else 6)
    ax1.set_xlabel("minutes (0 = start of the moment)")
    ax1.set_ylabel("speed over 10-s steps (km/h)")
    ax1.legend(fontsize=7, loc="upper right")
    ax1.grid(alpha=0.25)

    # right: map in meters around the moment
    lat0, lon0 = lat[inside].mean(), lon[inside].mean()
    x, y = local_xy(lat[ctx], lon[ctx], lat0, lon0)
    xi, yi = local_xy(lat[inside], lon[inside], lat0, lon0)
    reach = max(40.0, np.abs(np.r_[xi, yi]).max() * 1.4)
    reach = min(reach, 150.0)
    for way in ways:
        if g.way_class(way.get("tags", {})) not in ("trail", "track",
                                                    "road"):
            continue
        geom = [p for p in way.get("geometry") or [] if p]
        if len(geom) < 2:
            continue
        wx, wy = local_xy([p["lat"] for p in geom], [p["lon"] for p in geom],
                          lat0, lon0)
        if np.min(np.hypot(wx, wy)) < reach * 1.5:
            ax2.plot(wx, wy, color="#bdbdbd", lw=2.2, zorder=1)
    ax2.plot(x, y, color="#9e9e9e", lw=0.6, zorder=2)
    ax2.scatter(x, y, s=4, color="#9e9e9e", zorder=2,
                label="3 min before / after")
    sc = ax2.scatter(xi, yi, s=10, c=(t[inside] - t0) / 60, cmap="viridis",
                     zorder=3, label="during the moment")
    circle = plt.Circle((0, 0), 10, fill=False, ls="--", color="#D85A30",
                        lw=1, zorder=4)
    ax2.add_patch(circle)
    ax2.set_xlim(-reach, reach)
    ax2.set_ylim(-reach, reach)
    ax2.set_aspect("equal")
    ax2.set_xlabel("meters east")
    ax2.set_ylabel("meters north")
    ax2.tick_params(labelsize=7)
    cb = fig.colorbar(sc, ax=ax2, fraction=0.046, pad=0.02)
    cb.set_label("minute", fontsize=7)
    cb.ax.tick_params(labelsize=6)
    ax2.legend(fontsize=6, loc="lower left", framealpha=0.85)
    ax2.set_title("dashed circle = 10 m;  gray band = mapped trail",
                  fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)

    # plain facts
    net = g.haversine_m(lat[inside][0], lon[inside][0], lat[inside][-1],
                        lon[inside][-1])
    path = g.haversine_m(lat[inside][:-1], lon[inside][:-1],
                         lat[inside][1:], lon[inside][1:]).sum()
    spread = np.percentile(np.hypot(xi, yi), 90)
    facts = {
        "duration": f"{int(ep['duration_s'] // 60)} min "
                    f"{int(ep['duration_s'] % 60):02d} s",
        "net_move_m": f"{net:.0f} m",
        "spread_m": f"{spread:.0f} m",
        "gps_every_s": f"{np.median(np.diff(t[ctx])):.0f} s",
        "when": datetime.fromtimestamp(t0, timezone.utc).astimezone(TZ)
        .strftime("%a %d %b %Y, %I:%M %p"),
    }
    if dem is not None:
        a, ext = dem
        zc = fl.sample(a, ext, np.array([lat0]), np.array([lon0]))[0]
        facts["elevation"] = f"{zc:,.0f} m"
        # grade of the trail walked in the 3 min before the moment
        before = (t >= t0 - CONTEXT_S) & (t <= t0)
        if before.sum() >= 3:
            zb = fl.sample(a, ext, lat[before][[0, -1]], lon[before][[0, -1]])
            run = g.haversine_m(lat[before][:-1], lon[before][:-1],
                                lat[before][1:], lon[before][1:]).sum()
            if run > 20:
                facts["grade_before"] = f"{100 * (zb[1] - zb[0]) / run:+.0f}%"
    return base64.b64encode(buf.getvalue()).decode(), facts, \
        {"net_move_m": net, "path_m": path, "spread90_m": spread}


HTML_HEAD = """<!doctype html><html><head><meta charset="utf-8">
<title>Stop-checking sheet</title>
<style>
body{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#222;line-height:1.45}
h1{font-size:22px;margin-bottom:4px}
.lead{background:#f5f7fa;border:1px solid #dde3ea;border-radius:8px;padding:12px 16px;margin:12px 0 20px}
.lead li{margin:3px 0}
.card{border:1px solid #ddd;border-radius:10px;padding:12px 14px;margin:16px 0}
.card h2{font-size:16px;margin:0 0 6px}
.card img{width:100%;max-width:900px;display:block}
.facts{font-size:13px;color:#444;margin:6px 0 8px}
.facts span{display:inline-block;margin-right:16px}
.btns button{font-size:14px;padding:6px 14px;margin-right:8px;border-radius:6px;border:1px solid #bbb;background:#fff;cursor:pointer}
.btns button.on{color:#fff;border-color:transparent}
.btns button.on.Y{background:#1D9E75}.btns button.on.N{background:#185FA5}.btns button.on.Q{background:#888}
#out{width:100%;font-family:monospace;font-size:14px;padding:8px;height:64px}
.sticky{position:sticky;bottom:0;background:#fff;border-top:2px solid #ddd;padding:10px 0}
.count{font-size:13px;color:#555}
</style></head><body>
<h1>Stop-checking sheet: 20 moments from real White Mountains hikes</h1>
<div class="lead">
<b>Your job:</b> for each card, decide whether the hiker <b>actually stopped</b>
(stood or sat still) during the <span style="background:#FAC775">shaded</span> time.
About a minute per card; don't overthink it.
<ul>
<li><b>Stopped</b>: the colored dots on the right <b>bunch up in one small blob</b>,
about the size of the dashed 10 m circle or smaller, and don't make progress along
the trail. Dots jiggling back and forth is GPS noise, not walking.</li>
<li><b>Moving slowly</b>: the colored dots <b>march along the trail</b> in one
direction, even if slowly (steep climbs, scrambles, deep snow). "Net move" well above
~15 m is a strong hint.</li>
<li><b>Can't tell</b>: mixed, confusing, or looks like a GPS glitch.</li>
</ul>
The sheet doesn't say which rule flagged each moment. That's deliberate, so your
judgment is independent. When you're done, <b>copy the line at the bottom and paste
it to Claude</b>.
</div>
"""

HTML_TAIL = """
<div class="sticky">
<div class="count" id="count">0 of N answered</div>
<textarea id="out" readonly>(click your answers above; this line fills in)</textarea>
</div>
<script>
const answers = {};
function pick(id, val, btn){
  answers[id] = val;
  btn.parentElement.querySelectorAll('button').forEach(b=>b.classList.remove('on','Y','N','Q'));
  btn.classList.add('on', val==='?' ? 'Q' : val);
  const ids = Object.keys(answers).map(Number).sort((a,b)=>a-b);
  document.getElementById('out').value = 'stop labels: ' + ids.map(i=>i+':'+answers[i]).join(' ');
  document.getElementById('count').textContent = ids.length + ' of N answered';
}
</script></body></html>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    pool, segs, box_of = [], {}, {}
    ways_of, dem_of = {}, {}
    for box in g.REGIONS[REGION]:
        name = box[0]
        texts, info, _ = g.download_box("cache", REGION, box, offline=True)
        ways = g.get_ways("cache", REGION, box, offline=True)
        if not texts or not ways:
            continue
        matcher = g.WayMatcher(ways, box)
        ways_of[name] = ways
        tif = Path("cache/layers") / f"{name}_dem5m.tif"
        dem_of[name] = fl.dem(Path("cache/layers"), name, None) \
            if tif.exists() else None
        seen = set()
        for k, trace in enumerate(g.timed_traces(texts, info)):
            if g.classify(trace) not in g.USABLE:
                continue
            fp = g.fingerprint(trace)
            if fp in seen:
                continue
            seen.add(fp)
            tid = f"{name}#{k}"
            segs[tid] = trace["segments"]
            box_of[tid] = name
            pool += episodes_for_trace(tid, trace, matcher)
    pool = pd.DataFrame(pool)
    print("candidate episodes on trails:",
          pool["kind"].value_counts().to_dict())

    chosen = []
    for kind, n in PICK.items():
        cand = pool[pool["kind"] == kind].sample(frac=1, random_state=SEED)
        per_trace = {}
        for _, row in cand.iterrows():
            if per_trace.get(row["trace"], 0) >= MAX_PER_TRACE:
                continue
            chosen.append(row)
            per_trace[row["trace"]] = per_trace.get(row["trace"], 0) + 1
            if sum(1 for r in chosen if r["kind"] == kind) == n:
                break
    chosen = pd.DataFrame(chosen).sample(frac=1, random_state=SEED + 1)
    chosen = chosen.reset_index(drop=True)
    chosen.insert(0, "id", np.arange(1, len(chosen) + 1))

    cards, key_rows, label_rows = [], [], []
    for _, ep in chosen.iterrows():
        seg = segs[ep["trace"]][ep["segment"]]
        img, facts, nums = draw(ep, seg, ways_of[box_of[ep["trace"]]],
                                dem_of[box_of[ep["trace"]]])
        f = facts
        cards.append(f"""
<div class="card" id="c{ep['id']}">
<h2>#{ep['id']}</h2>
<img src="data:image/png;base64,{img}">
<div class="facts"><span><b>Duration:</b> {f['duration']}</span>
<span><b>Net move (start to end):</b> {f['net_move_m']}</span>
<span><b>90% of dots within:</b> {f['spread_m']} of center</span>
<span><b>GPS point every:</b> {f['gps_every_s']}</span>
<span><b>Elevation:</b> {f.get('elevation', '?')}</span>
<span><b>Trail grade just before:</b> {f.get('grade_before', '?')}</span>
<span><b>When:</b> {f['when']}</span></div>
<div class="btns">
<button onclick="pick({ep['id']},'Y',this)">Stopped</button>
<button onclick="pick({ep['id']},'N',this)">Moving slowly</button>
<button onclick="pick({ep['id']},'?',this)">Can't tell</button>
</div></div>""")
        key_rows.append({"id": ep["id"], "kind": ep["kind"],
                         "trace": ep["trace"], "segment": ep["segment"],
                         "t_start": ep["t_start"], "t_end": ep["t_end"],
                         "duration_s": ep["duration_s"], **nums})
        label_rows.append({"id": ep["id"], "duration": f["duration"],
                           "net_move": f["net_move_m"],
                           "when": f["when"],
                           "your_label (Y stopped / N moving / ?)": "",
                           "notes": ""})

    html = HTML_HEAD + "\n".join(cards) + \
        HTML_TAIL.replace("of N answered", f"of {len(cards)} answered")
    (OUT / "stop_check.html").write_text(html, encoding="utf-8")
    pd.DataFrame(label_rows).to_csv(OUT / "stop_labels.csv", index=False)
    pd.DataFrame(key_rows).to_csv(KEY, index=False)
    print(f"wrote {OUT / 'stop_check.html'} ({len(cards)} cards), "
          f"{OUT / 'stop_labels.csv'}, and the hidden key {KEY}")


if __name__ == "__main__":
    main()
