#!/usr/bin/env python3
"""
Check the travel-mode calls (t1_modes.py) against what the uploaders' own
apps wrote into the original GPX files: a track <type> (Garmin: hiking,
cycling, running ...; Strava: 1 = Ride, 9 = Run ...) or a track name
("Morning Hike", "Afternoon Ride", "MTB Tour" ...). These labels never
look at speed, so they test the classifier without circularity. They are
noisy too (a hike recorded in cycling mode), so a disagreement is a case
to look at, not automatically a classifier error.

Only traces with an original GPX file can be checked: the identifiable and
public uploads fetched from the API (lab-only regions have none until their
full download lands).

Output (results/t1_mode_check/):
  labels.csv     one row per labeled hiking trace (label, where it came
                 from, our mode, the speed features)
  confusion.csv  label x mode counts, all regions
  summary.json   the headline shares
Run (cluster, after the builds):  python t1_mode_check.py
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

import regions
from t1_build_dataset import GPX_DIR, _open_any

OUT = Path("results/t1_mode_check")

# track <type> values -> label (lower case). Strava numbers: 1 Ride, 4 Hike,
# 9 Run, 10 Walk (checked against the track names below: see summary.json)
TYPE_LABEL = {
    "hike": ["hiking", "hike", "walking", "walk", "trekking", "backpacking",
             "mountaineering", "snowshoeing", "snowshoe", "4", "10",
             "nordic_walking", "on_foot", "foot"],
    "run": ["running", "run", "trail_running", "trailrunning", "9"],
    "bike": ["cycling", "biking", "bike", "road_biking", "mountain_biking",
             "mountainbiking", "mtb", "gravel_cycling", "cyclocross",
             "e_bike", "ebikeride", "ebike", "ride", "1"],
    "ski": ["alpineski", "alpine_skiing", "backcountryski",
            "backcountry_skiing", "nordicski", "cross_country_skiing",
            "skiing", "ski", "snowboard", "snowboarding", "skitour"],
}
TYPE_OF = {t: lab for lab, ts in TYPE_LABEL.items() for t in ts}

# words in a track name or description -> label (first match wins, in
# this order, so "bike to the hike" counts as bike)
NAME_WORDS = [
    ("ski", r"\b(ski|skiing|skitour\w*|skin(ning)?|splitboard\w*|"
            r"snowboard\w*|nordic ski)\b"),
    ("bike", r"\b(ride|rides|bike|bikes|biking|mtb|cycl\w*|bicycl\w*|"
             r"velo|vélo|radtour|radfahrt|fahrrad\w*|bici\w*|gravel)\b"),
    ("run", r"\b(run|runs|running|jog|jogging|trail ?run\w*|lauf)\b"),
    ("hike", r"\b(hike|hikes|hiking|hiked|walk|walks|walking|wanderung\w*|"
             r"wandern|randonn\w*|rando|trek\w*|caminata|senderismo|"
             r"backpack\w*|snowshoe\w*|summit|bushwhack\w*)\b"),
]


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def gpx_text_fields(path):
    """creator, track types and names/descriptions of an original upload."""
    creator, types, words = set(), [], []
    for text in _open_any(path):
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError:
            continue
        creator.add(root.attrib.get("creator", ""))
        for parent in root:
            ptag = _local(parent.tag)
            if ptag not in ("trk", "metadata", "rte"):
                continue
            for el in parent:                 # never walk the points
                name = _local(el.tag)
                if name == "extensions":      # e.g. an app's activity tag
                    types += [(x.text or "").strip() for x in el.iter()
                              if _local(x.tag) in ("activity", "type")
                              and (x.text or "").strip()]
                    continue
                val = (el.text or "").strip()
                if not val or name in ("trkseg", "rtept"):
                    continue
                if name == "type" and ptag in ("trk", "rte"):
                    types.append(val)
                elif name in ("name", "desc", "cmt", "keywords"):
                    words.append(val)
    return "; ".join(sorted(c for c in creator if c)), types, words


def label_of(types, words):
    """(label, how) from the track type, else from the words, else None."""
    for t in types:
        lab = TYPE_OF.get(t.strip().lower().replace(" ", "_"))
        if lab:
            return lab, "type"
    text = " ".join(words).lower()
    for lab, pat in NAME_WORDS:
        if re.search(pat, text):
            return lab, "name"
    return None, None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for key in regions.CANDIDATES:
        d = regions.data_dir(key)
        if not (d / "modes.csv").exists():
            continue
        tr = pd.read_csv(d / "traces.csv")
        modes = pd.read_csv(d / "modes.csv").set_index("trace_id")
        hik = tr[tr.hiking_trace & tr.trace_id.str.startswith("osm")]
        n_files = 0
        for tid in hik.trace_id:
            files = [f for f in sorted(GPX_DIR.glob(f"{tid[3:]}.*"))
                     if not f.name.endswith(".tmp")]
            if not files:
                continue
            n_files += 1
            creator, types, words = gpx_text_fields(files[0])
            lab, how = label_of(types, words)
            m = modes.loc[tid] if tid in modes.index else None
            rows.append({
                "region": key, "trace_id": tid, "label": lab, "how": how,
                "gpx_type": "|".join(types)[:60],
                "gpx_name": " | ".join(words)[:120], "creator": creator[:60],
                "mode": None if m is None else m["mode"],
                "foot_anchor": None if m is None else bool(m["foot_anchor"]),
                "v_med": None if m is None else m["v_med"],
                "v_p90": None if m is None else m["v_p90"],
                "asym": None if m is None else m["asym"]})
        got = sum(r["region"] == key and r["label"] is not None for r in rows)
        print(f"{key}: {len(hik)} hiking traces, {n_files} with an original "
              f"file, {got} labeled", flush=True)
    df = pd.DataFrame(rows)
    lab = df[df.label.notna()].copy()
    lab.to_csv(OUT / "labels.csv", index=False)
    conf = pd.crosstab(lab.label, lab["mode"], margins=True)
    conf.to_csv(OUT / "confusion.csv")
    print(conf.to_string())

    def share(sub, col, val):
        return None if not len(sub) else round(100 * (sub[col] == val).mean(),
                                               1)

    hike, bike = lab[lab.label == "hike"], lab[lab.label == "bike"]
    walk_called = lab[lab["mode"] == "walk"]
    strava = df[df.gpx_type.isin(["1", "4", "9", "10"])]
    out = {
        "hiking_traces_with_original_file": int(len(df)),
        "labeled": int(len(lab)),
        "labeled_by": lab.how.value_counts().to_dict(),
        "labels": lab.label.value_counts().to_dict(),
        "hike_labels_called_walk_pct": share(hike, "mode", "walk"),
        "bike_labels_called_bike_ski_pct": share(bike, "mode", "bike/ski"),
        "bike_labels_called_walk_pct": share(bike, "mode", "walk"),
        "called_walk_labeled_bike_or_ski_pct": round(
            100 * walk_called.label.isin(["bike", "ski"]).mean(), 1)
        if len(walk_called) else None,
        "called_walk_n_labeled": int(len(walk_called)),
        "strava_numeric_types_vs_names": {
            t: pd.Series([label_of([], [w])[0] for w in
                          strava[strava.gpx_type == t].gpx_name])
            .value_counts(dropna=False).to_dict()
            for t in ["1", "4", "9", "10"]},
    }
    (OUT / "summary.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))
    worst = lab[(lab.label == "bike") & (lab["mode"] == "walk")]
    if len(worst):
        print("\nbike labels called walk (look at these):")
        print(worst[["region", "trace_id", "gpx_type", "gpx_name", "v_med",
                     "v_p90", "asym"]].to_string(index=False))


if __name__ == "__main__":
    main()
