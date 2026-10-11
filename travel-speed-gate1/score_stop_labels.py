#!/usr/bin/env python3
"""
Score stop rules against Brian's hand labels (stop-checking sheet).

Takes the line copied from stop_check.html, e.g.
    stop labels: 1:Y 2:N 3:? ...
and, for many versions of the two rule families, asks: on how many of the
labeled moments does the rule agree with the human? "?" answers are skipped.

  crude family:   step speed < V km/h, sustained for >= D seconds
  window family:  any stretch of >= W seconds that ends < R meters away

A moment counts as "stopped" by a rule if the rule flags at least half of
its time. With ~20 labels this is a sanity check and a way to choose between
families, not a precise fit; the chosen rule then goes in DECISIONS_LOG.md.

Run:  python score_stop_labels.py "stop labels: 1:Y 2:N 3:? ..."
"""

import itertools
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import gate1_audit as g

KEY = Path("results/stop_check_key.csv")


def parse_labels(text):
    labels = {}
    for i, v in re.findall(r"(\d+)\s*[:=,]?\s*([YyNn?])", text):
        labels[int(i)] = v.upper()
    return labels


def episode_points(row, segs):
    seg = segs[row.trace][int(row.segment)]
    lat, lon, t, _ = g.clean_segment(seg)
    k = g.thin(t)
    return lat[k], lon[k], t[k]


def crude_flags(lat, lon, t, v_max, min_dur):
    v, dt, _ = g.steps(lat, lon, t)
    slow = v < v_max
    out = np.zeros(len(v), bool)
    i = 0
    while i < len(v):
        if not slow[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(v) and slow[j + 1]:
            j += 1
        if dt[i:j + 1].sum() >= min_dur:
            out[i:j + 1] = True
        i = j + 1
    return out, dt


def window_flags(lat, lon, t, w, r):
    n = len(t)
    dt = np.diff(t)
    j = np.searchsorted(t, t + w, side="left")
    i_idx = np.nonzero(j < n)[0]
    j_idx = j[i_idx]
    d = g.haversine_m(lat[i_idx], lon[i_idx], lat[j_idx], lon[j_idx])
    ok = d < r
    mark = np.zeros(n, int)
    np.add.at(mark, i_idx[ok], 1)
    np.add.at(mark, j_idx[ok], -1)
    return np.cumsum(mark)[:-1] > 0, dt


def main():
    labels = parse_labels(" ".join(sys.argv[1:]))
    if not labels:
        sys.exit("paste the line from the sheet, e.g. "
                 "'stop labels: 1:Y 2:N 3:?'")
    key = pd.read_csv(KEY)
    key["label"] = key.id.map(labels)
    lab = key[key.label.isin(["Y", "N"])].copy()
    print(f"{len(labels)} answers: {sum(v == 'Y' for v in labels.values())} "
          f"stopped, {sum(v == 'N' for v in labels.values())} moving, "
          f"{sum(v == '?' for v in labels.values())} can't tell")

    # rebuild the hikes the episodes came from (cached Gate 1 sample)
    segs = {}
    for box in g.REGIONS["white_mountains"]:
        texts, info, _ = g.download_box("cache", "white_mountains", box,
                                        offline=True)
        seen = set()
        for k, tr in enumerate(g.timed_traces(texts, info)):
            if g.classify(tr) not in g.USABLE:
                continue
            fp = g.fingerprint(tr)
            if fp in seen:
                continue
            seen.add(fp)
            segs[f"{box[0]}#{k}"] = tr["segments"]

    pts = {r.id: episode_points(r, segs) for r in lab.itertuples()}

    def judged(flag_fn):
        pred = []
        for r in lab.itertuples():
            lat, lon, t = pts[r.id]
            flags, dt = flag_fn(lat, lon, t)
            mid = (t[:-1] + t[1:]) / 2
            inside = (mid >= r.t_start) & (mid <= r.t_end)
            share = dt[inside & flags].sum() / max(dt[inside].sum(), 1e-9)
            pred.append("Y" if share >= 0.5 else "N")
        pred = np.array(pred)
        truth = lab.label.to_numpy()
        tp = ((pred == "Y") & (truth == "Y")).sum()
        return {"agree": (pred == truth).mean(),
                "caught_stops": tp / max((truth == "Y").sum(), 1),
                "false_stops": ((pred == "Y") & (truth == "N")).sum()}

    rows = []
    for v_max, dur in itertools.product([0.5, 0.8, 1.0, 1.5],
                                        [0, 20, 40, 60]):
        rows.append({"rule": f"crude: < {v_max} km/h for >= {dur} s",
                     **judged(lambda la, lo, t: crude_flags(la, lo, t,
                                                            v_max, dur))})
    for w, r in itertools.product([30, 45, 60, 90], [5, 8, 10, 15, 20]):
        rows.append({"rule": f"window: >= {w} s ending < {r} m away",
                     **judged(lambda la, lo, t: window_flags(la, lo, t,
                                                             w, r))})
    res = pd.DataFrame(rows).sort_values(["agree", "false_stops"],
                                         ascending=[False, True])
    pd.set_option("display.width", 160)
    print(f"\nscored on {len(lab)} moments with a Y/N answer\n")
    print(res.head(15).to_string(index=False,
                                 formatters={"agree": "{:.0%}".format,
                                             "caught_stops": "{:.0%}".format}))
    cur = res[res.rule.str.startswith("window: >= 60 s ending < 10 m")]
    print("\ncurrent draft rule:\n" + cur.to_string(index=False, header=False))
    by_kind = lab.groupby("kind").label.value_counts().unstack(fill_value=0)
    print("\nyour answers by (hidden) moment type:\n" + by_kind.to_string())
    res.to_csv("results/stop_rule_scores.csv", index=False)


if __name__ == "__main__":
    main()
