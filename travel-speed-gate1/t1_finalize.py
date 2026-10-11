#!/usr/bin/env python3
"""
T1 last step for a built region: the columns T3 needs to split by geography,
and a final section on the data card.

plan sec. 10: "Split by trace and by geography, never by point ... hold out
whole traces, and ideally whole trail systems." Two labels per segment:

  trail_network  connected group of OSM trails (trails only; roads split
                 them). Informative, but too lumpy to split on: in the White
                 Mountains two networks hold 70% of the walked segments.
  block_10km     the 10 km x 10 km UTM square of the segment's midpoint.
                 The unit for geographic hold-out (spatial block CV).

Also adds a "T1 final" section to data_card.md: travel modes (t1_modes.py),
outings, the match rate, the stop-rule sensitivity and these splits.

Run after t1_build_dataset.py, t1_variants.py and t1_modes.py (all regions):
    python t1_finalize.py --region wm
"""

import argparse
import json

import numpy as np
import pandas as pd
from pyproj import Transformer

import regions
import t1_build_dataset as b

BLOCK_M = 10_000


def trail_networks(ways, cls, key):
    """OSM way id -> network id (connected components of trail ways)."""
    parent = {}

    def root(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    first = {}
    for k, w in enumerate(ways):
        if cls[k] != "trail":
            continue
        nodes = [(round(p["lat"], 7), round(p["lon"], 7))
                 for p in w.get("geometry") or [] if p]
        for a, c in zip(nodes[:-1], nodes[1:]):
            parent[root(a)] = root(c)
        if nodes:
            first[w["id"]] = nodes[0]
    roots = {wid: root(n) for wid, n in first.items()}
    ids = {r: f"{key}_net{i:04d}" for i, r in enumerate(sorted(set(
        roots.values())))}
    return {wid: ids[r] for wid, r in roots.items()}


def add_geography(seg, key, network):
    seg = seg.drop(columns=["trail_network", "block_10km"], errors="ignore")
    seg["trail_network"] = seg.osm_way_id.map(network)
    to_utm = Transformer.from_crs(4326, regions.utm_epsg(key),
                                  always_xy=True)
    x, y = to_utm.transform(((seg.lon0 + seg.lon1) / 2).to_numpy(),
                            ((seg.lat0 + seg.lat1) / 2).to_numpy())
    seg["block_10km"] = [f"{key}_{int(a // BLOCK_M)}_{int(c // BLOCK_M)}"
                         for a, c in zip(x, y)]
    return seg


def card_section(d, key):
    seg = pd.read_parquet(d / "segments_L50.parquet")
    tr = pd.read_csv(d / "traces.csv")
    walk = seg[seg.hiking_trace & (seg.way_class == "trail")
               & (seg["mode"] == "walk") & ~seg.suspect]
    lines = ["", "## T1 final (t1_finalize.py)", ""]
    if (d / "modes.csv").exists():
        m = pd.read_csv(d / "modes.csv")
        h = m[m.trace_id.isin(tr.loc[tr.hiking_trace, "trace_id"])]
        lines += [f"- travel mode of hiking traces (t1_modes.py): "
                  f"{h['mode'].value_counts().to_dict()}",
                  f"- foot-only anchor traces called walking: "
                  f"{int((h.foot_anchor & (h['mode'] == 'walk')).sum())} "
                  f"of {int(h.foot_anchor.sum())}"]
    h = tr[tr.hiking_trace]
    lines += [
        f"- walking trail segments (50 m, not suspect): {len(walk):,} from "
        f"{walk.trace_id.nunique()} traces = {walk.outing_id.nunique()} "
        f"outings",
        f"- map-match rate: {100 * (tr.matched_share * tr.points_used).sum() / tr.points_used.sum():.1f}% "
        f"of points (hiking traces "
        f"{100 * (h.matched_share * h.points_used).sum() / h.points_used.sum():.1f}%)",
        f"- trail networks with walking segments: "
        f"{walk.trail_network.nunique()}; largest holds "
        f"{100 * walk.trail_network.value_counts(normalize=True).iloc[0]:.0f}%"
        f" of segments",
        f"- 10 km blocks with walking segments (unit for geographic "
        f"hold-out): {walk.block_10km.nunique()}"]
    # plan sec. 8: "sampling rate varies wildly ... record the interval per
    # trace; stratify or filter on it"
    import t1_variants as v
    iv = walk.groupby("trace_id").native_interval_s.median()
    rng, parts = np.random.default_rng(0), []
    for name, a, c in (("<= 2 s", 0, 2), ("2-6 s", 2, 6), ("> 6 s", 6, 1e9)):
        sub = walk[walk.trace_id.isin(iv[(iv > a) & (iv <= c)].index)]
        if sub.trace_id.nunique() < 10:
            parts.append(f"{name}: {sub.trace_id.nunique()} traces")
            continue
        v0, k, _ = v.fit(sub)
        lo, hi = np.percentile(v.boot(sub, rng), [2.5, 97.5], axis=0)
        parts.append(f"{name}: {sub.trace_id.nunique()} traces, v0 "
                     f"{v0:.2f} [{lo[0]:.2f}, {hi[0]:.2f}], k {k:.2f}")
    lines.append("- curve by GPS sampling interval (walkers): "
                 + "; ".join(parts))
    sens = d / "stop_rule_sensitivity.csv"
    if sens.exists():
        s = pd.read_csv(sens)
        lines.append("- stop-rule sensitivity (walkers): " + "; ".join(
            f"{r.rule} removes {r.time_removed_pct:.0f}%, v0 {r.v0_kmh:.2f} "
            f"[{r.v0_lo:.2f}, {r.v0_hi:.2f}], k {r.k:.2f}"
            for r in s.itertuples()))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="wm",
                    choices=sorted(regions.CANDIDATES))
    key = ap.parse_args().region
    d = regions.data_dir(key)
    b.init_layers(regions.region_name(key), regions.tiles(key))
    network = trail_networks(b.W["ways"], b.W["cls"], key)
    for f in sorted(d.glob("segments_L*.parquet")):
        add_geography(pd.read_parquet(f), key, network).to_parquet(
            f, index=False)
    card = (d / "data_card.md").read_text()
    card = card.split("\n## T1 final")[0].rstrip("\n") + "\n"
    lines = card_section(d, key)
    (d / "data_card.md").write_text(card + "\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
